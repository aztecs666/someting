# Codebase Concerns

**Analysis Date:** 2026-03-26

Current operational snapshot from `data/shipments.db`:
- `route_observations`: 88 rows
- `route_predictions`: 15 rows
- `quote_history`: 0 rows
- `market_rate_history`: 17780 rows
- `route_forecasts`: 168 rows
- `live_ticks`: 263 rows
- `live_predictions`: 263 rows
- `prediction_accuracy`: 59 rows
- Database file size: 8278016 bytes

## Tech Debt

**Runtime schema and data mutation inside application code:**
- Issue: `data/real_data_fetcher.py` initializes schema and seed data from `RealDataFetcher.__init__()`, and the same module contains destructive migration and cleanup paths in `_migrate_external_benchmark_table()` and `_deduplicate_route_forecasts()`.
- Files: `data/real_data_fetcher.py`, `app/forecast_support.py`, `utils/real_data_audit.py`, `pipeline/real_data_pipeline.py`
- Impact: startup, import, and audit flows are not read-only. A diagnostic run can mutate production data, drop and recreate tables, or delete duplicate forecast rows without an explicit migration step.
- Fix approach: move schema evolution into explicit migration scripts, make `ensure_schema()` idempotent and non-destructive, and keep audit commands read-only.

**Two forecasting systems coexist with overlapping concepts and storage:**
- Issue: the legacy benchmark stream path uses `benchmark_history`, `benchmark_model.joblib`, and `app/stream_engine.py`, while the planner path uses `market_rate_history`, `route_forecaster.joblib`, and `app/forecast_support.py`.
- Files: `pipeline/build_train_data.py`, `ml/train_model.py`, `app/stream_engine.py`, `app/forecast_support.py`, `ml/train_route_forecaster.py`, `documentation_records/README.md`
- Impact: there is no single source of truth for training data, model artifacts, or forecast semantics. Future changes can easily update one path and leave the other stale.
- Fix approach: formally retire the legacy benchmark model or isolate it into a separate package and document one supported forecasting path.

**Large monolithic modules concentrate unrelated responsibilities:**
- Issue: `app/forecast_support.py` is 1518 lines, `app/app.py` is 934 lines, `data/real_data_fetcher.py` is 804 lines, and `app/stream_engine.py` is 573 lines.
- Files: `app/forecast_support.py`, `app/app.py`, `data/real_data_fetcher.py`, `app/stream_engine.py`
- Impact: feature work, bug fixes, and reviews require loading too much context. Small edits carry regression risk because data import, feature engineering, persistence, and UI logic are tightly coupled.
- Fix approach: split these files by responsibility into importers, data access, forecasting, persistence, and presentation modules.

**Generated artifacts and stateful data live beside source code:**
- Issue: the repository contains generated artifacts and databases while `.gitignore` also ignores the same categories.
- Files: `.gitignore`, `data/shipments.db`, `app/shipments.db`, `real data/shipments.db`, `app/route_forecaster.joblib`, `ml/benchmark_model.joblib`, `app/route_forecast_training_dataset.csv`
- Impact: local environments can drift silently, stale binaries can be mistaken for canonical outputs, and debugging becomes path-dependent.
- Fix approach: move runtime databases and model artifacts to a dedicated data/output directory outside the repo root or manage them through an artifact registry.

**Dependency versions are not pinned:**
- Issue: `requirements.txt` lists package names only.
- Files: `requirements.txt`, `ml/model_health_check.py`, `app/real_time_predictor.py`, `app/stream_engine.py`
- Impact: `xgboost`, `scikit-learn`, `joblib`, and `flask` upgrades can break serialized model compatibility or runtime behavior without any code change.
- Fix approach: pin versions, regenerate lockfiles, and record the model-training package set alongside each artifact.

**Legacy pseudo-real benchmark generation remains active in the codebase:**
- Issue: `pipeline/benchmark_manager.py` seeds lane prices by scaling a FRED macro index and adding random noise, while the project documentation presents the planner as real-data-only.
- Files: `pipeline/benchmark_manager.py`, `pipeline/build_train_data.py`, `documentation_records/README.md`
- Impact: the legacy benchmark model can still be trained on synthetic-looking derived data, which undermines the honesty boundary between real observations and simulated signals.
- Fix approach: remove or quarantine `benchmark_manager.load_historical_benchmarks()` from supported workflows and label the entire legacy benchmark path as sandbox-only.

## Known Bugs

**Observable predictor persistence creates duplicate prediction rows:**
- Symptoms: `route_predictions` accepts repeated inserts for the same `observation_id`. The current database already contains 5 redundant rows, and some observations have 2 prediction versions.
- Files: `app/real_time_predictor.py`, `data/real_data_fetcher.py`
- Trigger: running `RealTimePredictor.run_predictions(..., persist=True)` against observations that were already scored inserts a fresh row instead of replacing or versioning deliberately.
- Workaround: query only the latest `prediction_id` per `observation_id` as `utils/real_data_audit.py` does, and clean duplicates manually until a uniqueness rule exists.

