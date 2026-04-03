import argparse
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import (
    ARTIFACT_PATH,
    DB_PATH,
    ROUTE_FORECASTS_TABLE,
    build_training_dataset,
    describe_training_provenance,
    load_forecaster_bundle,
    load_market_rate_history,
    predict_forecaster_bundle,
    sync_public_benchmarks,
    time_split,
)


def _latest_forecast_window(db_path, model_version):
    conn = sqlite3.connect(db_path)
    try:
        query = f"""
        SELECT
            forecast_date,
            MIN(departure_window_start) AS min_departure_window_start,
            MAX(departure_window_start) AS max_departure_window_start,
            COUNT(*) AS row_count
        FROM {ROUTE_FORECASTS_TABLE}
        WHERE model_version = ?
        GROUP BY forecast_date
        ORDER BY forecast_date DESC
        LIMIT 1
        """
        row = conn.execute(query, (model_version,)).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return {
        "forecast_date": str(row[0]),
        "min_departure_window_start": str(row[1]),
        "max_departure_window_start": str(row[2]),
        "row_count": int(row[3]),
    }


def _latest_market_history_date():
    market_history = load_market_rate_history(DB_PATH)
    if market_history.empty:
        return None
    benchmark_dates = pd.to_datetime(market_history["benchmark_date"], errors="coerce")
    if benchmark_dates.isna().all():
        return None
    return str(benchmark_dates.max().date())


def _evaluate(bundle, training_df):
    train_df, test_df = time_split(training_df)
    y_test = test_df["target_cost_usd"].astype(float)

    base_pred, low_pred, high_pred = predict_forecaster_bundle(bundle, test_df)

    baseline_series = (
        pd.to_numeric(test_df["latest_observed_benchmark_cost"], errors="coerce")
        if "latest_observed_benchmark_cost" in test_df.columns
        else pd.Series(np.nan, index=test_df.index)
    )
    if baseline_series.isna().all() and "lag_1d_cost" in test_df.columns:
        baseline_series = pd.to_numeric(test_df["lag_1d_cost"], errors="coerce")
    baseline_series = baseline_series.ffill().bfill()

    baseline_mae = mean_absolute_error(y_test, baseline_series)
    baseline_mape = float(
        np.mean(
            np.abs(
                (y_test - baseline_series)
                / np.where(np.abs(y_test) < 1e-9, 1.0, y_test)
            )
        )
        * 100.0
    )

    metrics = {
        "test_rows": int(len(test_df)),
        "mae": round(float(mean_absolute_error(y_test, base_pred)), 2),
        "rmse": round(float(np.sqrt(mean_squared_error(y_test, base_pred))), 2),
        "mape_pct": round(
            float(
                np.mean(
                    np.abs(
                        (y_test - base_pred)
                        / np.where(np.abs(y_test) < 1e-9, 1.0, y_test)
                    )
                )
                * 100.0
            ),
            2,
        ),
        "interval_coverage_pct": round(
            float(((y_test >= low_pred) & (y_test <= high_pred)).mean() * 100.0), 2
        ),
        "baseline_mae": round(float(baseline_mae), 2),
        "baseline_mape_pct": round(float(baseline_mape), 2),
        "mae_improvement_vs_baseline_pct": round(
            float(((baseline_mae - mean_absolute_error(y_test, base_pred)) / baseline_mae) * 100.0)
            if baseline_mae > 0
            else 0.0,
            2,
        ),
    }

    detail = test_df[
        [
            "feature_date",
            "departure_window_start",
            "route_name",
            "container_type",
            "target_cost_usd",
            "latest_observed_benchmark_cost",
            "training_data_mode",
            "training_data_source",
        ]
    ].copy()
    detail["predicted_cost_usd"] = base_pred
    detail["predicted_low_cost_usd"] = low_pred
    detail["predicted_high_cost_usd"] = high_pred
    detail["abs_error"] = np.abs(detail["target_cost_usd"] - detail["predicted_cost_usd"])
    detail["ape_pct"] = (
        np.abs(detail["target_cost_usd"] - detail["predicted_cost_usd"])
        / np.where(np.abs(detail["target_cost_usd"]) < 1e-9, 1.0, detail["target_cost_usd"])
        * 100.0
    )

    route_metrics = (
        detail.groupby(["route_name", "container_type"], as_index=False)
        .agg(
            samples=("target_cost_usd", "count"),
            mae=("abs_error", "mean"),
            mape_pct=("ape_pct", "mean"),
        )
        .sort_values(["mape_pct", "mae"])
        .reset_index(drop=True)
    )
    route_metrics["mae"] = route_metrics["mae"].round(2)
    route_metrics["mape_pct"] = route_metrics["mape_pct"].round(2)

    return metrics, route_metrics, detail


