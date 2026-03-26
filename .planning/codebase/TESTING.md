# Testing Patterns

## Framework

- **No test framework configured.** No `pytest`, `unittest`, or `nose` imports found anywhere in the codebase.
- `requirements.txt` does not include any testing dependencies (`pytest`, `coverage`, `pytest-cov`, etc.).
- No `conftest.py` files exist.

## Test Structure

### Test Files
- **Zero test files exist.** No `test_*.py` or `*_test.py` files found anywhere in the project.
- No `/tests/` or `/test/` directory exists.

### Test Naming
- N/A — no tests to establish naming conventions.

## Mocking Patterns

- **No mocking observed.** No imports of `unittest.mock`, `pytest-mock`, `responses`, or `httpretty` anywhere.
- Database calls use real SQLite connections throughout — no mock/fake DB patterns.
- API calls (`requests.get`) are made directly in production code without abstraction for testing (e.g., `data/real_data_fetcher.py:569`, `app/forecast_support.py:236`).

## Coverage

- **No coverage configuration found.** No `.coveragerc`, `setup.cfg [tool:coverage]`, or `pyproject.toml [tool.coverage]` sections.
- No `coverage` or `pytest-cov` in `requirements.txt`.

## CI Pipeline

- **No CI/CD configuration found.** Specifically checked:
  - `.github/` — does not exist
  - `.gitlab-ci.yml` — does not exist
  - `Makefile` — does not exist
  - `pyproject.toml` — does not exist
  - `setup.cfg` — does not exist
  - `.flake8` — does not exist
  - `ruff.toml` — does not exist
- No linting tools configured (`flake8`, `ruff`, `pylint`, `mypy`).

## Current State

### What Exists (Informal Validation Only)
- `ml/model_health_check.py` — manual health check script that validates model loading, feature alignment, and dummy prediction. Uses `sys.exit(0/1)` for pass/fail. Not a test framework integration.
- `skills/senior-data-scientist/scripts/model_evaluation_suite.py` — evaluation class with `logging`, but uses `assert` for validation, not a test framework.

### Gaps
- **No unit tests** for any module (data fetching, feature engineering, model training, prediction, API endpoints).
- **No integration tests** for the pipeline (`pipeline/real_data_pipeline.py`).
- **No API tests** for Flask routes (`app/app.py` endpoints).
- **No regression tests** for model training (`ml/train_model.py`).
- **No mock patterns** for external API dependencies (Open-Meteo weather API, Frankfurter FX API, Compass benchmark API).
- **No database fixtures** or test database setup.
- **No test data generation** — no factory patterns or fixture files.
- **No CI/CD pipeline** to run tests automatically on commits.
- **No linting/formatting** enforced — no static analysis of any kind.
- The `model_health_check.py:55-73` dummy prediction test is the closest thing to a smoke test, but it runs against the production model file, not in isolation.
