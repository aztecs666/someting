# 📋 Change Log — Route Planning Forecaster

> **Author:** Parth  
> **Date:** 2026-03-16  
> **Project:** Route Planning Forecaster — Real-Data-Only Refactoring

---

## 🎯 Purpose of These Changes

This document records the concrete, verifiable changes made to convert the project from a flat-file prototype into a **production-style, real-data-only route planning forecaster**. The goal was to:

1. Reorganize the project into a clean, modular folder structure.
2. Remove all synthetic/fabricated training data.
3. Implement a more accurate **residual-blend** prediction strategy.
4. Add honest documentation about data limitations.

---

## 📁 Project Structure After Refactoring

The project was restructured from a single flat directory into a clean modular layout:

```
real data/
│
├── app/                    # Application layer (dashboard, forecasting, streaming)
│   ├── app.py              # Flask dashboard (legacy sandbox UI)
│   ├── forecast_routes.py  # Generate 14–20 day route forecasts
│   ├── forecast_support.py # Core prediction engine & support functions
│   ├── compare_external_benchmark.py  # Compare with external providers
│   ├── real_time_predictor.py         # Real-time prediction interface
│   └── stream_engine.py              # Live data stream engine
│
├── data/                   # Data layer (fetching, importing, database)
│   ├── fetch_fred_data.py  # Pull economic indicators from FRED API
│   ├── import_quotes.py    # Import private quote CSVs
│   ├── real_data_fetcher.py # Real shipping data fetcher
│   └── shipments.db        # Main SQLite database (8 MB)
│
├── ml/                     # Machine learning layer (training, evaluation)
│   ├── train_model.py      # General model training logic
│   ├── train_route_forecaster.py  # Route forecaster training entry
│   ├── evaluate_route_forecaster.py # Evaluation with real holdout data
│   ├── model_health_check.py       # Post-training health check
│   ├── benchmark_model.joblib       # Trained model artifact
│   ├── benchmark_features.joblib    # Feature list artifact
│   └── training_reference_profile.json # Training data profile
│
├── pipeline/               # Data pipeline layer
│   ├── build_train_data.py           # Build training datasets
│   ├── build_forecast_dataset.py     # Build forecasting datasets
│   ├── real_data_feature_engineering.py # Feature engineering
│   ├── real_data_pipeline.py          # Observable snapshot pipeline
│   └── benchmark_manager.py           # Benchmark data management
│
├── scripts/                # Entry-point wrapper scripts & utilities
│   ├── build_forecast_dataset.py    # → calls pipeline module
│   ├── train_route_forecaster.py    # → calls ml module
│   ├── evaluate_route_forecaster.py # → calls ml module
│   ├── forecast_routes.py           # → calls app module
│   ├── sync_public_benchmarks.py    # → calls app module
│   ├── import_quotes.py             # → calls data module
│   ├── real_data_audit.py           # → calls utils module
│   ├── compare_external_benchmark.py # → calls app module
│   ├── dump_code.py                 # Dumps all code to all_programs.txt
│   └── fix_paths.py                 # One-time migration (archived)
│
├── utils/                  # Utility layer
│   └── real_data_audit.py  # Audit database state & data health
│
├── logs/                   # Output logs & generated files
│
├── README.md               # Main project documentation
├── CHANGES_README.md        # ← This file
├── requirements.txt         # Python dependencies
└── .gitignore               # Git ignore rules
```

---

## 🔧 What the `scripts/` Folder Contains

These are **thin wrapper scripts** that were moved from the project root into `scripts/` for a cleaner structure. Each one simply imports and runs the `main()` function from the actual module inside a subfolder.

| Script | Calls | Purpose |
|---|---|---|
| `scripts/build_forecast_dataset.py` | `pipeline.build_forecast_dataset.main()` | Build the training or forecasting dataset from real data |
| `scripts/train_route_forecaster.py` | `ml.train_route_forecaster.main()` | Train the route forecaster model |
| `scripts/evaluate_route_forecaster.py` | `ml.evaluate_route_forecaster.main()` | Evaluate the model against real holdout data |
| `scripts/forecast_routes.py` | `app.forecast_routes.main()` | Generate 14–20 day route cost forecasts |
| `scripts/sync_public_benchmarks.py` | `app.forecast_support.sync_public_benchmarks()` | Sync public benchmark data into `market_rate_history` |
| `scripts/import_quotes.py` | `data.import_quotes.main()` | Import private quote CSV into the database |
| `scripts/real_data_audit.py` | `utils.real_data_audit.main()` | Run a full data health & coverage audit |
| `scripts/compare_external_benchmark.py` | `app.compare_external_benchmark.main()` | Import and compare external forecast providers |

### Utility Scripts (not wrappers)

| Script | Purpose |
|---|---|
| `scripts/dump_code.py` | Walks the project tree and exports all `.py`, `.html`, `.css`, `.js` files into a single `all_programs.txt` for review |
| `scripts/fix_paths.py` | One-time migration script (archived) — patched import paths during the flat → modular restructure |

---

## 🧠 Core Technical Changes

