import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    print("[FAIL] Observable predictor artifact build is retired in this repository.")
    print(
        "[!] No reproducible supervised label source is defined for "
        "ml/xgb_models.joblib and ml/xgb_features.joblib."
    )
    print(
        "[!] Supported workflow: fetch route observations, then run the "
        "route forecaster backed by market benchmark history."
    )
    print(
        "[*] If you want to revive the observable predictor, define a stable "
        "training target contract first and then add a real builder here."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
