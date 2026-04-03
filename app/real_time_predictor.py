"""
Real-time predictor for observable route snapshots.
"""

import json
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from pipeline.real_data_feature_engineering import (
    OBSERVED_TABLE,
    RealDataFeatureEngineer,
)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(PROJECT_ROOT, "ml")
MODEL_BUNDLE_PATH = os.path.join(MODEL_DIR, "xgb_models.joblib")
FEATURE_ORDER_PATH = os.path.join(MODEL_DIR, "xgb_features.joblib")
TRAINING_PROFILE_FILE = os.path.join(PROJECT_ROOT, "ml", "training_reference_profile.json")
PREDICTIONS_TABLE = "route_predictions"
BUILD_COMMAND = "python scripts/build_observable_artifacts.py"

TARGET_TO_OUTPUT = {
    "total_supply_chain_cost": "predicted_shipping_price",
    "delay_days": "predicted_delay_days",
    "route_efficiency": "predicted_route_efficiency",
    "port_efficiency_combined": "predicted_port_efficiency",
    "cost_per_teu": "predicted_cost_per_teu",
    "total_risk_score": "predicted_total_risk_score",
}


class RealTimePredictor:
    def __init__(self, db_path=DB_PATH, model_dir=MODEL_DIR, training_profile_path=TRAINING_PROFILE_FILE):
        self.db_path = db_path
        self.model_dir = model_dir
        self.training_profile_path = training_profile_path
        self.models = {}
        self.feature_order = []
        self.training_profile = {}
        self._readiness_message = "Observable predictor artifacts have not been loaded."
        self._load_models()
        self._load_training_profile()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _load_models(self):
        missing_artifacts = []
        if not os.path.exists(MODEL_BUNDLE_PATH):
            missing_artifacts.append(os.path.basename(MODEL_BUNDLE_PATH))
        if not os.path.exists(FEATURE_ORDER_PATH):
            missing_artifacts.append(os.path.basename(FEATURE_ORDER_PATH))
        if missing_artifacts:
            self.models = {}
            self.feature_order = []
            self._readiness_message = (
                "Observable predictor disabled: missing "
                + ", ".join(missing_artifacts)
                + " in ml/. This stage is retired until a reproducible builder is available. "
                + f"See {BUILD_COMMAND}."
            )
            return

        try:
            self.models = joblib.load(MODEL_BUNDLE_PATH)
            self.feature_order = joblib.load(FEATURE_ORDER_PATH)
        except Exception as exc:
            self.models = {}
            self.feature_order = []
            self._readiness_message = (
                f"Observable predictor disabled: failed to load artifacts ({exc}). "
                f"Rebuild support is currently retired; see {BUILD_COMMAND}."
            )
            return

        if not self.models:
            self._readiness_message = (
                f"Observable predictor disabled: loaded model bundle is empty. See {BUILD_COMMAND}."
            )
            return
        if not self.feature_order:
            self._readiness_message = (
                f"Observable predictor disabled: loaded feature order is empty. See {BUILD_COMMAND}."
            )
            return

        self._readiness_message = "Observable predictor ready."

    def is_ready(self):
        return bool(self.models) and bool(self.feature_order)

    def readiness_message(self):
        return self._readiness_message

    def _load_training_profile(self):
        if os.path.exists(self.training_profile_path):
            with open(self.training_profile_path, "r", encoding="utf-8") as fh:
                self.training_profile = json.load(fh)

    def load_observations(self, limit=50):
        conn = self._connect()
        try:
            return pd.read_sql_query(
                f"SELECT * FROM {OBSERVED_TABLE} ORDER BY observation_id DESC LIMIT {int(limit)}",
                conn,
            )
        finally:
            conn.close()

    def _clip_to_training_ranges(self, X):
        feature_ranges = self.training_profile.get("feature_ranges", {})
        if not feature_ranges:
            return X, 0

        drift_count = 0
        X = X.copy()
        for col, bounds in feature_ranges.items():
            if col not in X.columns:
                continue
            mask = X[col].notna() & ((X[col] < bounds["min"]) | (X[col] > bounds["max"]))
            if mask.any():
                drift_count += int(mask.sum())
                X.loc[mask, col] = X.loc[mask, col].clip(bounds["min"], bounds["max"])
        return X, drift_count

    def prepare_features(self, observations_df, clip_to_training_range=True):
        if not self.feature_order:
            return pd.DataFrame(index=observations_df.index), 0.0, 0

        engineer = RealDataFeatureEngineer(self.db_path)
        X = engineer.get_model_features(observations_df, self.feature_order)
        coverage_pct = float(X.notna().sum(axis=1).mean() / len(self.feature_order) * 100.0)

        drift_count = 0
        if clip_to_training_range:
            X, drift_count = self._clip_to_training_ranges(X)

        return X, coverage_pct, drift_count

    def predict_dataframe(self, observations_df, clip_to_training_range=True):
        if observations_df is None or observations_df.empty or not self.is_ready():
            return None

        X, coverage_pct, drift_count = self.prepare_features(
            observations_df, clip_to_training_range=clip_to_training_range
        )
        predictions_df = observations_df.copy().reset_index(drop=True)

        for target_col, model in self.models.items():
            predictions_df[TARGET_TO_OUTPUT[target_col]] = model.predict(X)

        predictions_df["observed_feature_coverage_pct"] = coverage_pct
        predictions_df["drift_feature_count"] = drift_count
        return predictions_df

    def save_predictions(self, predictions_df):
        if predictions_df is None or predictions_df.empty:
            return

        rows = []
        for row in predictions_df.itertuples(index=False):
            rows.append(
                (
                    int(row.observation_id),
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "xgb_models.joblib",
                    "observable-real-mode",
                    float(row.observed_feature_coverage_pct),
                    int(row.drift_feature_count),
                    float(row.predicted_shipping_price),
                    float(row.predicted_delay_days),
                    float(row.predicted_route_efficiency),
                    float(row.predicted_port_efficiency),
                    float(row.predicted_cost_per_teu),
                    float(row.predicted_total_risk_score),
                )
            )

        conn = self._connect()
        cursor = conn.cursor()
        cursor.executemany(
            f"""
            INSERT INTO {PREDICTIONS_TABLE} (
                observation_id,
                predicted_at,
                model_name,
                model_version,
                observed_feature_coverage_pct,
                drift_feature_count,
                predicted_shipping_price,
                predicted_delay_days,
                predicted_route_efficiency,
                predicted_port_efficiency,
                predicted_cost_per_teu,
                predicted_total_risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        conn.close()

    def run_predictions(self, limit=50, persist=True):
        observations_df = self.load_observations(limit=limit)
        predictions_df = self.predict_dataframe(observations_df)
        if persist:
            self.save_predictions(predictions_df)
        return predictions_df


if __name__ == "__main__":
    predictor = RealTimePredictor()
    output = predictor.run_predictions(limit=10, persist=False)
    if output is None or output.empty:
        print(predictor.readiness_message())
        raise SystemExit(0)
    cols = [
        "observation_id",
        "route_name",
        "predicted_shipping_price",
        "predicted_delay_days",
        "predicted_route_efficiency",
        "predicted_port_efficiency",
        "predicted_cost_per_teu",
        "predicted_total_risk_score",
        "observed_feature_coverage_pct",
    ]
    print(output[cols].round(2).to_string(index=False))
