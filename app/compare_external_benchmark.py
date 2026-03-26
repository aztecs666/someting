import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import (
    ExternalBenchmarkImporter,
    compare_latest_forecasts_to_benchmarks,
)


def main():
    parser = argparse.ArgumentParser(
        description="Import external benchmark CSVs and compare them to route forecasts."
    )
    parser.add_argument("--import-csv")
    parser.add_argument("--provider")
    args = parser.parse_args()

    if args.import_csv:
        importer = ExternalBenchmarkImporter()
        result = importer.import_csv(args.import_csv, provider_override=args.provider)
        print("Benchmark import complete:")
        for key, value in result.items():
            print(f"  {key}: {value}")

    comparison = compare_latest_forecasts_to_benchmarks(provider=args.provider)
    if comparison.empty:
        print("No matching external benchmark rows found for the latest forecasts.")
        return

    print("\nForecast vs external benchmark:")
    cols = [
        "forecast_date",
        "departure_window_start",
        "route_name",
        "container_type",
        "expected_low_cost",
        "expected_base_cost",
        "expected_high_cost",
        "predicted_cost",
        "absolute_delta",
        "percentage_delta",
        "rank_by_cost",
        "provider_rank",
        "ranking_agreement_score",
    ]
    print(comparison[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
