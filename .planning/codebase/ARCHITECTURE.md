# Architecture

**Analysis Date:** 2026-03-26

## Pattern Overview

**Overall:** Modular Python application organized by responsibility around a shared SQLite database and file-based ML artifacts.

**Key Characteristics:**
- Use package directories as coarse layers: `data/` for ingestion and schema ownership, `pipeline/` for orchestration and feature preparation, `ml/` for training and evaluation, `app/` for runtime services and web/API delivery, `scripts/` for thin executable wrappers.
- Share state through the SQLite database at `data/shipments.db` plus model and dataset artifacts in `ml/` and `app/`.
- Favor script-driven execution over framework-managed dependency injection; most modules prepend `PROJECT_ROOT` to `sys.path` and then import sibling packages directly.

## Layers

**Interface Layer:**
- Purpose: Expose the dashboard, JSON APIs, SSE stream, and human-invoked CLI commands.
- Location: `app/app.py`, `scripts/*.py`, `app/compare_external_benchmark.py`, `data/import_quotes.py`
- Contains: Flask routes, inline HTML dashboard, argparse entry points, wrapper `main()` functions.
- Depends on: `app/stream_engine.py`, `app/forecast_support.py`, `ml/*.py`, `pipeline/*.py`, `utils/real_data_audit.py`
- Used by: Browser clients, local operators running `python ...` commands.

**Runtime Service Layer:**
- Purpose: Hold long-lived runtime services that keep operating state in memory and persist outputs to SQLite.
- Location: `app/stream_engine.py`, `app/real_time_predictor.py`
- Contains: `StreamEngine`, `RealTimePredictor`, SSE subscriber registry, live tick simulation, prediction persistence.
- Depends on: `ml/benchmark_model.joblib`, `ml/benchmark_features.joblib`, `pipeline/build_train_data.py`, `pipeline/real_data_feature_engineering.py`, `data/shipments.db`
- Used by: `app/app.py` and `pipeline/real_data_pipeline.py`

**Planner Domain Layer:**
- Purpose: Centralize route-planning logic, training dataset construction, forecast feature creation, weather enrichment, and forecast persistence.
- Location: `app/forecast_support.py`, `app/forecast_routes.py`
- Contains: `QuoteHistoryImporter`, `ExternalBenchmarkImporter`, `PublicBenchmarkSync`, `ForecastWeatherBuilder`, model training helpers, forecast comparators.
- Depends on: `data/real_data_fetcher.py`, `requests`, `pandas`, `scikit-learn`, `joblib`, SQLite tables in `data/shipments.db`
- Used by: `ml/train_route_forecaster.py`, `ml/evaluate_route_forecaster.py`, `pipeline/build_forecast_dataset.py`, `scripts/*.py`, `pipeline/real_data_pipeline.py`

**Data Ingestion and Persistence Layer:**
- Purpose: Own the canonical schema for observed routes and planner tables, then populate SQLite from public or file-based sources.
- Location: `data/real_data_fetcher.py`, `data/fetch_fred_data.py`, `pipeline/benchmark_manager.py`
- Contains: `RealDataFetcher`, schema initialization, watchlist seeding, API fetches, benchmark table loaders, CSV imports, database migration helpers.
- Depends on: `requests`, `sqlite3`, `pandas`, external HTTP APIs, `data/shipments.db`
- Used by: `pipeline/real_data_pipeline.py`, `app/forecast_support.py`, `utils/real_data_audit.py`

**Feature Engineering and Training Layer:**
- Purpose: Transform raw observations and historical benchmark series into model-ready frames, then train and evaluate ML artifacts.
- Location: `pipeline/real_data_feature_engineering.py`, `pipeline/build_train_data.py`, `ml/train_model.py`, `ml/train_route_forecaster.py`, `ml/evaluate_route_forecaster.py`, `ml/model_health_check.py`
- Contains: `RealDataFeatureEngineer`, benchmark training dataset builder, XGBoost training flow, planner forecaster training and evaluation.
- Depends on: `data/shipments.db`, `app/forecast_support.py`, `joblib`, `xgboost`, `scikit-learn`, `numpy`, `pandas`
- Used by: `app/real_time_predictor.py`, `app/stream_engine.py`, CLI wrappers under `scripts/`

