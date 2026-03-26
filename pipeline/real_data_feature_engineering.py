"""
Feature engineering for observable real-data route snapshots.

The design goal here is strict: do not invent missing operational or
commercial inputs. Missing values remain NaN so the model can handle them
explicitly instead of being fed synthetic stand-ins.
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3

import numpy as np
import pandas as pd

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
OBSERVED_TABLE = "route_observations"


class RealDataFeatureEngineer:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def load_from_database(self, query=None):
        conn = sqlite3.connect(self.db_path)
        try:
            if query is None:
                query = f"SELECT * FROM {OBSERVED_TABLE} ORDER BY observation_id DESC"
            return pd.read_sql_query(query, conn)
        finally:
            conn.close()

    def engineer_features(self, df):
        df = df.copy()
        eps = 1e-6

        if "observed_at" in df.columns:
            df["observed_at"] = pd.to_datetime(df["observed_at"])
            df["day"] = df["observed_at"].dt.day
            df["hour"] = df["observed_at"].dt.hour

        if {"port_efficiency_origin", "port_efficiency_destination"}.issubset(df.columns):
            df["port_efficiency_diff"] = (
                pd.to_numeric(df["port_efficiency_origin"], errors="coerce")
                - pd.to_numeric(df["port_efficiency_destination"], errors="coerce")
            )

        if {"port_congestion_origin", "port_congestion_destination"}.issubset(df.columns):
            df["port_congestion_total"] = (
                pd.to_numeric(df["port_congestion_origin"], errors="coerce")
                + pd.to_numeric(df["port_congestion_destination"], errors="coerce")
            )

        if {"weather_severity_origin", "weather_severity_destination"}.issubset(df.columns):
            df["weather_risk_total"] = (
                pd.to_numeric(df["weather_severity_origin"], errors="coerce")
                + pd.to_numeric(df["weather_severity_destination"], errors="coerce")
            )

        if {"temp_deviation_origin", "temp_deviation_destination"}.issubset(df.columns):
            df["temp_diff"] = (
                pd.to_numeric(df["temp_deviation_origin"], errors="coerce")
                - pd.to_numeric(df["temp_deviation_destination"], errors="coerce")
            )

        if {"wind_speed_origin", "wind_speed_destination"}.issubset(df.columns):
            df["wind_risk"] = (
                pd.to_numeric(df["wind_speed_origin"], errors="coerce")
                + pd.to_numeric(df["wind_speed_destination"], errors="coerce")
            ) / 2.0

        if "container_weight_teus" in df.columns:
            df["weight_per_container"] = pd.to_numeric(
                df["container_weight_teus"], errors="coerce"
            )

        if {"total_teus", "container_count"}.issubset(df.columns):
            df["teu_per_container"] = pd.to_numeric(
                df["total_teus"], errors="coerce"
            ) / (pd.to_numeric(df["container_count"], errors="coerce") + eps)

        if {"distance_nm", "base_transit_time"}.issubset(df.columns):
            df["estimated_speed_nm_per_day"] = pd.to_numeric(
                df["distance_nm"], errors="coerce"
            ) / (pd.to_numeric(df["base_transit_time"], errors="coerce") + eps)

        if {
            "port_congestion_total",
            "port_efficiency_origin",
            "port_efficiency_destination",
        }.issubset(df.columns):
            df["congestion_pressure"] = pd.to_numeric(
                df["port_congestion_total"], errors="coerce"
            ) / (
                pd.to_numeric(df["port_efficiency_origin"], errors="coerce")
                + pd.to_numeric(df["port_efficiency_destination"], errors="coerce")
                + eps
            )

        if {
            "vessels_at_port_origin",
            "vessels_at_port_destination",
            "crane_availability",
        }.issubset(df.columns):
            df["port_capacity_pressure"] = (
                pd.to_numeric(df["vessels_at_port_origin"], errors="coerce")
                + pd.to_numeric(df["vessels_at_port_destination"], errors="coerce")
            ) / (pd.to_numeric(df["crane_availability"], errors="coerce") + eps)

        if {"weather_risk_total", "port_congestion_total"}.issubset(df.columns):
            df["weather_port_interaction"] = pd.to_numeric(
                df["weather_risk_total"], errors="coerce"
            ) * (1.0 + pd.to_numeric(df["port_congestion_total"], errors="coerce") / 10.0)

        if "month" in df.columns:
            df["is_peak_season"] = (
                pd.to_numeric(df["month"], errors="coerce").isin([11, 12, 1, 2]).astype(float)
            )

        if {"quarter", "demand_factor"}.issubset(df.columns):
            df["quarter_demand"] = pd.to_numeric(df["quarter"], errors="coerce") * pd.to_numeric(
                df["demand_factor"], errors="coerce"
            )

        if {"fuel_price_origin", "fuel_price_destination"}.issubset(df.columns):
            df["fuel_cost_diff"] = (
                pd.to_numeric(df["fuel_price_origin"], errors="coerce")
                - pd.to_numeric(df["fuel_price_destination"], errors="coerce")
            )
            df["fuel_cost_avg"] = (
                pd.to_numeric(df["fuel_price_origin"], errors="coerce")
                + pd.to_numeric(df["fuel_price_destination"], errors="coerce")
            ) / 2.0

        if {"vessels_at_port_origin", "crane_availability"}.issubset(df.columns):
            df["origin_crowding_index"] = pd.to_numeric(
                df["vessels_at_port_origin"], errors="coerce"
            ) / (pd.to_numeric(df["crane_availability"], errors="coerce") + eps)

        if {"port_charges_origin", "port_charges_destination"}.issubset(df.columns):
            df["port_charge_total"] = (
                pd.to_numeric(df["port_charges_origin"], errors="coerce")
                + pd.to_numeric(df["port_charges_destination"], errors="coerce")
            )

        if {"customs_complexity", "port_congestion_destination"}.issubset(df.columns):
            df["compound_friction"] = pd.to_numeric(
                df["customs_complexity"], errors="coerce"
            ) * pd.to_numeric(df["port_congestion_destination"], errors="coerce")

        return df

    def get_model_features(self, df, feature_order):
        engineered_df = self.engineer_features(df)
        feature_frame = pd.DataFrame(index=engineered_df.index)

        for col in feature_order:
            if col in engineered_df.columns:
                feature_frame[col] = pd.to_numeric(engineered_df[col], errors="coerce")
            else:
                feature_frame[col] = np.nan

        return feature_frame


if __name__ == "__main__":
    engineer = RealDataFeatureEngineer()
    df = engineer.load_from_database(f"SELECT * FROM {OBSERVED_TABLE} ORDER BY observation_id DESC LIMIT 5")
    print(engineer.engineer_features(df).to_string())
