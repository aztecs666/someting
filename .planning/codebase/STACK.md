# Technology Stack

## Languages & Runtime
- **Python 3.13** (evidenced by `__pycache__/*.cpython-313.pyc` files)
- Standard library modules: `sqlite3`, `threading`, `queue`, `json`, `math`, `argparse`, `io`, `uuid`, `shutil`, `os`, `sys`, `time`, `datetime`

## Frameworks
- **Flask** — Web dashboard with Server-Sent Events (SSE) for real-time streaming (`app/app.py:24`)
  - Routes: `/`, `/api/prices`, `/api/stats`, `/api/ticks`, `/api/accuracy`, `/api/retrain`, `/api/retrain_log`, `/stream`
  - Runs on `0.0.0.0:5001`
- **Chart.js** — Client-side charting via CDN in the dashboard HTML (`app/app.py:130`)
- **Google Fonts** — JetBrains Mono + Inter loaded via CDN (`app/app.py:129`)

## Dependencies (`requirements.txt`)
```
flask
joblib
numpy
pandas
requests
scikit-learn
xgboost
```

## ML/Data Stack
- **XGBoost** (`xgboost`) — Primary forecasting model
  - Benchmark model: `ml/benchmark_model.joblib` — Predicts % price change for lane cost forecasting
  - Configuration: n_estimators=100, max_depth=2, learning_rate=0.05, early_stopping_rounds=15 (`ml/train_model.py:99-113`)
  - Retrains weekly (Sunday midnight) via `app/stream_engine.py:626-634`
- **scikit-learn** — Route planning forecaster + preprocessing
  - `GradientBoostingRegressor` — Residual model for 14-20 day route planning forecasts (`app/forecast_support.py:994`)
  - `Pipeline`, `ColumnTransformer` — Feature preprocessing (`app/forecast_support.py:942-964`)
  - `SimpleImputer`, `OneHotEncoder` — Categorical/numeric handling (`app/forecast_support.py:949-953`)
  - `mean_absolute_error`, `mean_squared_error`, `r2_score` — Model evaluation
- **joblib** — Model serialization (`ml/benchmark_model.joblib`, `ml/benchmark_features.joblib`, `app/route_forecaster.joblib`, `ml/benchmark_model.joblib`, `ml/xgb_models.joblib`)
- **pandas** — Data manipulation throughout all modules
- **numpy** — Numerical computation, NaN handling, array operations
- **requests** — HTTP client for external API calls

## Configuration
- **No `.env` files or env templates found** — API keys are either hardcoded public keys or not required
- **Database path**: `data/shipments.db` (SQLite, relative to PROJECT_ROOT)
- **Model paths**: Hardcoded relative paths in each module
  - `ml/benchmark_model.joblib` — Main benchmark XGBoost model
  - `ml/benchmark_features.joblib` — Feature list for benchmark model
  - `ml/xgb_models.joblib` — Multi-target model bundle for observable predictor
  - `ml/xgb_features.joblib` — Feature list for observable predictor
  - `app/route_forecaster.joblib` — Route planning forecaster bundle
  - `ml/training_reference_profile.json` — Training data ranges for drift detection
- **`.opencode/settings.json`**, `.opencode/opencode.json` — OpenCode tool configuration
- **`.gitignore`** — Present at project root

## Build/Dev Tools
- **No build system** (no Makefile, pyproject.toml, setup.py, Dockerfile)
- **CLI scripts** via `argparse` in `scripts/` directory:
  - `scripts/forecast_routes.py` — Run route forecasts
  - `scripts/train_route_forecaster.py` — Train the route forecaster model
  - `scripts/evaluate_route_forecaster.py` — Evaluate forecaster performance
  - `scripts/build_forecast_dataset.py` — Build train/future datasets (`--mode train|future`)
  - `scripts/sync_public_benchmarks.py` — Sync Compass/Xeneta benchmarks
  - `scripts/import_quotes.py` — Import quote CSV data
  - `scripts/compare_external_benchmark.py` — Compare forecasts vs external benchmarks
  - `scripts/real_data_audit.py` — Audit real data quality
  - `scripts/fix_paths.py` — Path correction utility
  - `scripts/dump_code.py` — Code export utility
- **OpenCode** — AI-assisted development tool (`.opencode/` directory)
- **Skill system** — `skills/senior-data-scientist/` with evaluation and feature engineering scripts
