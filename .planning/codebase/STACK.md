# Technology Stack

**Analysis Date:** 2026-03-26

## Languages

**Primary:**
- Python (version not pinned in repo) - Application, data ingestion, ML training, forecasting, and CLI tooling across `app/`, `data/`, `pipeline/`, `ml/`, `utils/`, and `scripts/`

**Secondary:**
- SQL (SQLite dialect) - Table creation and queries embedded in `data/real_data_fetcher.py`, `pipeline/benchmark_manager.py`, `app/stream_engine.py`, `app/forecast_support.py`, and `utils/real_data_audit.py`
- JSON and CSV data formats - Model metadata, datasets, and interchange files in `ml/training_reference_profile.json`, `app/route_forecaster_metrics.json`, `app/route_forecast_training_dataset.csv`, and importer/exporter flows in `app/forecast_support.py`

## Runtime

**Environment:**
- CPython via direct `python` execution; repo runtime version is not pinned in `E:\MLCollege\real data`
- Long-running local process support is required for the Flask dashboard in `app/app.py` and the polling loop in `pipeline/real_data_pipeline.py`

**Package Manager:**
- `pip` with dependency installation from `requirements.txt`
- Lockfile: missing

## Frameworks

**Core:**
- Flask (version not pinned) - Local web server and JSON/SSE endpoints in `app/app.py`
- pandas (version not pinned) - Data ingestion, SQL reads, CSV reads/writes, and feature assembly across `data/`, `pipeline/`, `app/`, and `ml/`
- NumPy (version not pinned) - Numerical transforms and metrics across `app/forecast_support.py`, `data/real_data_fetcher.py`, `pipeline/benchmark_manager.py`, and `ml/train_model.py`

**Testing:**
- Not detected - no `pytest`, `unittest`, `nose`, `tox`, or test files were found under `E:\MLCollege\real data`

**Build/Dev:**
- `argparse`-driven CLI entry points in `data/import_quotes.py`, `pipeline/build_forecast_dataset.py`, `ml/evaluate_route_forecaster.py`, and `app/compare_external_benchmark.py`
- Direct script wrappers in `scripts/` such as `scripts/train_route_forecaster.py`, `scripts/sync_public_benchmarks.py`, `scripts/forecast_routes.py`, and `scripts/real_data_audit.py`
- Joblib artifact serialization in `ml/train_model.py`, `app/forecast_support.py`, `app/real_time_predictor.py`, and `app/stream_engine.py`

## Key Dependencies

**Critical:**
- `flask` - Serves the dashboard, JSON API, and server-sent event stream from `app/app.py`
- `pandas` - Primary tabular processing layer for SQLite, CSV, and feature data in `app/forecast_support.py`, `data/real_data_fetcher.py`, and `pipeline/build_train_data.py`
- `numpy` - Shared numerical backbone for feature engineering and evaluation in `pipeline/real_data_feature_engineering.py`, `ml/train_model.py`, and `ml/evaluate_route_forecaster.py`
- `scikit-learn` - Planner model pipeline built with `ColumnTransformer`, `Pipeline`, `SimpleImputer`, `OneHotEncoder`, and `GradientBoostingRegressor` in `app/forecast_support.py`
- `xgboost` - Benchmark and observable prediction models in `ml/train_model.py` and the artifact consumers in `app/stream_engine.py` and `app/real_time_predictor.py`
- `requests` - HTTP client for public data sources in `data/real_data_fetcher.py` and `app/forecast_support.py`
- `joblib` - Persists model bundles and feature lists in `ml/` and `app/`

**Infrastructure:**
- `sqlite3` from the Python standard library - Sole persistence layer, targeting `data/shipments.db`
- `threading` and `queue` from the standard library - Background simulation and SSE fan-out in `app/stream_engine.py`
- `json`, `io`, and `uuid` from the standard library - Payload persistence, CSV ingestion, and import batch metadata in `app/forecast_support.py`

## Configuration

**Environment:**
- Environment-variable driven configuration was not detected; `rg` found no `os.getenv`, `dotenv`, or `.env` usage under `E:\MLCollege\real data`
- Runtime paths are hardcoded relative to `PROJECT_ROOT`, including `data/shipments.db` in `data/real_data_fetcher.py`, model artifacts in `ml/train_model.py`, and planner artifacts in `app/forecast_support.py`
- Model behavior is configured with in-code constants such as `MIN_TRAINING_ROWS`, `RESIDUAL_BLEND_WEIGHT`, and forecast feature lists in `app/forecast_support.py`, plus XGBoost hyperparameters in `ml/train_model.py`

**Build:**
- No packaging or build config files were detected: no `pyproject.toml`, `setup.py`, `setup.cfg`, `tox.ini`, `Dockerfile`, or CI workflow files
- Dependency declaration is limited to `requirements.txt`
- Operational commands are documented in `documentation_records/README.md`

## Platform Requirements

**Development:**
- Python environment with the packages in `requirements.txt`
- Outbound HTTPS access to public providers used by `data/fetch_fred_data.py`, `data/real_data_fetcher.py`, and `app/forecast_support.py`
- Filesystem write access to `data/`, `app/`, and `ml/` for SQLite, CSV outputs, JSON metrics, and `.joblib` model artifacts

**Production:**
- Self-hosted or local-process deployment model; the only detected network server is `app/app.py`, which runs Flask on `0.0.0.0:5001`
- Local SQLite-backed state in `data/shipments.db`; no external database, message broker, cache, or container orchestration is configured

---

*Stack analysis: 2026-03-26*
