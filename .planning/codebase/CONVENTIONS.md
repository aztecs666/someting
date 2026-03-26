# Coding Conventions

**Analysis Date:** 2026-03-26

## Naming Patterns

**Files:**
- Use `snake_case.py` for modules and script entrypoints. Examples: `app/real_time_predictor.py`, `pipeline/build_forecast_dataset.py`, `data/real_data_fetcher.py`.
- Use package-local wrapper scripts in `scripts/` when exposing a top-level CLI alias. Examples: `scripts/train_route_forecaster.py`, `scripts/evaluate_route_forecaster.py`.

**Functions:**
- Use `snake_case` for functions and methods. Examples: `app/forecast_support.py` (`build_training_dataset`, `predict_forecaster_bundle`), `pipeline/build_train_data.py` (`prepare_training_data`), `utils/real_data_audit.py` (`forecast_duplicate_summary`).
- Prefix internal helpers with `_` instead of exporting them through package APIs. Examples: `ml/train_model.py` (`_temporal_split`, `_naive_baseline`), `data/real_data_fetcher.py` (`_clean_numeric`, `_safe_nan_reduce`).

**Variables:**
- Use `snake_case` for locals, instance attributes, and DataFrame columns. Examples: `predictor_status`, `forecast_status`, `data_quality_score`, `feature_order`.
- Use descriptive names for DataFrame intermediates (`training_df`, `future_df`, `predictions_df`, `route_metrics`) instead of single-letter aliases outside very small scopes.

**Types and Classes:**
- Use `PascalCase` for classes. Examples: `data/real_data_fetcher.py` (`RealDataFetcher`), `pipeline/real_data_feature_engineering.py` (`RealDataFeatureEngineer`), `app/stream_engine.py` (`StreamEngine`).
- Use `UPPER_SNAKE_CASE` for module constants, table names, and artifact paths. Examples: `DB_PATH`, `ARTIFACT_PATH`, `OBSERVED_TABLE`, `PUBLIC_BENCHMARK_ROUTES`.
- Type annotations are not part of the current codebase convention. New code should only introduce them if applied consistently within the touched module.

## Code Style

**Formatting:**
- No formatter configuration is detected. `pyproject.toml`, `setup.cfg`, `tox.ini`, `pytest.ini`, `.flake8`, `ruff.toml`, and `.editorconfig` are not present at repo root.
- Match the existing hand-formatted style: 4-space indentation, double-quoted strings by default, and one blank line between top-level definitions.
- Keep long pandas and SQL expressions vertically expanded for readability. Examples: multi-line `cursor.execute(...)` blocks in `data/real_data_fetcher.py` and chained DataFrame expressions in `ml/evaluate_route_forecaster.py`.

**Module Preamble:**
- Most executable modules start by resolving the repository root and injecting it into `sys.path`:

```python
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

- Reuse that preamble when adding new runnable modules under `app/`, `data/`, `ml/`, `pipeline/`, `scripts/`, or `utils/`. Examples: `app/app.py`, `data/import_quotes.py`, `pipeline/real_data_pipeline.py`.

**Linting:**
- No lint configuration or enforced rule set is detected.
- Follow the observed import grouping manually:
1. Standard library imports, including the `PROJECT_ROOT` bootstrap.
2. Third-party imports such as `numpy`, `pandas`, `requests`, `joblib`, `sklearn`, `xgboost`, `flask`.
3. First-party imports from `app`, `data`, `ml`, `pipeline`, and `utils`.

## Import Organization

**Order:**
1. `import sys`, `import os`, then `PROJECT_ROOT` bootstrap in runnable modules.
2. Remaining standard-library imports like `sqlite3`, `json`, `time`, `datetime`, `uuid`, `warnings`.
3. Third-party packages.
4. Internal imports.

**Path Strategy:**
- Import from concrete modules, not package barrels. Examples: `from app.forecast_support import QuoteHistoryImporter`, `from pipeline.real_data_feature_engineering import RealDataFeatureEngineer`.
- Keep `__init__.py` files empty. Current package markers in `app/__init__.py`, `data/__init__.py`, `ml/__init__.py`, `pipeline/__init__.py`, and `utils/__init__.py` do not re-export symbols.

## Configuration

**Runtime Configuration:**
- Prefer module-level filesystem constants over environment variables. Examples: `app/forecast_support.py` (`ARTIFACT_PATH`, `METRICS_PATH`, `TRAINING_DATASET_PATH`), `app/real_time_predictor.py` (`MODEL_BUNDLE_PATH`, `FEATURE_ORDER_PATH`), `data/real_data_fetcher.py` (`DB_PATH`).
- Use relative paths rooted at `PROJECT_ROOT` rather than current working directory assumptions.
- Environment-variable configuration is not part of the current implementation. `os.getenv` and `os.environ` are not used in the application code.

**CLI Configuration:**
- Add `argparse` wrappers for user-triggered workflows. Examples: `data/import_quotes.py`, `pipeline/build_forecast_dataset.py`, `app/compare_external_benchmark.py`, `ml/evaluate_route_forecaster.py`.
- Prefer explicit flags such as `--db-path`, `--mode`, `--output`, `--provider`, and `--sync-public` instead of implicit positional behavior when optional configuration is needed.

## Error Handling

**Patterns:**
- Handle expected operational failures locally and return sentinel values (`None`, `False`, `0`) rather than raising custom exceptions. Examples: `data/real_data_fetcher.py` returns `None` on failed API calls; `ml/model_health_check.py` returns `False` on failed checks; `app/stream_engine.py` returns `None` when no prediction can be produced.
- Raise `ValueError` for invalid user-supplied CSV structure or insufficient training data. Examples: `app/forecast_support.py` (`Missing required quote columns`, `No valid benchmark rows found`, `Not enough rows to train`).
- Close SQLite connections with `try/finally` when a function can return early. Examples: `app/real_time_predictor.py` (`load_observations`), `pipeline/real_data_feature_engineering.py` (`load_from_database`), `utils/real_data_audit.py` (`read_sql`).
- Catch broad exceptions only at process boundaries or long-running loops. Examples: `app/stream_engine.py` catches `Exception` inside `_pipeline_loop`; `app/app.py` catches exceptions around SSE heartbeats.

**User-Facing Failure Style:**
- Prefer early-return guard clauses with a printed explanation over stack traces for routine conditions. Examples:
  - `app/forecast_routes.py`: missing artifact or empty future dataset.
  - `ml/train_route_forecaster.py`: empty training data or `ValueError` from training.
  - `pipeline/build_forecast_dataset.py`: no rows available for requested mode.

## Logging

**Framework:**
- Use `print` for CLI status reporting and diagnostics. The standard `logging` module is not used anywhere in the repo.

**Patterns:**
- Prefix operational messages with lightweight status markers such as `[OK]`, `[FAIL]`, `[!]`, and `[*]`. Examples: `ml/model_health_check.py`, `pipeline/benchmark_manager.py`, `data/fetch_fred_data.py`.
- Print tabular diagnostics with `DataFrame.to_string(index=False)` for audits and evaluations. Examples: `utils/real_data_audit.py`, `pipeline/real_data_pipeline.py`, `ml/evaluate_route_forecaster.py`, `app/forecast_routes.py`.
- For web routes, return JSON error payloads instead of logging-and-raising. Example: `app/app.py` returns `{"error": "Retrain failed — no training data"}` with HTTP 500 from `/api/retrain`.

## Comments and Docstrings

**When to Comment:**
- Use a module docstring to explain the file’s purpose, especially in data/ML-heavy modules. Examples: `data/real_data_fetcher.py`, `pipeline/real_data_pipeline.py`, `pipeline/real_data_feature_engineering.py`.
- Add short section comments to separate workflow stages in long procedural functions. Examples: `ml/train_model.py` and `app/stream_engine.py`.
- Keep comments focused on domain or modeling intent, not obvious assignments.

**Docstring Usage:**
- Functions and classes get docstrings selectively when behavior is reusable or non-obvious. Examples: `data/real_data_fetcher.py` (`RealDataFetcher`), `app/stream_engine.py` (`StreamEngine`, `init_stream_tables`), `pipeline/build_train_data.py` (`build_training_dataset`).
- Small wrapper scripts like `scripts/train_route_forecaster.py` and `scripts/sync_public_benchmarks.py` omit docstrings.

## Function Design

**Size:**
- Small CLI files stay thin and delegate to shared modules. Examples: `data/import_quotes.py`, `pipeline/build_forecast_dataset.py`, `scripts/evaluate_route_forecaster.py`.
- Core orchestration and feature-engineering modules tolerate large functions when they operate over one business workflow. Examples: `app/forecast_support.py`, `data/real_data_fetcher.py`, `app/stream_engine.py`.

**Parameters:**
- Default parameters are common for paths and control knobs. Examples: `db_path=DB_PATH`, `limit=50`, `day_start=14`, `day_end=20`, `persist=True`.
- Prefer primitive inputs and pandas DataFrames over custom data structures. There are no dataclasses or Pydantic models in the repo.

**Return Values:**
- Return pandas DataFrames for data retrieval and transformation boundaries. Examples: `predict_dataframe` in `app/real_time_predictor.py`, `build_future_forecast_features` in `app/forecast_support.py`, `latest_joined` in `utils/real_data_audit.py`.
- Return plain dictionaries for CLI/reporting summaries and API payloads. Examples: `sync_public_benchmarks` results in `app/forecast_support.py`, SSE events in `app/stream_engine.py`, evaluation metrics in `ml/evaluate_route_forecaster.py`.

## Module Design

**Exports:**
- Keep shared logic in concrete modules and import exact functions/classes from those modules.
- Use scripts as wrappers, not as the primary implementation site. Examples: `scripts/train_route_forecaster.py` delegates to `ml/train_route_forecaster.py`; `scripts/evaluate_route_forecaster.py` delegates to `ml/evaluate_route_forecaster.py`.

**Barrel Files:**
- Barrel-file re-exports are not used.
- New shared code should live in the domain module where it is consumed most often:
  - forecasting and training helpers in `app/forecast_support.py`
  - benchmark-history preparation in `pipeline/build_train_data.py` or `pipeline/benchmark_manager.py`
  - observable-route ingestion in `data/real_data_fetcher.py`
  - validation/audit scripts in `ml/` or `utils/`

---

*Convention analysis: 2026-03-26*