**Observable predictor stage is not reproducible from source alone:**
- Symptoms: `pipeline/real_data_pipeline.py` can only execute the prediction stage when `ml/xgb_models.joblib` and `ml/xgb_features.joblib` exist, but the repository does not provide a documented command to create them.
- Files: `app/real_time_predictor.py`, `pipeline/real_data_pipeline.py`, `documentation_records/README.md`
- Trigger: running the observable pipeline in a fresh clone or new machine.
- Workaround: treat the stage as disabled and rely only on observation fetch plus route forecaster execution.

**Database file ambiguity is already present in the repository:**
- Symptoms: three SQLite files exist, including a zero-byte `app/shipments.db`.
- Files: `data/shipments.db`, `app/shipments.db`, `real data/shipments.db`
- Trigger: manual experimentation, tooling that searches for `shipments.db`, or developers opening the wrong file in SQLite tools.
- Workaround: operate only on `data/shipments.db` and delete accidental copies after verifying they are not needed.

## Security Considerations

**Unauthenticated network-exposed write endpoints:**
- Risk: the Flask app binds to `0.0.0.0` and exposes `POST /api/retrain` with no authentication, authorization, CSRF protection, or rate limiting.
- Files: `app/app.py`, `app/stream_engine.py`
- Current mitigation: none in code.
- Recommendations: restrict binding to localhost by default, add authentication before exposing any write endpoints, and queue retraining behind a background worker instead of servicing it directly from an HTTP request.

**Unsafe deserialization boundary around model artifacts:**
- Risk: `joblib.load()` is used for model and feature artifacts. Replacing a `.joblib` file with a malicious payload can execute code during load.
- Files: `app/stream_engine.py`, `app/real_time_predictor.py`, `ml/model_health_check.py`
- Current mitigation: artifacts are loaded from local disk only.
- Recommendations: treat model files as trusted deployment artifacts only, verify hashes before load, and do not accept user-supplied artifact paths.

**Operational data stored in a local SQLite file under the repo root:**
- Risk: observed route data, forecasts, and imported quotes live in `data/shipments.db`. The current database also sits alongside source code and can be copied or committed accidentally.
- Files: `data/shipments.db`, `.gitignore`, `data/real_data_fetcher.py`, `app/forecast_support.py`
- Current mitigation: `.gitignore` ignores `data/*.db`, but a database file is still present in the working tree.
- Recommendations: move the database path to an environment-driven location outside the repository and add deployment guidance for file permissions and backup handling.

## Performance Bottlenecks

**Per-tick SQLite churn in the live stream engine:**
- Problem: each tick opens database connections repeatedly, inserts into `live_ticks`, inserts into `live_predictions`, reads recent history for lag features, and writes accuracy records.
- Files: `app/stream_engine.py`
- Cause: the streaming loop performs multiple synchronous SQLite operations per 1.5-3.5 second cycle and keeps all work inside one Python process.
- Improvement path: batch writes, cache lag inputs in memory, move historical feature computation out of the hot loop, and separate ingest from HTTP serving.

**Row-wise pandas operations and per-row network lookups:**
- Problem: large parts of the training and import pipeline rely on `DataFrame.apply(axis=1)`, `iterrows()`, `itertuples()`, and row-by-row FX lookups.
- Files: `pipeline/build_train_data.py`, `app/forecast_routes.py`, `app/forecast_support.py`, `pipeline/benchmark_manager.py`
- Cause: forecasting, quote import, and benchmark sync are written as Python loops rather than vectorized transforms. `QuoteHistoryImporter.import_csv()` can call the FX provider once per row and `forecast_routes.py` runs several row-wise calculations over the full forecast frame.
- Improvement path: vectorize distance and heuristic calculations, cache FX rates by `(currency, date)`, and precompute reusable aggregates before row iteration.

**Manual retraining blocks the serving process:**
- Problem: retraining runs inside the same process that serves the dashboard and SSE stream.
- Files: `app/app.py`, `app/stream_engine.py`, `ml/train_model.py`
- Cause: `api_retrain()` calls `engine.retrain_model()` directly and the retraining function performs dataset construction, model fitting, artifact write, and DB logging synchronously.
- Improvement path: run retraining in a separate worker or task queue and expose only status polling from the web process.

## Fragile Areas

**Broad exception handling hides real failures:**
- Files: `app/app.py`, `app/stream_engine.py`, `data/real_data_fetcher.py`, `data/fetch_fred_data.py`, `app/real_time_predictor.py`
- Why fragile: several hot paths catch `Exception` broadly, print a message, and continue. The SSE stream converts all queue errors into heartbeats, the stream loop only prints `[STREAM ERROR]`, and external API failures often degrade to `None`.
- Safe modification: tighten exception scopes, log structured context, and fail loudly in test and CLI modes.
- Test coverage: no automated tests exercise these failure paths.

**Forecast persistence rewrites an entire date partition at once:**
- Files: `app/forecast_support.py`
- Why fragile: `persist_route_forecasts()` deletes all rows for a `forecast_date` before inserting replacement rows. A failure between delete and insert leaves the forecast date empty.
- Safe modification: wrap delete-plus-insert in an explicit transaction with verification, or stage into a temporary table before swapping.
- Test coverage: no automated tests verify rollback behavior or partial-write recovery.