def _window_metrics(detail, days):
    if detail.empty:
        return None

    latest_feature_date = pd.to_datetime(detail["feature_date"], errors="coerce").max()
    if pd.isna(latest_feature_date):
        return None

    cutoff = latest_feature_date - pd.Timedelta(days=days - 1)
    window = detail[pd.to_datetime(detail["feature_date"], errors="coerce") >= cutoff].copy()
    if window.empty:
        return None

    baseline_series = (
        pd.to_numeric(window["latest_observed_benchmark_cost"], errors="coerce")
        .ffill()
        .bfill()
    )
    model_mae = mean_absolute_error(window["target_cost_usd"], window["predicted_cost_usd"])
    baseline_mae = mean_absolute_error(window["target_cost_usd"], baseline_series)
    model_rmse = np.sqrt(mean_squared_error(window["target_cost_usd"], window["predicted_cost_usd"]))
    model_mape = float(window["ape_pct"].mean())
    baseline_mape = float(
        np.mean(
            np.abs(
                (window["target_cost_usd"] - baseline_series)
                / np.where(np.abs(window["target_cost_usd"]) < 1e-9, 1.0, window["target_cost_usd"])
            )
        )
        * 100.0
    )

    return {
        "days": int(days),
        "rows": int(len(window)),
        "start_date": str(cutoff.date()),
        "end_date": str(latest_feature_date.date()),
        "mae": round(float(model_mae), 2),
        "rmse": round(float(model_rmse), 2),
        "mape_pct": round(model_mape, 2),
        "baseline_mae": round(float(baseline_mae), 2),
        "baseline_mape_pct": round(float(baseline_mape), 2),
        "mae_improvement_vs_baseline_pct": round(
            float(((baseline_mae - model_mae) / baseline_mae) * 100.0) if baseline_mae > 0 else 0.0,
            2,
        ),
    }


