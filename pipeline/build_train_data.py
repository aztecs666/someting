"""
Training Dataset Builder for Benchmark Forecasting
Creates supervised learning samples: predict FUTURE benchmark price given current observations

FIXES APPLIED:
- Target now predicts forward (date + horizon) instead of backward
- Added lag features (past prices) for richer context
- Added rolling statistics (moving average, volatility, momentum)
- Added synthetic data detection warning
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")


def _check_synthetic_data(conn):
    """Warn if training data appears to be synthetic."""
    try:
        sources = pd.read_sql_query(
            "SELECT DISTINCT source FROM benchmark_history LIMIT 10", conn
        )
        source_list = sources["source"].tolist()
        if all(s in ("public_index", "synthetic_seed") for s in source_list):
            warnings.warn(
                "\n[!] TRAINING DATA WARNING: All benchmark data comes from "
                "synthetic/seeded sources.\n"
                "   The model will learn artificial patterns, not real market "
                "dynamics.\n"
                "   Import real freight index data with:\n"
                "     benchmark_manager.import_csv_benchmarks('your_data.csv')\n",
                UserWarning,
                stacklevel=3,
            )
            return True
    except Exception:
        pass
    return False


def build_training_dataset(forecast_horizons=[14, 21]):
    """
    Build training samples:
    - Input: current benchmark price, route features, time features, lag features
    - Output: FUTURE benchmark price (14-21 days ahead)

    The target is constructed by looking AHEAD in the time series for each lane,
    not by shifting dates backward (which was the previous bug).
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")

    is_synthetic = _check_synthetic_data(conn)

    # Get benchmark history
    query = """
        SELECT bl.lane_id, bl.lane_name, bl.origin_port, bl.destination_port, 
               bl.container_type, bh.date, bh.price_usd
        FROM benchmark_history bh
        JOIN benchmark_lanes bl ON bh.lane_id = bl.lane_id
        ORDER BY bl.lane_id, bh.date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if len(df) == 0:
        print("[!] No benchmark data found")
        return pd.DataFrame()

    # Route distances (nautical miles)
    distances = {
        ("Singapore", "New York"): 8285,
        ("Shanghai", "Los Angeles"): 5646,
        ("Shanghai", "Long Beach"): 5500,
        ("Dubai", "Mumbai"): 1044,
        ("Rotterdam", "New York"): 3650,
        ("Singapore", "Rotterdam"): 8760,
        ("Busan", "Los Angeles"): 5600,
        ("Hong Kong", "Los Angeles"): 5800,
    }

    df["distance_nm"] = df.apply(
        lambda r: distances.get(
            (r["origin_port"], r["destination_port"]), 5000
        ),
        axis=1,
    )

    # Parse dates and extract time features
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek
    df["quarter"] = df["date"].dt.quarter
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_peak_season"] = df["month"].isin([9, 10, 11, 12, 1, 2]).astype(int)
    df["day_of_year"] = df["date"].dt.dayofyear

    # Encode container type
    df["container_type_enc"] = (df["container_type"] == "40ft").astype(int)

    # Encode route
    route_mapping = {name: i for i, name in enumerate(df["lane_name"].unique())}
    df["route_enc"] = df["lane_name"].map(route_mapping)

    training_samples = []

    for horizon in forecast_horizons:
        # For each (lane, container_type), pair each row with its FUTURE price
        for (lane, ctype), group in df.groupby(["lane_name", "container_type"]):
            group = group.sort_values("date").reset_index(drop=True)

            # Date → price lookup for this lane/container combination
            price_lookup = dict(zip(group["date"], group["price_usd"]))

            # Target: the price at (date + horizon) — looking FORWARD
            group["target_date"] = group["date"] + timedelta(days=horizon)
            group["target_price"] = group["target_date"].map(price_lookup)
            group["horizon_days"] = horizon

            # Lag features: only past prices (no look-ahead)
            group["price_lag_7d"] = group["price_usd"].shift(1)
            group["price_lag_14d"] = group["price_usd"].shift(2)
            group["price_lag_21d"] = group["price_usd"].shift(3)

            # Rolling statistics (backward-looking only)
            group["price_ma_4w"] = (
                group["price_usd"].rolling(4, min_periods=1).mean()
            )
            group["price_volatility_4w"] = (
                group["price_usd"].rolling(4, min_periods=2).std().fillna(0)
            )
            group["price_momentum"] = (
                group["price_usd"] - group["price_usd"].shift(1)
            )

            # --- NEW: Quantitative Finance Features ---
            # EMAs and MACD
            ema_4w = group["price_usd"].ewm(span=4, adjust=False).mean()
            ema_12w = group["price_usd"].ewm(span=12, adjust=False).mean()
            group["price_ema_4w"] = ema_4w
            group["price_ema_12w"] = ema_12w
            group["price_macd"] = ema_4w - ema_12w

            # RSI (14-period)
            delta = group["price_usd"].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean().fillna(0)
            ema_down = down.ewm(com=13, adjust=False).mean().fillna(0)
            
            # Use np.where to handle division by zero safely
            rs = np.where(ema_down == 0, 100, ema_up / (ema_down + 1e-9))
            rsi = np.where(ema_down == 0, 100, 100 - (100 / (1 + rs)))
            group["price_rsi_14w"] = pd.Series(rsi, index=group.index).fillna(50)

            # Rate of Change (4-week)
            group["price_roc_4w"] = group["price_usd"].pct_change(periods=4).fillna(0)

            # --- NEW: Domain Specific Features ---
            group["cost_per_nm"] = group["price_usd"] / group["distance_nm"]
            group["route_historical_premium"] = group["price_usd"] / ema_12w

            # Rename current price for clarity
            group = group.rename(columns={"price_usd": "current_price"})

            # Drop rows without a valid future target (end of series)
            valid = group.dropna(subset=["target_price"])
            if len(valid) > 0:
                valid = valid.copy()
                valid["price_change_pct"] = (
                    (valid["target_price"] - valid["current_price"])
                    / valid["current_price"]
                )
                training_samples.append(valid)

    if training_samples:
        df_train = pd.concat(training_samples, ignore_index=True)
    else:
        df_train = pd.DataFrame()

    data_label = "SYNTHETIC" if is_synthetic else "REAL"
    print(f"[OK] Built training dataset: {len(df_train)} samples ({data_label} data)")
    return df_train


def get_features():
    """Feature columns for model training."""
    return [
        "current_price",
        "distance_nm",
        "year",
        "month",
        "day_of_week",
        "quarter",
        "week_of_year",
        "is_peak_season",
        "day_of_year",
        "container_type_enc",
        "route_enc",
        "horizon_days",
        # Lag features (backward-looking only, no data leakage)
        "price_lag_7d",
        "price_lag_14d",
        "price_lag_21d",
        "price_ma_4w",
        "price_volatility_4w",
        "price_momentum",
        # Quantitative indicators
        "price_ema_4w",
        "price_ema_12w",
        "price_macd",
        "price_rsi_14w",
        "price_roc_4w",
        # Domain features
        "cost_per_nm",
        "route_historical_premium",
    ]


def prepare_training_data():
    """Main entry point to prepare training data."""
    df = build_training_dataset(forecast_horizons=[14, 21])

    if len(df) == 0:
        print("[!] No training data generated")
        return None, None, None

    features = get_features()
    X = df[features].copy()

    # TARGET: predict percentage change, NOT absolute price.
    # This is the standard in commodity/freight forecasting because:
    # 1) Absolute prices vary wildly across lanes ($280 Dubai-Mumbai vs $2800 Singapore-NY)
    # 2) Predicting % moves lets one model work across all price scales
    # 3) Naive baseline for % change is 0% (no change), which is much easier to beat
    y = df["price_change_pct"].copy()

    # Fill NaN in lag features (first few rows of each group)
    X = X.fillna(0)
    y = y.fillna(0)

    return X, y, df


if __name__ == "__main__":
    X, y, df = prepare_training_data()
    if df is not None:
        print("\n=== Training Data Sample ===")
        sample_cols = [
            "lane_name", "date", "current_price",
            "target_date", "target_price", "horizon_days",
        ]
        print(df[sample_cols].head(10))
        print(f"\nFeatures: {get_features()}")
        print(f"\nShape: {X.shape}")

        # Sanity check: all targets are in the future
        future_ok = (df["target_date"] > df["date"]).all()
        print(f"\n{'[OK]' if future_ok else '[FAIL]'} All targets are future dates: {future_ok}")