**Audit and Utility Layer:**
- Purpose: Provide operational inspection and one-off maintenance helpers.
- Location: `utils/real_data_audit.py`, `scripts/dump_code.py`, `scripts/fix_paths.py`
- Contains: database audits, drift summaries, repository dump helper, historical migration script.
- Depends on: live database contents and the same domain modules as production flows.
- Used by: Local maintainers; `scripts/real_data_audit.py` wraps the main audit.

## Data Flow

**Observable Snapshot Pipeline:**

1. `pipeline/real_data_pipeline.py` instantiates `data.real_data_fetcher.RealDataFetcher` and calls `fetch_watchlist_observations()`.
2. `data/real_data_fetcher.py` ensures schema, seeds the route watchlist, fetches weather and marine snapshots, builds observation rows, and inserts them into `route_observations` inside `data/shipments.db`.
3. `app/real_time_predictor.py` loads recent observations, uses `pipeline.real_data_feature_engineering.RealDataFeatureEngineer` to build ordered feature frames, and persists predictions to `route_predictions` when XGBoost artifacts are present.
4. `pipeline/real_data_pipeline.py` optionally invokes `app.forecast_routes.main()` when the route forecaster artifact at `app/route_forecaster.joblib` exists.

**Planner Training Flow:**

1. `ml/train_route_forecaster.py` calls `app.forecast_support.build_training_dataset()`.
2. `app/forecast_support.py` loads `quote_history` and `market_rate_history`, prepares feature rows, and chooses training modes such as `quote_history` or `external_benchmark_history`.
3. `app/forecast_support.py` trains a scikit-learn bundle and writes outputs to `app/route_forecaster.joblib`, `app/route_forecast_training_dataset.csv`, and `app/route_forecaster_metrics.json`.
4. Later forecast and evaluation commands reload the same bundle through `load_forecaster_bundle()`.

**Route Forecast Generation Flow:**

1. `app/forecast_routes.py` loads the saved forecaster bundle from `app/route_forecaster.joblib`.
2. `app/forecast_support.py` builds 14-20 day future feature rows from recent history and weather forecasts through `build_future_forecast_features()`.
3. `predict_forecaster_bundle()` generates baseline, low, and high cost estimates; `estimate_weather_cost_uplift()` and `estimate_weather_delay_days()` add heuristic adjustments.
4. `persist_route_forecasts()` stores ranked route windows in the `route_forecasts` table.

**Live Dashboard Flow:**

1. `app/app.py` imports the singleton `engine` from `app/stream_engine.py`.
2. Running `python app/app.py` starts `engine.start()` and then starts Flask on port `5001`.
3. `app/stream_engine.py` spawns a tick-generation thread and a weekly retrain scheduler, writes `live_ticks`, `live_predictions`, `prediction_accuracy`, and `retrain_log` rows, and broadcasts JSON updates to SSE subscribers.
4. Browser code embedded in `app/app.py` consumes `/stream` plus `/api/prices`, `/api/stats`, `/api/ticks`, `/api/accuracy`, and `/api/retrain_log`.

**State Management:**
- Persist application state in `data/shipments.db`; treat it as the contract boundary between ingestion, training, forecasting, and audit commands.
- Persist model bundles and dataset snapshots to files in `ml/` and `app/`; runtime modules reload from disk rather than sharing training objects in memory across processes.
- Use in-memory state only for transient runtime concerns such as SSE subscriber queues and current live lane prices in `app/stream_engine.py`.

## Key Abstractions

**`RealDataFetcher`:**
- Purpose: Own schema setup and observable route snapshot ingestion.
- Examples: `data/real_data_fetcher.py`
- Pattern: Stateful service object with private schema helpers and public fetch/persist methods.

**`RealDataFeatureEngineer`:**
- Purpose: Convert observed route snapshots into model input columns without fabricating missing values.
- Examples: `pipeline/real_data_feature_engineering.py`
- Pattern: Stateless transformer class operating on pandas DataFrames.