def _recent_route_metrics(detail, days):
    if detail.empty:
        return pd.DataFrame()

    latest_feature_date = pd.to_datetime(detail["feature_date"], errors="coerce").max()
    if pd.isna(latest_feature_date):
        return pd.DataFrame()

    cutoff = latest_feature_date - pd.Timedelta(days=days - 1)
    window = detail[pd.to_datetime(detail["feature_date"], errors="coerce") >= cutoff].copy()
    if window.empty:
        return pd.DataFrame()

    route_metrics = (
        window.groupby(["route_name", "container_type"], as_index=False)
        .agg(
            samples=("target_cost_usd", "count"),
            mae=("abs_error", "mean"),
            mape_pct=("ape_pct", "mean"),
        )
        .sort_values(["mape_pct", "mae"])
        .reset_index(drop=True)
    )
    route_metrics["mae"] = route_metrics["mae"].round(2)
    route_metrics["mape_pct"] = route_metrics["mape_pct"].round(2)
    return route_metrics


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the route forecaster against real holdout data and latest internet-synced benchmark history."
    )
    parser.add_argument("--sync-public", action="store_true")
    args = parser.parse_args()

    if args.sync_public:
        result = sync_public_benchmarks()
        print("Public benchmark sync:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print()

    if not os.path.exists(ARTIFACT_PATH):
        print("No route forecaster artifact found. Run train_route_forecaster.py first.")
        return

    training_df = build_training_dataset()
    if training_df.empty:
        print("No real planner training data found. Import quote history or sync/import external benchmark history first.")
        return

    bundle = load_forecaster_bundle()
    metrics, route_metrics, detail = _evaluate(bundle, training_df)
    latest_history_date = _latest_market_history_date()
    latest_forecast_window = _latest_forecast_window(DB_PATH, bundle["model_version"])
    recent_windows = [window for window in (_window_metrics(detail, 30), _window_metrics(detail, 60), _window_metrics(detail, 90)) if window]
    recent_route_metrics = _recent_route_metrics(detail, 60)

    print("=== ROUTE FORECASTER EVALUATION ===")
    print(f"Model version: {bundle['model_version']}")
    print(f"Training modes: {', '.join(bundle.get('training_data_modes', [])) or 'unknown'}")
    print(f"Training sources: {', '.join(bundle.get('training_data_sources', [])) or 'unknown'}")
    provenance = bundle.get("training_provenance", {})
    print(f"Training provenance: {describe_training_provenance(provenance)}")
    if provenance.get("is_benchmark_only"):
        print(
            "Commercial quote history support: none in this artifact. "
            "Evaluation reflects public market benchmark behavior."
        )
    print(f"Latest market history date: {latest_history_date or 'none'}")
    print(f"Holdout rows: {metrics['test_rows']}")
    print(f"Model MAE: {metrics['mae']}")
    print(f"Model RMSE: {metrics['rmse']}")
    print(f"Model MAPE: {metrics['mape_pct']}%")
    print(f"Interval coverage: {metrics['interval_coverage_pct']}%")
    print(f"Naive baseline MAE: {metrics['baseline_mae']}")
    print(f"Naive baseline MAPE: {metrics['baseline_mape_pct']}%")
    print(f"MAE improvement vs baseline: {metrics['mae_improvement_vs_baseline_pct']}%")

    if recent_windows:
        print("\nRecent validated windows:")
        for window in recent_windows:
            print(
                f"  Last {window['days']} days ({window['start_date']} to {window['end_date']}): "
                f"rows={window['rows']}, "
                f"MAE={window['mae']}, "
                f"MAPE={window['mape_pct']}%, "
                f"baseline_MAE={window['baseline_mae']}, "
                f"baseline_MAPE={window['baseline_mape_pct']}%, "
                f"MAE_vs_baseline={window['mae_improvement_vs_baseline_pct']}%"
            )

    if latest_forecast_window is None:
        print("Latest forecast window: none stored for this model version")
    else:
        print(
            "Latest stored forecast window: "
            f"{latest_forecast_window['forecast_date']} -> "
            f"{latest_forecast_window['min_departure_window_start']} to "
            f"{latest_forecast_window['max_departure_window_start']} "
            f"({latest_forecast_window['row_count']} rows)"
        )
        if latest_history_date is None:
            print("Real-time validation status: no market history available.")
        else:
            can_validate = pd.Timestamp(latest_history_date) >= pd.Timestamp(
                latest_forecast_window["max_departure_window_start"]
            )
            if can_validate:
                print("Real-time validation status: actual benchmark data is available for the latest forecast window.")
            else:
                lag_days = (
                    pd.Timestamp(latest_forecast_window["min_departure_window_start"])
                    - pd.Timestamp(latest_history_date)
                ).days
                print(
                    "Real-time validation status: actual benchmark data is not available yet for the latest forecast window."
                )
                print(
                    f"Validation gap: latest actual is {latest_history_date}, while the forecast window starts {latest_forecast_window['min_departure_window_start']} ({lag_days} days later)."
                )

    print("\nPer-route holdout metrics:")
    print(route_metrics.to_string(index=False))

    if not recent_route_metrics.empty:
        print("\nPer-route metrics for the last 60 validated days:")
        print(recent_route_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
