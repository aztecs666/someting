"""
Train the Benchmark Forecasting Model
Uses XGBoost to predict future lane costs

FIXES APPLIED:
- Temporal (chronological) train/test split instead of random
- Naive baseline comparison (predict no change)
- Data quality warnings
- Feature importance visualization
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

from pipeline.build_train_data import prepare_training_data, get_features
from ml.training_runtime_manifest import write_training_runtime_manifest

MODEL_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(MODEL_DIR, "benchmark_model.joblib")
FEATURES_PATH = os.path.join(MODEL_DIR, "benchmark_features.joblib")
MANIFEST_PATH = os.path.join(MODEL_DIR, "benchmark_model_runtime_manifest.json")


def _temporal_split(X, y, df, test_ratio=0.2):
    """
    Split data chronologically — train on earlier dates, test on later dates.
    This prevents future data from leaking into the training set.
    """
    if "date" in df.columns:
        sorted_idx = df["date"].sort_values().index
        X_sorted = X.loc[sorted_idx].reset_index(drop=True)
        y_sorted = y.loc[sorted_idx].reset_index(drop=True)
    else:
        X_sorted = X.reset_index(drop=True)
        y_sorted = y.reset_index(drop=True)

    split_point = int(len(X_sorted) * (1 - test_ratio))

    X_train = X_sorted.iloc[:split_point]
    X_test = X_sorted.iloc[split_point:]
    y_train = y_sorted.iloc[:split_point]
    y_test = y_sorted.iloc[split_point:]

    return X_train, X_test, y_train, y_test


def _naive_baseline(X_test, y_test):
    """
    Naive baseline: predict 0% change (price stays the same).
    Since y is now price_change_pct, any useful model must predict
    the direction and magnitude of % moves better than just guessing 0.
    """
    naive_pred = np.zeros(len(y_test))  # predict no change
    naive_mae = mean_absolute_error(y_test, naive_pred)
    naive_rmse = np.sqrt(mean_squared_error(y_test, naive_pred))
    naive_r2 = r2_score(y_test, naive_pred)
    return naive_mae, naive_rmse, naive_r2


def train_model():
    print("=" * 60)
    print("  BENCHMARK FORECASTING MODEL — TRAINING")
    print("=" * 60)

    print("\n=== Building Training Data ===")
    X, y, df = prepare_training_data()

    if X is None or len(X) == 0:
        print("[!] No training data available")
        return None

    # ── Temporal split (NOT random) ──────────────────────────────
    X_train, X_test, y_train, y_test = _temporal_split(X, y, df, test_ratio=0.2)

    print(f"Training samples: {len(X_train)} (earlier dates)")
    print(f"Test samples:     {len(X_test)} (later dates)")
    if "date" in df.columns:
        dates_sorted = df["date"].sort_values()
        split_idx = int(len(dates_sorted) * 0.8)
        split_date = dates_sorted.iloc[split_idx]
        print(f"Split at:         {split_date.strftime('%Y-%m-%d')}")

    # ── Naive baseline ───────────────────────────────────────────
    naive_mae, naive_rmse, naive_r2 = _naive_baseline(X_test, y_test)
    if naive_mae is not None:
        print(f"\n=== Naive Baseline (predict price stays the same) ===")
        print(f"Baseline MAE:  ${naive_mae:.2f}")
        print(f"Baseline RMSE: ${naive_rmse:.2f}")
        print(f"Baseline R2:   {naive_r2:.4f}")

    # -- Train XGBoost (regularized to prevent overfitting) --------
    print("\n=== Training XGBoost Model ===")
    model = xgb.XGBRegressor(
        n_estimators=100,        # significantly reduced to avoid overfitting
        max_depth=2,             # shallower bounds logic
        learning_rate=0.05,      # optimal balance
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=20,     # stronger regularization for broader splits
        gamma=0.2,               # minimum loss reduction for split
        reg_alpha=1.0,           # L1 regularization
        reg_lambda=2.0,          # L2 regularization
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=15,
        eval_metric="mae",       # set the evaluation metric contextually
    )

    # Use a simpler validation split for the early stopping
    X_train_sub, X_val, y_train_sub, y_val = _temporal_split(X_train, y_train, df.iloc[:len(X_train)], test_ratio=0.1)

    model.fit(
        X_train_sub, y_train_sub,
        eval_set=[(X_train_sub, y_train_sub), (X_val, y_val)],
        verbose=False,
    )

    # -- Evaluate --------------------------------------------------
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_r2 = r2_score(y_test, y_pred_test)

    print(f"\n=== Model Performance (% Change Target) ===")
    print(f"Train MAE:  {mean_absolute_error(y_train, y_pred_train)*100:.2f}%")
    print(f"Test MAE:   {test_mae*100:.2f}%")
    print(f"Test RMSE:  {test_rmse*100:.2f}%")
    print(f"Test R2:    {test_r2:.4f}")

    # Convert to dollar MAE for business interpretation
    if "current_price" in X_test.columns:
        actual_future = X_test["current_price"].values * (1 + y_test.values)
        predicted_future = X_test["current_price"].values * (1 + y_pred_test)
        dollar_mae = mean_absolute_error(actual_future, predicted_future)
        naive_dollar_mae = mean_absolute_error(actual_future, X_test["current_price"].values)
        print(f"\n=== Dollar Equivalent ===")
        print(f"Model Dollar MAE:    ${dollar_mae:.2f}")
        print(f"Naive Dollar MAE:    ${naive_dollar_mae:.2f}")

    # Directional accuracy: how often model correctly predicts up vs down
    correct_direction = np.sign(y_pred_test) == np.sign(y_test.values)
    # Exclude cases where actual change is ~0
    nontrivial = np.abs(y_test.values) > 0.001
    if nontrivial.sum() > 0:
        dir_acc = correct_direction[nontrivial].mean() * 100
        print(f"Directional Accuracy: {dir_acc:.1f}% (of non-trivial moves)")

    # -- Model vs Baseline -----------------------------------------
    if naive_mae is not None and naive_mae > 0:
        mae_improvement = ((naive_mae - test_mae) / naive_mae) * 100
        print(f"\n=== Model vs Naive Baseline ===")
        if mae_improvement > 0:
            print(f"[+] Model beats baseline by {mae_improvement:.1f}% (MAE reduction)")
            print(f"  Baseline MAE: {naive_mae*100:.2f}% -> Model MAE: {test_mae*100:.2f}%")
        else:
            print(f"[-] Model is WORSE than baseline by {abs(mae_improvement):.1f}%")
            print(f"  Consider adding external signals (oil prices, congestion indices).")

    # ── Feature importance ───────────────────────────────────────
    print(f"\n=== Feature Importance (top 10) ===")
    features = get_features()
    importance = model.feature_importances_
    sorted_feats = sorted(zip(features, importance), key=lambda x: -x[1])
    for feat, imp in sorted_feats[:10]:
        bar = "#" * int(imp * 50)
        print(f"  {feat:25s} {imp:.4f} {bar}")

    # Check if current_price dominates (sign of shortcut)
    top_feat, top_imp = sorted_feats[0]
    if top_feat == "current_price" and top_imp > 0.8:
        print(f"\n  WARNING: 'current_price' dominates at {top_imp:.1%}.")
        print(f"     The model may just be echoing the input price.")
        print(f"     This often happens with synthetic/smooth data.")

    # ── Save ─────────────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    joblib.dump(features, FEATURES_PATH)
    write_training_runtime_manifest(
        MANIFEST_PATH,
        artifact_paths={
            "benchmark_model": MODEL_PATH,
            "benchmark_features": FEATURES_PATH,
        },
        extra_metadata={
            "model_name": "benchmark_forecasting_model",
            "target": "price_change_pct",
            "training_rows": int(len(X)),
        },
    )
    print(f"\n[OK] Model saved to {MODEL_PATH}")
    print(f"[OK] Features saved to {FEATURES_PATH}")
    print(f"[OK] Runtime manifest saved to {MANIFEST_PATH}")

    return model


def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None


def predict_future_price(
    current_price,
    distance_nm,
    month,
    day_of_week,
    quarter,
    week_of_year,
    is_peak_season,
    day_of_year,
    container_type_enc,
    route_enc,
    horizon_days,
    price_lag_7d=None,
    price_lag_14d=None,
    price_lag_21d=None,
    price_ma_4w=None,
    price_volatility_4w=0,
    price_momentum=0,
    price_ema_4w=None,
    price_ema_12w=None,
    price_macd=0,
    price_rsi_14w=50,
    price_roc_4w=0,
    cost_per_nm=None,
    route_historical_premium=1.0,
):
    """Make a prediction for future price."""
    model = load_model()
    if model is None:
        return None

    # Default lags to current price if not provided
    if price_lag_7d is None:
        price_lag_7d = current_price
    if price_lag_14d is None:
        price_lag_14d = current_price
    if price_lag_21d is None:
        price_lag_21d = current_price
    if price_ma_4w is None:
        price_ma_4w = current_price
    if price_ema_4w is None:
        price_ema_4w = current_price
    if price_ema_12w is None:
        price_ema_12w = current_price
    if cost_per_nm is None:
        cost_per_nm = current_price / distance_nm if distance_nm else 0


    features = get_features()
    X = pd.DataFrame(
        [
            [
                current_price,
                distance_nm,
                2026,
                month,
                day_of_week,
                quarter,
                week_of_year,
                is_peak_season,
                day_of_year,
                container_type_enc,
                route_enc,
                horizon_days,
                price_lag_7d,
                price_lag_14d,
                price_lag_21d,
                price_ma_4w,
                price_volatility_4w,
                price_momentum,
                price_ema_4w,
                price_ema_12w,
                price_macd,
                price_rsi_14w,
                price_roc_4w,
                cost_per_nm,
                route_historical_premium,
            ]
        ],
        columns=features,
    )
    # Model predicts % change — convert back to dollar forecast
    pct_change = model.predict(X)[0]
    return current_price * (1 + pct_change)


if __name__ == "__main__":
    train_model()