**Planner Forecaster Bundle:**
- Purpose: Package the trained route-planning model, preprocessing, metadata, calibration widths, and training provenance.
- Examples: `app/forecast_support.py`, persisted at `app/route_forecaster.joblib`
- Pattern: File-backed bundle returned by `train_forecaster_bundle()` and reused by training, forecasting, and evaluation flows.

**`RealTimePredictor`:**
- Purpose: Apply observable-model artifacts to latest route observations and persist scored results.
- Examples: `app/real_time_predictor.py`
- Pattern: Service object that validates artifact readiness, engineers features, clips feature drift, and inserts predictions.

**`StreamEngine`:**
- Purpose: Run the live benchmark dashboard loop and weekly retraining.
- Examples: `app/stream_engine.py`
- Pattern: Singleton long-lived background service imported into Flask.

## Entry Points

**Flask Dashboard:**
- Location: `app/app.py`
- Triggers: `python app/app.py`
- Responsibilities: Start `StreamEngine`, serve dashboard HTML, expose JSON APIs and SSE.

**Observable Pipeline Runner:**
- Location: `pipeline/real_data_pipeline.py`
- Triggers: `python pipeline/real_data_pipeline.py`
- Responsibilities: Fetch observations, optionally score them with the observable predictor, optionally run the route forecaster.

**Planner Dataset Builder:**
- Location: `pipeline/build_forecast_dataset.py`
- Triggers: `python pipeline/build_forecast_dataset.py --mode train|future`
- Responsibilities: Materialize planner training or future forecast CSV datasets.

**Planner Trainer:**
- Location: `ml/train_route_forecaster.py`
- Triggers: `python ml/train_route_forecaster.py` or `python scripts/train_route_forecaster.py`
- Responsibilities: Build training data, train the planner, persist bundle and metrics.

**Planner Evaluator:**
- Location: `ml/evaluate_route_forecaster.py`
- Triggers: `python ml/evaluate_route_forecaster.py` or `python scripts/evaluate_route_forecaster.py`
- Responsibilities: Evaluate holdout performance and optionally sync public benchmark history first.

**Legacy Benchmark Trainer:**
- Location: `ml/train_model.py`
- Triggers: `python ml/train_model.py`
- Responsibilities: Train the XGBoost benchmark forecasting model used by `app/stream_engine.py`.

**Data Import Commands:**
- Location: `data/import_quotes.py`, `app/compare_external_benchmark.py`, `scripts/sync_public_benchmarks.py`
- Triggers: Direct CLI execution or the wrappers under `scripts/`
- Responsibilities: Import quote history, import external benchmarks, sync public benchmark history, compare latest forecasts.

## Error Handling

**Strategy:** Best-effort script execution with defensive guards, user-facing print messages, and early returns instead of centralized exception handling.

**Patterns:**
- Validate prerequisites at command entry and exit early with a printed message when files or training data are missing, as in `ml/train_route_forecaster.py`, `app/forecast_routes.py`, and `ml/evaluate_route_forecaster.py`.
- Keep network and file failures local to the calling helper, usually by `try/except` blocks that return `None`, an empty DataFrame, or a status message, as in `data/fetch_fred_data.py`, `app/forecast_support.py`, and `app/real_time_predictor.py`.
- Allow background runtime errors to be logged and retried inside loops, as in `app/stream_engine.py`.

## Cross-Cutting Concerns

**Logging:** Use `print()` for CLI flows and background errors; expose runtime state as JSON via Flask endpoints in `app/app.py` and `app/stream_engine.py`. No structured logging framework is present.

**Validation:** Perform validation close to the edge. CSV importers in `app/forecast_support.py` and `data/import_quotes.py` check required columns; training flows verify row counts and artifact existence before proceeding.

**Authentication:** Not detected. The Flask app in `app/app.py` exposes dashboard and API endpoints without auth middleware.

**Configuration:** Resolve most configuration by file paths relative to `PROJECT_ROOT` or module directories. Runtime tuning is largely hard-coded in modules instead of external config files.

**Persistence Boundary:** Treat `data/shipments.db` as the shared system record. New cross-module features should prefer new tables or columns there over ad hoc JSON files unless they are model artifacts.

---

*Architecture analysis: 2026-03-26*
