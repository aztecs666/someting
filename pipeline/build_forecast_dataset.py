import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import (
    FUTURE_DATASET_PATH,
    TRAINING_DATASET_PATH,
    build_future_forecast_features,
    build_training_dataset,
)


def main():
    parser = argparse.ArgumentParser(description="Build training or future forecast datasets.")
    parser.add_argument("--mode", choices=["train", "future"], default="train")
    parser.add_argument("--output")
    parser.add_argument("--day-start", type=int, default=14)
    parser.add_argument("--day-end", type=int, default=20)
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    if args.mode == "train":
        df = build_training_dataset(db_path=args.db_path) if args.db_path else build_training_dataset()
        output_path = args.output or TRAINING_DATASET_PATH
    else:
        df = (
            build_future_forecast_features(
                day_start=args.day_start,
                day_end=args.day_end,
                db_path=args.db_path,
            )
            if args.db_path
            else build_future_forecast_features(day_start=args.day_start, day_end=args.day_end)
        )
        output_path = args.output or FUTURE_DATASET_PATH

    if df.empty:
        print("No rows available for this dataset.")
        return

    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


if __name__ == "__main__":
    main()