**Distance and heuristic fallbacks can hide bad inputs:**
- Files: `pipeline/build_train_data.py`, `app/forecast_support.py`, `app/stream_engine.py`
- Why fragile: unknown route distances fall back to 5000 nautical miles, weather uplift and confidence calculations are hard-coded heuristics, and route encoding defaults can silently coerce unsupported lanes into generic values.
- Safe modification: validate route coverage before training or forecasting and emit explicit warnings when fallback values are used.
- Test coverage: not covered by automated tests.

**Audit and support tools are not side-effect free:**
- Files: `utils/real_data_audit.py`, `app/forecast_support.py`, `data/real_data_fetcher.py`
- Why fragile: audit and helper paths instantiate `RealDataFetcher`, which initializes schema and seeds reference data. A command intended for inspection can still alter database state.
- Safe modification: separate read-only queries from setup code and require explicit mutation flags.
- Test coverage: not covered by automated tests.

## Scaling Limits

**SQLite-backed single-process architecture:**
- Current capacity: the current database is 8.3 MB with low hundreds to low tens of thousands of rows, and the live app stores ticks, predictions, accuracy, and forecasts in the same file.
- Limit: concurrency becomes the bottleneck before storage size does. The combination of Flask threads, background retraining, sync import jobs, and SQLite write locks does not scale to multiple workers or sustained external traffic.
- Scaling path: move write-heavy data to a server database, isolate background jobs from request handling, and introduce queue-based ingestion for streaming events.

**In-memory subscriber fan-out for SSE:**
- Current capacity: subscribers live in the process-level `_subscribers` list inside `app/stream_engine.py`, each with a bounded in-memory queue.
- Limit: multi-process deployment breaks shared subscriber state, and slow clients accumulate dropped events or disconnect behavior that is hard to observe.
- Scaling path: replace in-process fan-out with Redis, a message broker, or a dedicated streaming layer.

## Dependencies at Risk

**Unpinned ML and web dependencies:**
- Risk: `flask`, `joblib`, `numpy`, `pandas`, `requests`, `scikit-learn`, and `xgboost` are all unversioned in `requirements.txt`.
- Impact: fresh installs can change model serialization compatibility, training outputs, or Flask behavior unexpectedly.
- Migration plan: pin exact versions, add a lockfile, and retrain artifacts under the pinned environment before future upgrades.

**Third-party public data contracts can break without warning:**
- Risk: benchmark sync depends on Compass/Xeneta's current CSV shape and AJAX endpoint, and the data pipeline depends on Open-Meteo and FRED response formats.
- Impact: upstream schema changes or rate limits can break imports and quietly reduce forecast quality or coverage.
- Migration plan: add schema validation, retries with backoff, monitoring around row counts, and fallback handling that fails the job explicitly when critical sources change.

## Missing Critical Features

**Automated test suite:**
- Problem: no `.test`, `.spec`, or other automated test files were found anywhere in the repository.
- Blocks: safe refactoring of `app/forecast_support.py`, `data/real_data_fetcher.py`, `app/stream_engine.py`, and persistence paths that currently mutate live SQLite state.

**Artifact build path for the observable predictor:**
- Problem: `app/real_time_predictor.py` expects `ml/xgb_models.joblib` and `ml/xgb_features.joblib`, but the repository does not include a supported build/export command for them.
- Blocks: reproducible setup of the observable prediction stage and any CI verification for that stage.

**Authentication and environment-based configuration:**
- Problem: the web app and database/model paths are hard-coded into source files instead of environment-driven deployment config.
- Blocks: secure multi-user deployment, secret management, and safe separation between local, staging, and production runtime state.

## Test Coverage Gaps

**No automated coverage for import and schema evolution flows:**
- What's not tested: CSV import validation, FX conversion behavior, public benchmark sync, and database migration/dedup logic.
- Files: `app/forecast_support.py`, `data/real_data_fetcher.py`, `pipeline/benchmark_manager.py`
- Risk: malformed source data or migration changes can corrupt stored history without an immediate signal.
- Priority: High

**No automated coverage for live streaming and retraining flows:**
- What's not tested: tick generation, prediction persistence, accuracy tracking, SSE fan-out, scheduler behavior, and manual retraining.
- Files: `app/stream_engine.py`, `app/app.py`, `ml/train_model.py`
- Risk: concurrency issues, lock contention, or hot-path exceptions can surface only at runtime.
- Priority: High

**No automated coverage for planner forecast persistence and evaluation:**
- What's not tested: `persist_route_forecasts()`, route ranking, confidence scoring, weather uplift heuristics, and holdout evaluation/report generation.
- Files: `app/forecast_routes.py`, `app/forecast_support.py`, `ml/evaluate_route_forecaster.py`
- Risk: forecast rows can be deleted, misranked, or persisted inconsistently without detection.
- Priority: High

---

*Concerns audit: 2026-03-26*
