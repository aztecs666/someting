# Codebase Conventions

## Code Style

### Formatting
- **No formatter enforced** — no `black`, `ruff`, or `autopep8` configuration present.
- Inconsistent indentation: mostly 4 spaces, but some files use tab-aligned comments (e.g., `app/stream_engine.py:206-220`).
- Line lengths vary widely; many lines exceed 120 characters (e.g., `data/real_data_fetcher.py:86`, `app/forecast_support.py:357`).
- Blank line usage is inconsistent — some functions have 1 blank line before, others have 2.

### Type Hints
- **Almost never used** in core codebase (`app/`, `pipeline/`, `data/`, `ml/`, `utils/`).
- **Exception**: `skills/senior-data-scientist/scripts/model_evaluation_suite.py:13` imports `Dict`, `List`, `Optional` from `typing` and uses them in class signatures.
- Function parameters and return types are untyped throughout (e.g., `pipeline/real_data_pipeline.py:29`, `data/real_data_fetcher.py:98`).

### Docstrings
- Module-level docstrings present in most files (e.g., `app/app.py:1-9`, `pipeline/real_data_pipeline.py:1-9`, `data/real_data_fetcher.py:1-6`).
- Module docstrings are descriptive, explaining purpose and design intent.
- Function/class docstrings are **sparse** — only present on a few functions:
  - `ml/train_model.py:32-35` (`_temporal_split`) — one-liner docstring
  - `ml/train_model.py:54-58` (`_naive_baseline`) — multi-line docstring
  - `ml/train_model.py:224` (`predict_future_price`) — single-line docstring
  - `app/stream_engine.py:136` (`StreamEngine`) — class docstring is one line
- Most functions have **no docstrings** at all (e.g., `_connect()`, `save_observation()`, `run_once()`).

## Naming

### Variables
- **snake_case** throughout — consistently applied (e.g., `current_price`, `price_change_pct`, `data_quality_score`).
- Module-level constants use **UPPER_SNAKE_CASE** (e.g., `DB_PATH`, `MODEL_PATH`, `OBSERVED_TABLE`, `PORT_DATABASE`).
- Private helpers prefixed with underscore (e.g., `_connect()`, `_clean_numeric()`, `_safe_nan_reduce()`).

### Functions
- **snake_case** — consistently applied (e.g., `fetch_weather_open_meteo`, `calculate_distance_nm`, `build_route_observation`).
- Private/internal functions prefixed with underscore (e.g., `_temporal_split`, `_init_database`, `_load_model`).
- No `@staticmethod` or `@classmethod` decorators used anywhere.

### Classes
- **PascalCase** — consistently applied (e.g., `RealDataFetcher`, `RealTimePredictor`, `StreamEngine`, `QuoteHistoryImporter`).
- Class count is low; most logic is procedural functions.

### Modules
- **snake_case** file names — consistently applied (e.g., `real_data_fetcher.py`, `stream_engine.py`, `model_health_check.py`).
- Duplicate script names exist across directories:
  - `scripts/real_data_audit.py` and `utils/real_data_audit.py`
  - `scripts/forecast_routes.py` and `app/forecast_routes.py`
  - `scripts/compare_external_benchmark.py` and `app/compare_external_benchmark.py`
  - `scripts/evaluate_route_forecaster.py` and `ml/evaluate_route_forecaster.py`
  - `scripts/train_route_forecaster.py` and `ml/train_route_forecaster.py`
  - `scripts/build_forecast_dataset.py` and `pipeline/build_forecast_dataset.py`
  - `scripts/import_quotes.py` and `data/import_quotes.py`
  - `scripts/sync_public_benchmarks.py` (no `app/` or `pipeline/` counterpart found but referenced)

## Patterns

### Error Handling
- **Minimal try/except usage** — most code does not handle errors explicitly.
- Common patterns:
  - `try/except` for API calls with `print()` logging: `data/real_data_fetcher.py:568-574` (`except requests.RequestException`)
  - `try/finally` for database connections: `data/real_data_fetcher.py:551-557`, `utils/real_data_audit.py:40-43`
  - Bare `except Exception` in SSE stream: `app/app.py:103`
  - `except Exception as exc` for model loading: `app/real_time_predictor.py:75`
- **No custom exceptions** defined anywhere in the codebase.
- Validation errors raise `ValueError` (e.g., `app/forecast_support.py:310`, `app/forecast_support.py:1083`).
- Many functions return `None` on failure instead of raising (e.g., `ml/train_model.py:76`, `data/real_data_fetcher.py:574`).

### Logging
- **No centralized logging** — uses `print()` statements throughout.
- One exception: `skills/senior-data-scientist/scripts/model_evaluation_suite.py:10-19` uses Python `logging` module with `basicConfig`.
- Print-based status markers: `[OK]`, `[!]`, `[FAIL]`, `[WARN]`, `[STREAM ERROR]` (e.g., `ml/model_health_check.py:25`, `ml/train_model.py:75`).
- `logs/` directory exists but is gitignored — no logging configuration files found.

### Config Management
- **No config files** — no `.env`, `config.py`, `settings.py`, or YAML config.
- All configuration is hardcoded as module-level constants:
  - `DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")` (repeated in multiple files)
  - `MODEL_PATH`, `FEATURES_PATH` (repeated in `ml/train_model.py`, `app/app.py`, `app/stream_engine.py`)
  - API URLs hardcoded: `https://api.open-meteo.com/v1/forecast`, `https://marine-api.open-meteo.com/v1/marine`, `https://api.frankfurter.app/`
  - Model hyperparameters hardcoded: `n_estimators=100`, `max_depth=2`, etc. in `ml/train_model.py:99-113`

## Imports

### Organization
- **No consistent import ordering** — stdlib, third-party, and local imports are mixed.
- Common pattern: `sys.path.insert(0, PROJECT_ROOT)` block appears at the top of almost every file before other imports.
- The `sys.path` manipulation is the primary import mechanism (not proper package installation).

### Import Style
- **Absolute imports** throughout — uses package-qualified paths (e.g., `from pipeline.build_train_data import prepare_training_data`, `from data.real_data_fetcher import RealDataFetcher`).
- No relative imports (`from . import` or `from .. import`) used anywhere.
- `__init__.py` files exist but are empty (`scripts/__init__.py`, `utils/__init__.py`, `app/__init__.py`, `ml/__init__.py`, `pipeline/__init__.py`, `data/__init__.py`, `utils/__init__.py`).
- Duplicate imports observed: `ml/model_health_check.py:1-2` has `import sys` twice.

## File Organization

### Directory Structure
```
app/          — Flask web app, SSE streaming, prediction routes
data/         — Data fetching, database schema, import scripts
ml/           — Model training, evaluation, health checks
pipeline/     — Feature engineering, data pipeline orchestration
scripts/      — Utility/migration scripts (many are copies of files in other dirs)
utils/        — Audit utilities
skills/       — Skill plugin scripts (senior-data-scientist)
documentation_records/ — Project documentation/notes
logs/         — Runtime logs (gitignored)
```

### Code Splitting
- Files are split by domain concern (app, data, ml, pipeline).
- `app/forecast_support.py` is the largest file (~1500+ lines) — handles import, training, prediction, weather features.
- Many files are self-contained scripts with `if __name__ == "__main__":` blocks.
- The `scripts/` directory contains what appear to be copies/snapshots of files from `app/`, `ml/`, `pipeline/`, and `data/`.
