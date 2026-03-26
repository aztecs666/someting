# Structure Documentation

## Directory Layout

```
E:\MLCollege\real data\
│
├── app/                          # Flask web application + ML serving
│   ├── __init__.py               # Empty (package marker)
│   ├── app.py                    # Flask entry point, SSE dashboard, API routes (1070 lines)
│   ├── stream_engine.py          # Live tick generator, XGBoost predictor, SSE broadcast (658 lines)
│   ├── forecast_support.py       # Core forecasting library: importers, training, prediction, weather (1334+ lines)
│   ├── forecast_routes.py        # CLI entry point for route forecasting (111 lines)
│   ├── real_time_predictor.py    # Observable snapshot predictor (235 lines)
│   ├── compare_external_benchmark.py  # Compare forecasts vs external providers (55 lines)
│   ├── route_forecaster.joblib   # Trained GradientBoosting forecaster bundle
│   ├── route_forecaster_metrics.json  # Forecaster evaluation metrics
│   ├── route_forecast_training_dataset.csv  # Exported training data
│   ├── route_forecast_future_dataset.csv    # Exported future forecast features
│   └── shipments.db              # SQLite database (duplicate for legacy access)
│
├── data/                         # Data acquisition layer
│   ├── __init__.py               # Empty (package marker)
│   ├── real_data_fetcher.py      # Open-Meteo weather/marine fetcher, SQLite schema manager (869 lines)
│   ├── fetch_fred_data.py        # FRED freight index downloader (83 lines)
│   ├── import_quotes.py          # CSV quote history importer CLI (27 lines)
│   └── shipments.db              # Primary SQLite database (all tables)
│
├── ml/                           # Model training and evaluation
│   ├── __init__.py               # Empty (package marker)
│   ├── train_model.py            # XGBoost benchmark model training (285 lines)
│   ├── train_route_forecaster.py # GradientBoosting route forecaster training (45 lines)
│   ├── evaluate_route_forecaster.py  # Holdout evaluation + window metrics (333 lines)
│   ├── model_health_check.py     # Model diagnostics
│   ├── benchmark_model.joblib    # Trained XGBoost model (for streaming)
│   ├── benchmark_features.joblib # Feature list for XGBoost model
│   └── training_reference_profile.json  # Training ranges for drift detection
│
├── pipeline/                     # Feature engineering and dataset construction
│   ├── __init__.py               # Empty (package marker)
│   ├── real_data_pipeline.py     # Orchestrator: fetch → predict → forecast (101 lines)
│   ├── real_data_feature_engineering.py  # Feature engineering for observations (172 lines)
│   ├── build_train_data.py       # XGBoost training dataset builder with quantitative features (269 lines)
│   ├── build_forecast_dataset.py # CLI to build train or future forecast CSVs (50 lines)
│   └── benchmark_manager.py      # FRED data loading, CSV import, benchmark queries (285 lines)
│
├── scripts/                      # CLI entry points (thin wrappers)
│   ├── __init__.py               # Empty (package marker)
│   ├── real_data_audit.py        # Delegates to utils.real_data_audit
│   ├── train_route_forecaster.py # Delegates to ml.train_route_forecaster
│   ├── import_quotes.py          # Delegates to data.import_quotes
│   ├── sync_public_benchmarks.py # Syncs Compass/Xeneta benchmarks
│   ├── build_forecast_dataset.py # Delegates to pipeline.build_forecast_dataset
│   ├── evaluate_route_forecaster.py  # Delegates to ml.evaluate_route_forecaster
│   ├── compare_external_benchmark.py # Delegates to app.compare_external_benchmark
│   ├── forecast_routes.py        # Delegates to app.forecast_routes
│   ├── dump_code.py              # Dumps all source files to all_programs.txt
│   └── fix_paths.py              # One-time migration script (path restructuring)
│
├── utils/                        # Utilities
│   ├── __init__.py               # Empty (package marker)
│   └── real_data_audit.py        # Data quality audit: drift, duplicates, predictions (241 lines)
│
├── skills/                       # Skill packs (reference documentation)
│   └── senior-data-scientist/
│       ├── SKILL.md              # Senior data scientist skill definition
│       ├── references/
│       │   ├── statistical_methods_advanced.md
│       │   ├── experiment_design_frameworks.md
│       │   └── feature_engineering_patterns.md
│       └── scripts/
│           ├── experiment_designer.py
│           ├── feature_engineering_pipeline.py
│           └── model_evaluation_suite.py
│
├── documentation_records/        # Documentation and notes
├── notepad/                      # Scratch notes
├── logs/                         # Application logs
├── real data/                    # Nested directory (legacy or misc)
├── .planning/                    # Planning documents (generated)
│   └── codebase/
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
├── requirements.txt              # Python dependencies (7 packages)
├── temp_output.txt               # Temporary output file
└── .gitignore                    # Git ignore rules
```

