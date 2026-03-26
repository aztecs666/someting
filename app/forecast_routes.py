import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

from app.forecast_support import (
    ARTIFACT_PATH,
    FUTURE_DATASET_PATH,
    build_future_forecast_features,
    estimate_confidence_score,
    estimate_weather_cost_uplift,
    estimate_weather_delay_days,
    load_forecaster_bundle,
    persist_route_forecasts,
    predict_forecaster_bundle,
)


def main():
    if not os.path.exists(ARTIFACT_PATH):
        print("No route forecaster artifact found. Run train_route_forecaster.py first.")
        return

    bundle = load_forecaster_bundle()
    future_df = build_future_forecast_features(day_start=14, day_end=20)
    if future_df.empty:
        print("No future forecast rows available. Import quote history first.")
        return

    future_df.to_csv(FUTURE_DATASET_PATH, index=False)
    market_baseline, low_market, high_market = predict_forecaster_bundle(bundle, future_df)

    future_df["market_baseline_cost"] = market_baseline
    future_df["weather_cost_uplift"] = future_df.apply(
        lambda row: estimate_weather_cost_uplift(
            row["market_baseline_cost"], row.to_dict()
        ),
        axis=1,
    )
    future_df["expected_delay_days"] = future_df.apply(
        lambda row: estimate_weather_delay_days(row.to_dict()), axis=1
    )
    future_df["severe_weather_probability"] = future_df[
        "forecast_severe_weather_probability"
    ].fillna(0.0)
    future_df["expected_base_cost"] = (
        future_df["market_baseline_cost"] + future_df["weather_cost_uplift"]
    )
    future_df["expected_low_cost"] = np.minimum(
        low_market + future_df["weather_cost_uplift"] * 0.5,
        future_df["expected_base_cost"],
    )
    future_df["expected_high_cost"] = np.maximum(
        high_market + future_df["weather_cost_uplift"] * 1.25,
        future_df["expected_base_cost"],
    )
    future_df["data_coverage_pct"] = (
        future_df["lane_history_coverage_pct"] * 0.6
        + future_df["forecast_weather_data_coverage_pct"].fillna(0.0) * 0.4
    )
    future_df["confidence_score"] = future_df.apply(
        lambda row: estimate_confidence_score(row.to_dict()), axis=1
    )

    future_df["rank_by_cost"] = (
        future_df.groupby("departure_window_start")["expected_base_cost"]
        .rank(method="dense", ascending=True)
        .astype(int)
    )
    future_df["risk_score"] = (
        future_df["expected_high_cost"] + future_df["expected_delay_days"] * 500.0
    )
    future_df["rank_by_risk"] = (
        future_df.groupby("departure_window_start")["risk_score"]
        .rank(method="dense", ascending=True)
        .astype(int)
    )

    inserted = persist_route_forecasts(future_df, bundle)
    print(f"Saved {inserted} forecast rows.")

    view_cols = [
        "departure_window_start",
        "route_name",
        "container_type",
        "expected_low_cost",
        "expected_base_cost",
        "expected_high_cost",
        "weather_cost_uplift",
        "expected_delay_days",
        "severe_weather_probability",
        "confidence_score",
        "rank_by_cost",
    ]
    print("\nRoute forecast table:")
    print(future_df[view_cols].round(2).to_string(index=False))

    best_rows = (
        future_df.sort_values(["departure_window_start", "rank_by_cost"])
        .groupby("departure_window_start", as_index=False)
        .head(1)
    )
    print("\nBest route per departure day:")
    print(best_rows[view_cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
