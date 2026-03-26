import sys
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import joblib
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.joblib")
FEATURES_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_features.joblib")

def run_health_check():
    print("=== MODEL HEALTH CHECK ===")
    
    # 1. Check files
    if not os.path.exists(MODEL_PATH):
        print(f"[FAIL] Model file missing: {MODEL_PATH}")
        return False
    if not os.path.exists(FEATURES_PATH):
        print(f"[FAIL] Features file missing: {FEATURES_PATH}")
        return False
    print("[OK] Model and feature dictionary files exist.")

    # 2. Load model
    try:
        model = joblib.load(MODEL_PATH)
        print("[OK] Model loaded successfully.")
    except Exception as e:
        print(f"[FAIL] Failed to load model: {e}")
        return False

    # 3. Load features
    try:
        features = joblib.load(FEATURES_PATH)
        print(f"[OK] Features loaded. Total features expected: {len(features)}")
    except Exception as e:
        print(f"[FAIL] Failed to load features: {e}")
        return False

    # 4. Feature alignment check
    try:
        expected_features = model.n_features_in_
        if expected_features == len(features):
            print(f"[OK] Feature count matches (Model expects {expected_features}, got {len(features)}).")
        else:
            print(f"[FAIL] Feature mismatch! Model expects {expected_features}, but dict has {len(features)}.")
            return False
    except AttributeError:
        print("[WARN] Model does not have `n_features_in_` attribute (older XGBoost version or different API).")

    # 5. Dummy Prediction Test
    try:
        dummy_data = np.zeros((1, len(features)))
        df_dummy = pd.DataFrame(dummy_data, columns=features)
        
        # Give some realistic values for the dummy prediction
        df_dummy["current_price"] = 2500
        df_dummy["distance_nm"] = 5000
        df_dummy["year"] = 2026
        df_dummy["month"] = 3
        df_dummy["horizon_days"] = 14
        df_dummy["price_ema_4w"] = 2400
        df_dummy["price_ema_12w"] = 2300
        
        pred_pct = model.predict(df_dummy)[0]
        pred_dollar = 2500 * (1 + pred_pct)
        print(f"[OK] Dummy prediction successful. Target: {pred_pct*100:.2f}% change -> ${pred_dollar:.2f}")
    except Exception as e:
        print(f"[FAIL] Dummy prediction failed: {e}")
        return False

    # 6. Feature Importances Check
    try:
        importances = model.feature_importances_
        if len(importances) == len(features):
            print("[OK] Feature importances retrieved successfully.")
            sorted_feats = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
            print("  Top 3 features:")
            for f, imp in sorted_feats[:3]:
                print(f"    - {f}: {imp:.4f}")
        else:
            print("[FAIL] Length of importances does not match features.")
    except Exception as e:
        print(f"[WARN] Could not retrieve feature importances: {e}")

    print("=== HEALTH CHECK PASSED ===")
    return True

if __name__ == "__main__":
    success = run_health_check()
    sys.exit(0 if success else 1)