## Key Locations

| What | Where |
|------|-------|
| **Database** | `data/shipments.db` (primary), `app/shipments.db` (duplicate) |
| **XGBoost model** | `ml/benchmark_model.joblib` |
| **XGBoost features** | `ml/benchmark_features.joblib` |
| **Route forecaster model** | `app/route_forecaster.joblib` |
| **Route forecaster metrics** | `app/route_forecaster_metrics.json` |
| **Training profile** | `ml/training_reference_profile.json` |
| **Port reference data** | `data/real_data_fetcher.py:31` (PORT_DATABASE dict) |
| **Flask app entry** | `app/app.py:1067` (`if __name__ == "__main__"`) |
| **Stream engine singleton** | `app/stream_engine.py:658` (`engine = StreamEngine()`) |
| **Feature definitions (XGBoost)** | `pipeline/build_train_data.py:196` (`get_features()`) |
| **Feature definitions (Forecaster)** | `app/forecast_support.py:131-175` (NUMERIC_FEATURES, CATEGORICAL_FEATURES) |
| **Public benchmark routes** | `app/forecast_support.py:64-129` (PUBLIC_BENCHMARK_ROUTES) |
| **Default watchlist** | `data/real_data_fetcher.py:59-68` (DEFAULT_WATCHLIST) |
| **Requirements** | `requirements.txt` (flask, joblib, numpy, pandas, requests, scikit-learn, xgboost) |

## Naming Conventions

### File Naming
- **Modules**: `snake_case.py` — `real_data_fetcher.py`, `build_train_data.py`
- **No `__main__.py`** files — entry points are explicit `if __name__ == "__main__"` blocks
- **Artifacts**: `<model_name>.joblib` for serialized models, `<model_name>_features.joblib` for feature lists
- **Scripts in `scripts/`**: Thin wrappers that `import` and call `main()` from the real module

### Module/Class Naming
- **Classes**: `PascalCase` — `RealDataFetcher`, `StreamEngine`, `QuoteHistoryImporter`
- **Functions**: `snake_case` — `build_training_dataset()`, `predict_forecaster_bundle()`
- **Private functions**: `_leading_underscore` — `_baseline_cost_series()`, `_distance_nm()`
- **Constants**: `UPPER_SNAKE_CASE` — `DB_PATH`, `NUMERIC_FEATURES`, `MIN_TRAINING_ROWS`

### Import Pattern
All modules use a path-injection pattern for resolving project root:
```python
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

Inter-module imports use absolute package-style paths:
- `from data.real_data_fetcher import RealDataFetcher`
- `from pipeline.build_train_data import prepare_training_data`
- `from app.stream_engine import engine`
- `from app.forecast_support import sync_public_benchmarks`

### Database Table Naming
- **snake_case plural**: `route_observations`, `live_ticks`, `benchmark_lanes`
- **Staging tables**: `_staging` suffix — `quote_history_staging`
- **History tables**: `_history` suffix — `benchmark_history`, `market_rate_history`
