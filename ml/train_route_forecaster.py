import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import (
    METRICS_PATH,
    TRAINING_DATASET_PATH,
    build_training_dataset,
    save_forecaster_bundle,
    train_forecaster_bundle,
)


def main():
    training_df = build_training_dataset()
    if training_df.empty:
        print(
            "No real planner training data found. Import quote history or sync/import external benchmark history first."
        )
        return

    training_df.to_csv(TRAINING_DATASET_PATH, index=False)
    try:
        bundle, metrics = train_forecaster_bundle(training_df)
    except ValueError as exc:
        print(str(exc))
        return
    save_forecaster_bundle(bundle)

    print("Route forecaster trained.")
    print(f"Training dataset: {TRAINING_DATASET_PATH}")
    print(f"Metrics: {METRICS_PATH}")
    if bundle.get("training_data_modes"):
        print(f"Training modes: {', '.join(bundle['training_data_modes'])}")
    if bundle.get("training_data_sources"):
        print(f"Training sources: {', '.join(bundle['training_data_sources'][:5])}")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
