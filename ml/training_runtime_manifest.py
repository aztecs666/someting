import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import version


PACKAGE_NAMES = [
    "flask",
    "joblib",
    "numpy",
    "pandas",
    "requests",
    "scikit-learn",
    "xgboost",
]


def _package_versions():
    versions = {}
    for package_name in PACKAGE_NAMES:
        try:
            versions[package_name] = version(package_name)
        except Exception:
            versions[package_name] = "unknown"
    return versions


def write_training_runtime_manifest(manifest_path, artifact_paths, extra_metadata=None):
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "artifact_paths": artifact_paths,
        "package_versions": _package_versions(),
    }
    if extra_metadata:
        payload["metadata"] = extra_metadata

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    return manifest_path
