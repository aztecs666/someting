"""
Observable real-data pipeline.

Flow:
1. Fetch monitored route observations from public APIs
2. Store only observed fields plus transparent derived values
3. Run the legacy observable snapshot predictor
4. Run the 14-20 day route planning forecaster when a trained bundle exists
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import time

from app.forecast_routes import main as run_route_forecasts
from app.forecast_support import ARTIFACT_PATH
from data.real_data_fetcher import RealDataFetcher
from app.real_time_predictor import RealTimePredictor


class RealDataPipeline:
    def __init__(self):
        self.fetcher = RealDataFetcher()
        self.predictor = RealTimePredictor()

    def run_once(self, route_limit=50):
        observations = self.fetcher.fetch_watchlist_observations()
        predictions = None
        predictor_status = self.predictor.readiness_message()
        if self.predictor.is_ready():
            predictions = self.predictor.run_predictions(limit=route_limit, persist=True)
            if predictions is not None and not predictions.empty:
                predictor_status = (
                    f"Observable predictor executed for {len(predictions)} observations."
                )
            else:
                predictor_status = "Observable predictor ran but returned no rows."
        forecast_status = "Route forecaster not trained yet."
        if os.path.exists(ARTIFACT_PATH):
            run_route_forecasts()
            forecast_status = "Route forecaster executed."
        return observations, predictions, predictor_status, forecast_status

    def start_scheduled(self, interval_minutes=30):
        try:
            while True:
                observations, predictions, predictor_status, forecast_status = self.run_once()
                print("\nLatest observations:")
                print(observations.to_string(index=False))
                if predictions is not None and not predictions.empty:
                    print("\nLatest predictions:")
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
                    print(predictions[cols].round(2).to_string(index=False))
                print(f"\n{predictor_status}")
                print(f"\n{forecast_status}")
                print(f"\nSleeping for {interval_minutes} minutes...\n")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("Pipeline stopped.")


def main():
    pipeline = RealDataPipeline()
    observations, predictions, predictor_status, forecast_status = pipeline.run_once()

    print("Observations fetched:")
    print(observations.to_string(index=False))
    if predictions is not None and not predictions.empty:
        print("\nPredictions:")
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
            "drift_feature_count",
        ]
        print(predictions[cols].round(2).to_string(index=False))
    print(f"\n{predictor_status}")
    print(f"\n{forecast_status}")


if __name__ == "__main__":
    main()