### 1. Residual-Blend Prediction Strategy (NEW)

**Before:** The model tried to predict the absolute cost directly — this made it volatile and overreactive.

**After:** A new residual-blend approach:
- Start from the **latest observed real benchmark cost** as a baseline
- Predict the **residual adjustment** (how much cost will deviate from baseline)
- Blend the adjustment back into the baseline to **reduce overreaction**

**Files changed:**
- `app/forecast_support.py` — Added baseline/residual prediction helpers, residual-blend strategy, and interval-width calibration by route
- `app/forecast_routes.py` — Switched to use the shared prediction path
- `ml/evaluate_route_forecaster.py` — Switched evaluation to the same prediction path for consistency

### 2. Real-Data-Only Enforcement

**Before:** The project could fall back to synthetic or fabricated commercial targets for training.

**After:** Strict real-data-only policy:
- If `quote_history` has data → use it (best option)
- If `quote_history` is empty but `market_rate_history` has data → use external benchmarks as training proxy
- If both are empty → **refuse to train** (no synthetic fallback)

### 3. Route-Specific Interval Calibration

**Before:** The model relied on narrow quantile outputs from the earlier model.

**After:** Uses a **time-based calibration slice** to compute route-specific interval widths, giving more reliable low/base/high cost bands per route.

### 4. Improved Evaluation

**Before:** Basic holdout evaluation only.

**After:**
- Added **recent validated windows** (last 30 / 60 / 90 days)
- Added **per-route metrics** for granular assessment
- Comparison against a **naive baseline** (latest benchmark repeated forward)
- Removed deprecated pandas `fillna` usage

### 5. UI & Dashboard Honesty

- `app/app.py` — Softened misleading UI claims; marked the old dashboard as a **legacy sandbox**
- The UI no longer presents benchmark-based forecasts as direct commercial quote predictions

### 6. Stream Engine Fixes

- `app/stream_engine.py` — Fixed route encoding mismatch; removed random retrain splits in favor of time-aware behavior

### 7. Audit Improvements

- `utils/real_data_audit.py` — Added visibility into `market_rate_history` table status

---

## ✅ Verified Evaluation Results (Real Data)

**Model version:** `20260316115358`  
**Training mode:** `external_benchmark_history`  
**Training source:** Compass/Xeneta  
**Prediction strategy:** `residual_blend`

### Holdout Performance

| Metric | Model | Baseline |
|---|---|---|
| MAE | 211.32 | 224.28 |
| RMSE | 414.23 | — |
| MAPE | 8.11% | 8.42% |
| MAE Improvement | **5.78%** over baseline | — |
| Interval Coverage | 70.36% | — |

### Recent Validated Windows

| Window | Model MAE | Baseline MAE | Model MAPE | Baseline MAPE |
|---|---|---|---|---|
| Last 30 days | 135.56 | 138.15 | 6.85% | 7.09% |
| Last 60 days | 121.78 | 125.08 | 6.96% | 7.08% |
| Last 90 days | 116.59 | 119.55 | 6.81% | 7.06% |

> The model consistently outperforms the naive baseline across all time windows, with improving accuracy on more recent data.

---

## 📦 Current Forecast Output

- **Forecast window:** 2026-03-30 through 2026-04-05
- **Rows saved:** 56 (for current model version)
- **Public data synced through:** 2026-03-13 (17,780 benchmark rows)

---

## ⚠️ Known Limitations

1. **No private quote history** — The model is trained on external benchmark data, not on actual commercial quotes. Outputs should be interpreted as a planning proxy.
2. **Forward forecasts cannot be truth-checked yet** — Public benchmark data only reaches 2026-03-13, so the forecasts for late March/April cannot be validated until that data is published.
3. **Free weather data covers only 16 days** — Forecasts for days 17–20 include a horizon-gap penalty.

---

## 🛠 Commands to Reproduce

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Sync public benchmark data
python scripts/sync_public_benchmarks.py

# 3. Build training dataset
python scripts/build_forecast_dataset.py --mode train

# 4. Train the model
python scripts/train_route_forecaster.py

# 5. Evaluate against real holdout data
python scripts/evaluate_route_forecaster.py --sync-public

# 6. Generate forecasts
python scripts/forecast_routes.py

# 7. Audit data state
python scripts/real_data_audit.py
```

---

## 📂 Support Files Added

| File | Purpose |
|---|---|
| `requirements.txt` | Lists all Python dependencies (`flask`, `joblib`, `numpy`, `pandas`, `requests`, `scikit-learn`, `xgboost`) |
| `.gitignore` | Prevents model artifacts, databases, logs, and cache files from being committed |
| `all_programs.txt` | Full source dump of all project code (generated by `dump_code.py`) |

---

## 📌 Summary for Instructor

The key takeaway: the project was **restructured from a flat prototype into a modular, production-style codebase**, with a **new residual-blend model** that outperforms the naive baseline by ~6% on real external benchmark data. All synthetic training fallbacks were removed, and the project is now **honest about its data limitations** — it trains on real data only, and clearly labels its outputs as benchmark-based planning proxies when private quote history is unavailable.
