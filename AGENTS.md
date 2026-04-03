# AGENTS.md - Agentic Coding Guidelines

## Project Overview

Route planning forecaster ML application. Build route-planning training data from quote history or external benchmarks, train 14-20 day forecasting models with cost bands, and provide weather uplift/delay heuristics.

## Build/Test Commands

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Core Commands
```bash
# Import quote history
python scripts/import_quotes.py path\to\quotes.csv

# Build planner training data
python scripts/build_forecast_dataset.py --mode train

# Train the planner
python scripts/train_route_forecaster.py

# Sync public benchmark history
python scripts/sync_public_benchmarks.py

# Generate forecasts
python scripts/forecast_routes.py

# Evaluate planner
python scripts/evaluate_route_forecaster.py --sync-public

# Compare external benchmarks
python scripts/compare_external_benchmark.py --import-csv path\to\provider.csv --provider Freightos
python scripts/compare_external_benchmark.py --provider Freightos

# Audit current state
python scripts/real_data_audit.py

# Run observable pipeline
python pipeline/real_data_pipeline.py
```

### Individual Test/Validation Scripts
```bash
python ml/model_health_check.py                 # Artifact health check (exit 0/1)
python ml/evaluate_route_forecaster.py          # Holdout evaluation
python utils/real_data_audit.py                 # Database & drift audit
python pipeline/build_train_data.py             # Training data sanity check
python pipeline/build_forecast_dataset.py --mode future  # Forecast dataset smoke test
```

## Code Style Guidelines

### Naming Conventions
- **Files**: `snake_case.py` (e.g., `real_time_predictor.py`, `train_route_forecaster.py`)
- **Functions**: `snake_case` (e.g., `build_training_dataset`, `predict_forecaster_bundle`)
- **Internal helpers**: Prefix with `_` (e.g., `_temporal_split`, `_clean_numeric`)
- **Variables**: `snake_case` including DataFrame columns
- **Classes**: `PascalCase` (e.g., `RealDataFetcher`, `StreamEngine`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DB_PATH`, `ARTIFACT_PATH`)

### Formatting
- 4-space indentation
- Double-quoted strings by default
- One blank line between top-level definitions
- Keep long pandas/SQL expressions vertically expanded for readability

### Type Annotations
Not currently enforced. Only add if applied consistently within the touched module.

## Import Organization

Order (three groups):
1. Standard library (`import sys`, `import os`, then PROJECT_ROOT bootstrap)
2. Third-party (`numpy`, `pandas`, `requests`, `joblib`, `sklearn`, `xgboost`, `flask`)
3. First-party (`app`, `data`, `ml`, `pipeline`, `utils`)

Import from concrete modules, not package barrels. Keep `__init__.py` files empty.

### Module Preamble Pattern
```python
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```
Reuse this in any new runnable module under `app/`, `data/`, `ml/`, `pipeline/`, `scripts/`, or `utils/`.

## Error Handling
- Handle expected failures locally; return sentinels (`None`, `False`, `0`) rather than raising custom exceptions
- Raise `ValueError` for invalid user-supplied CSV or insufficient training data
- Use `try/finally` to close SQLite connections when a function can return early
- Catch broad exceptions only at process boundaries or long-running loops
- Prefer early-return guard clauses with printed explanations over stack traces for routine conditions

Example patterns:
```python
if not os.path.exists(ARTIFACT_PATH):
    print("No route forecaster artifact found. Run train_route_forecaster.py first.")
    return

if valid.empty:
    raise ValueError("No valid quote rows found after validation.")
```

## Logging
- Use `print` for CLI status reporting (not `logging` module)
- Prefix operational messages: `[OK]`, `[FAIL]`, `[!]`, `[*]`
- Use `DataFrame.to_string(index=False)` for tabular diagnostics

## Configuration
- Prefer module-level filesystem constants over environment variables
- Use relative paths rooted at `PROJECT_ROOT`
- Use explicit argparse flags (`--db-path`, `--mode`, `--output`, `--provider`, `--sync-public`)

## Project Structure

```
app/          # Flask runtime, streaming engine, planner support, generated artifacts
data/         # SQLite DB, observable ingestion code
pipeline/     # Orchestration scripts, feature-building
ml/           # Model training, evaluation, benchmark artifacts
scripts/      # Thin CLI wrappers
utils/        # Operational audit helpers
logs/         # Generated logs and exports
documentation_records/  # Project notes
```

**Key Entry Points:**
- `app/app.py` - Flask dashboard
- `pipeline/real_data_pipeline.py` - Observable pipeline
- `ml/train_route_forecaster.py` - Planner training
- `app/forecast_support.py` - Central route-planning domain module
- `data/real_data_fetcher.py` - Observable schema and ingestion

## Module Design
- Keep business logic in `app/`, `data/`, `pipeline/`, `ml/`, or `utils/`
- `scripts/` should only contain thin wrappers with `sys.path` shim, one import, and `if __name__ == "__main__":`
- New code should live in the domain module where it is consumed most often

## Testing Guidelines

No formal test framework (pytest/unittest). Validation is script-driven:
- `ml/model_health_check.py` - Pass/fail exit code
- `ml/evaluate_route_forecaster.py` - Holdout metrics reporting
- `utils/real_data_audit.py` - Data quality and drift checks
- `pipeline/build_train_data.py` - Dataset sanity checks

UseTemporal validation, not random train/test splits. Compare models against naive baselines.

## Database
- SQLite: `data/shipments.db`
- Main tables: `quote_history`, `market_rate_history`, `route_forecasts`, `route_observations`, `route_predictions`
- Schema changes should stay near `RealDataFetcher` in `data/real_data_fetcher.py`

## Dependencies
```
flask, joblib, numpy, pandas, requests, scikit-learn, xgboost
```

## Notes
- No linter/formatter config detected - follow existing hand-formatted style
- No type annotations in codebase
- No dataclasses or Pydantic models
- Use plain DataFrames for data boundaries, plain dicts for CLI/reporting