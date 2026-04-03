import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.forecast_support import (
    METRICS_PATH,
    TRAINING_DATASET_PATH,
    ARTIFACT_PATH,
    build_training_dataset,
    describe_training_provenance,
    save_forecaster_bundle,
    train_forecaster_bundle,
)
from ml.training_runtime_manifest import write_training_runtime_manifest

MANIFEST_PATH = os.path.join(PROJECT_ROOT, "ml", "route_forecaster_runtime_manifest.json")


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
    write_training_runtime_manifest(
        MANIFEST_PATH,
        artifact_paths={
            "forecaster_bundle": ARTIFACT_PATH,
            "metrics": METRICS_PATH,
            "training_dataset_snapshot": TRAINING_DATASET_PATH,
        },
        extra_metadata={
            "model_name": bundle.get("model_name"),
            "model_version": bundle.get("model_version"),
            "training_provenance": bundle.get("training_provenance"),
        },
    )

    print("Route forecaster trained.")
    print(f"Training dataset: {TRAINING_DATASET_PATH}")
    print(f"Metrics: {METRICS_PATH}")
    print(f"Runtime manifest: {MANIFEST_PATH}")
    if bundle.get("training_data_modes"):
        print(f"Training modes: {', '.join(bundle['training_data_modes'])}")
    if bundle.get("training_data_sources"):
        print(f"Training sources: {', '.join(bundle['training_data_sources'][:5])}")
    provenance = bundle.get("training_provenance", {})
    print(f"Training provenance: {describe_training_provenance(provenance)}")
    if provenance.get("is_benchmark_only"):
        print(
            "[!] Commercial quote_history rows were not used in this training run. "
            "This artifact is benchmark-backed, not shipper-quote-backed."
        )
    for key, value in metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
