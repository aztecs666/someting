"""
Audit the observable real-data pipeline.
"""

import json
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3

import pandas as pd

from data.real_data_fetcher import (
    EXTERNAL_BENCHMARKS_TABLE,
    MARKET_RATE_HISTORY_TABLE,
    OBSERVED_TABLE,
    PREDICTIONS_TABLE,
    QUOTE_HISTORY_TABLE,
    RealDataFetcher,
    ROUTE_FORECASTS_TABLE,
)
from app.forecast_support import ARTIFACT_PATH
from app.real_time_predictor import RealTimePredictor

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
PROFILE_PATH = os.path.join(PROJECT_ROOT, "ml", "training_reference_profile.json")


def load_profile():
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_sql(query):
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def latest_joined(limit=20):
    query = f"""
    SELECT
        o.observation_id,
        o.observed_at,
        o.route_name,
        o.origin_port,
        o.destination_port,
        o.source_weather,
        o.source_marine,
        o.source_schedule,
        o.source_port_calls,
        o.distance_nm,
        o.weather_severity_origin,
        o.weather_severity_destination,
        o.wind_speed_origin,
        o.wind_speed_destination,
        o.visibility_nm,
        o.wave_height,
        o.data_quality_score,
        p.predicted_at,
        p.observed_feature_coverage_pct,
        p.drift_feature_count,
        p.predicted_shipping_price,
        p.predicted_delay_days,
        p.predicted_route_efficiency,
        p.predicted_port_efficiency,
        p.predicted_cost_per_teu,
        p.predicted_total_risk_score
    FROM {OBSERVED_TABLE} o
    LEFT JOIN {PREDICTIONS_TABLE} p
      ON p.prediction_id = (
          SELECT p2.prediction_id
          FROM {PREDICTIONS_TABLE} p2
          WHERE p2.observation_id = o.observation_id
          ORDER BY p2.prediction_id DESC
          LIMIT 1
      )
    ORDER BY o.observation_id DESC
    LIMIT {int(limit)}
    """
    return read_sql(query)


def benchmark_summary():
    query = f"""
    SELECT provider, metric_name, COUNT(*) AS row_count
    FROM {EXTERNAL_BENCHMARKS_TABLE}
    GROUP BY provider, metric_name
    ORDER BY provider, metric_name
    """
    return read_sql(query)


def forecast_duplicate_summary():
    query = f"""
    SELECT
        COUNT(*) AS duplicate_windows,
        COALESCE(SUM(row_count - 1), 0) AS redundant_rows
    FROM (
        SELECT COUNT(*) AS row_count
        FROM {ROUTE_FORECASTS_TABLE}
        GROUP BY
            forecast_date,
            departure_window_start,
            departure_window_end,
            route_name,
            origin_port,
            destination_port,
            container_type
        HAVING COUNT(*) > 1
    ) duplicate_groups
    """
    return read_sql(query)


def drift_summary(profile, predictor):
    if not predictor.is_ready():
        return pd.DataFrame()

    observations = predictor.load_observations(limit=50)
    if observations is None or observations.empty:
        return pd.DataFrame()

    X, coverage_pct, drift_count = predictor.prepare_features(
        observations, clip_to_training_range=False
    )
    feature_ranges = profile.get("feature_ranges", {})
    rows = []
    for col, bounds in feature_ranges.items():
        if col not in X.columns:
            continue
        series = pd.to_numeric(X[col], errors="coerce")
        below = (series < bounds["min"]).sum(skipna=True)
        above = (series > bounds["max"]).sum(skipna=True)
        if below or above:
            rows.append(
                {
                    "feature": col,
                    "rows_below_min": int(below),
                    "rows_above_max": int(above),
                    "training_min": bounds["min"],
                    "training_max": bounds["max"],
                }
            )
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        by=["rows_above_max", "rows_below_min"], ascending=False
    )


def main():
    RealDataFetcher(DB_PATH)
    predictor = RealTimePredictor()
    profile = load_profile()
    joined = latest_joined()
    benchmarks = benchmark_summary()
    duplicates = forecast_duplicate_summary()
    drift = drift_summary(profile, predictor)

    print("=" * 72)
    print("OBSERVABLE REAL-DATA AUDIT")
    print("=" * 72)

    print(f"Database: {DB_PATH}")
    print(f"Observed route snapshots: {len(read_sql(f'SELECT observation_id FROM {OBSERVED_TABLE}'))}")
    print(f"Prediction rows: {len(read_sql(f'SELECT prediction_id FROM {PREDICTIONS_TABLE}'))}")
    print(f"Quote history rows: {len(read_sql(f'SELECT quote_id FROM {QUOTE_HISTORY_TABLE}'))}")
    print(f"Market benchmark history rows: {len(read_sql(f'SELECT market_rate_id FROM {MARKET_RATE_HISTORY_TABLE}'))}")
    print(f"Route forecast rows: {len(read_sql(f'SELECT forecast_id FROM {ROUTE_FORECASTS_TABLE}'))}")
    print(f"Route forecaster artifact present: {os.path.exists(ARTIFACT_PATH)}")
    print(f"Observable predictor ready: {predictor.is_ready()}")
    print(f"Observable predictor status: {predictor.readiness_message()}")
    print(
        "Duplicate forecast windows: "
        f"{int(duplicates.iloc[0]['duplicate_windows'])} "
        f"(redundant rows: {int(duplicates.iloc[0]['redundant_rows'])})"
    )

    print("\nLatest observable rows:")
    cols = [
        "observation_id",
        "route_name",
        "source_weather",
        "source_marine",
        "source_schedule",
        "source_port_calls",
        "distance_nm",
        "data_quality_score",
        "observed_feature_coverage_pct",
        "drift_feature_count",
    ]
    print(joined[cols].fillna("NULL").to_string(index=False))

    if drift is not None and not drift.empty:
        print("\nTop feature drift against training ranges:")
        print(drift.head(12).to_string(index=False))

    print("\nPrediction summary:")
    pred_cols = [
        "predicted_shipping_price",
        "predicted_delay_days",
        "predicted_route_efficiency",
        "predicted_port_efficiency",
        "predicted_cost_per_teu",
        "predicted_total_risk_score",
    ]
    print(joined[pred_cols].describe().round(2).to_string())

    print("\nExternal comparison rows:")
    if benchmarks.empty:
        print("None loaded yet. This table is only for comparing your forecasts against third-party provider forecasts.")
    else:
        print(benchmarks.to_string(index=False))

    forecast_rows = read_sql(
        f"""
        SELECT forecast_date, departure_window_start, route_name, container_type,
               expected_low_cost, expected_base_cost, expected_high_cost,
               weather_cost_uplift, expected_delay_days, confidence_score, rank_by_cost
        FROM {ROUTE_FORECASTS_TABLE}
        ORDER BY departure_window_start, rank_by_cost
        LIMIT 20
        """
    )
    print("\nLatest route forecasts:")
    if forecast_rows.empty:
        print("None generated yet.")
    else:
        print(forecast_rows.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
