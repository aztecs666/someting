# Testing Patterns

**Analysis Date:** 2026-03-26

## Test Framework

**Runner:**
- Not detected. No `pytest`, `unittest`, `nose`, or `tox` configuration files are present, and no `test_*.py`, `*_test.py`, `*.spec.py`, or `conftest.py` files exist under `app/`, `data/`, `ml/`, `pipeline/`, `scripts/`, or `utils/`.
- Validation is currently script-driven through executable modules such as `ml/model_health_check.py`, `ml/evaluate_route_forecaster.py`, `utils/real_data_audit.py`, `pipeline/build_train_data.py`, and `pipeline/build_forecast_dataset.py`.

**Assertion Library:**
- Not applicable for automated tests.
- Script validation relies on explicit conditionals, printed metrics, and process exit codes. Example: `ml/model_health_check.py` returns `True` or `False` and exits with `sys.exit(0 if success else 1)`.

**Run Commands:**
```bash
python ml/model_health_check.py                 # Artifact health check with pass/fail exit code
python ml/evaluate_route_forecaster.py          # Holdout evaluation and validation-window reporting
python utils/real_data_audit.py                 # Database, drift, and forecast audit
python pipeline/build_train_data.py             # Training-data sanity sample and future-target check
python pipeline/build_forecast_dataset.py --mode future  # Forecast dataset generation smoke check
```

## Test File Organization

**Location:**
- There is no automated test directory or co-located test module pattern.
- Validation logic is embedded in production-adjacent scripts:
  - `ml/` for model evaluation and artifact checks.
  - `utils/` for data quality and audit reporting.
  - `pipeline/` for dataset generation sanity checks.
  - `scripts/` for thin wrappers around those commands.

**Naming:**
- Validation entrypoints use task-oriented names, not test names. Examples: `ml/model_health_check.py`, `ml/evaluate_route_forecaster.py`, `utils/real_data_audit.py`.

**Structure:**
```text
ml/
  model_health_check.py
  evaluate_route_forecaster.py
pipeline/
  build_train_data.py
  build_forecast_dataset.py
utils/
  real_data_audit.py
scripts/
  evaluate_route_forecaster.py
  train_route_forecaster.py
  sync_public_benchmarks.py
```

## Test Structure

**Validation Script Pattern:**
```python
if not os.path.exists(ARTIFACT_PATH):
    print("No route forecaster artifact found. Run train_route_forecaster.py first.")
    return

metrics, route_metrics, detail = _evaluate(bundle, training_df)
print("=== ROUTE FORECASTER EVALUATION ===")
print(route_metrics.to_string(index=False))
```

This pattern appears in `ml/evaluate_route_forecaster.py` and similar guard-then-report flows appear in `app/forecast_routes.py`, `pipeline/build_forecast_dataset.py`, and `pipeline/real_data_pipeline.py`.

**Patterns:**
- Use guard clauses to stop validation early when required artifacts or data are missing.
- Use pandas summaries and table prints instead of assertions for most checks.
- Reserve actual pass/fail process exit behavior for the artifact smoke test in `ml/model_health_check.py`.

## Mocking

**Framework:**
- Not used. No `unittest.mock`, `pytest-mock`, `MagicMock`, or `patch()` usage is present in the repo.

**Patterns:**
```python
try:
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json()
except requests.RequestException as exc:
    print(f"Weather API error for ({lat}, {lon}): {exc}")
    return None
```

This runtime-fallback style in `data/real_data_fetcher.py` replaces mocked external-service tests.

**What to Mock:**
- Nothing is mocked today.
- If automated tests are added, the first isolation boundaries should be:
  - `requests.get` and `requests.Session.get` in `data/real_data_fetcher.py` and `app/forecast_support.py`
  - `joblib.load` and `joblib.dump` in `app/real_time_predictor.py`, `app/stream_engine.py`, and `ml/model_health_check.py`
  - SQLite connections created by `sqlite3.connect(...)` across `data/`, `app/`, and `pipeline/`

**What NOT to Mock:**
- The current validation posture assumes real integration with `data/shipments.db`, model artifacts, and downloaded benchmark/weather data. Existing scripts are meant to inspect actual state, not faked state.

## Fixtures and Factories

**Test Data:**
```python
dummy_data = np.zeros((1, len(features)))
df_dummy = pd.DataFrame(dummy_data, columns=features)
df_dummy["current_price"] = 2500
df_dummy["distance_nm"] = 5000
```

This ad hoc fixture pattern appears in `ml/model_health_check.py`. The repo does not contain reusable fixture or factory modules.

**Location:**
- Real validation data comes from `data/shipments.db`.
- Generated artifacts live under `app/` and `ml/`, including `app/route_forecaster.joblib`, `app/route_forecast_training_dataset.csv`, `app/route_forecast_future_dataset.csv`, `ml/benchmark_model.joblib`, and `ml/benchmark_features.joblib`.
- Seed/reference constants are embedded directly in source modules. Examples: `PORT_DATABASE` and `DEFAULT_WATCHLIST` in `data/real_data_fetcher.py`, lane seed data in `pipeline/benchmark_manager.py`.

## Coverage

**Requirements:**
- None enforced. No coverage tool, threshold, or CI gate is present.

**Current Coverage Posture:**
- Automated unit-test coverage is effectively absent.
- Validation exists as manual or script-triggered checks around:
  - model artifact integrity in `ml/model_health_check.py`
  - offline holdout metrics in `ml/evaluate_route_forecaster.py`
  - database/state audits in `utils/real_data_audit.py`
  - dataset-generation sanity checks in `pipeline/build_train_data.py`
- High-risk modules with no automated regression net include `app/forecast_support.py`, `data/real_data_fetcher.py`, `app/stream_engine.py`, and `app/app.py`.

**View Coverage:**
```bash
Not available
```

## Test Types

**Unit Tests:**
- Not used.
- Pure-function candidates exist, but they are currently validated indirectly through script execution. Examples: `_temporal_split` in `ml/train_model.py`, `estimate_weather_delay_days` and `estimate_confidence_score` in `app/forecast_support.py`, and `_safe_nan_reduce` in `data/real_data_fetcher.py`.

**Integration Tests:**
- Implemented informally as executable workflows that hit real dependencies:
  - `ml/evaluate_route_forecaster.py` exercises training-data assembly, model loading, prediction, and metric reporting.
  - `utils/real_data_audit.py` joins database tables and checks drift against saved training ranges.
  - `ml/model_health_check.py` loads persisted artifacts and runs a real prediction through the model.
  - `app/compare_external_benchmark.py` imports CSV data and compares stored route forecasts to external benchmark rows.

**E2E Tests:**
- Not used.
- The nearest equivalent is running the Flask app in `app/app.py` and the background engine in `app/stream_engine.py`, then checking API routes and the dashboard manually.

## Validation Practices

**Training and Evaluation:**
- Use chronological validation rather than random train/test splitting. `ml/train_model.py` uses `_temporal_split(...)`, and `ml/evaluate_route_forecaster.py` uses `time_split(...)` from `app/forecast_support.py`.
- Compare models against naive baselines. `ml/train_model.py` reports baseline MAE/RMSE/R2, and `ml/evaluate_route_forecaster.py` reports `baseline_mae`, `baseline_mape_pct`, and improvement percentages.
- Track interval quality as well as point-error quality. `ml/evaluate_route_forecaster.py` reports `interval_coverage_pct`.

**Data Quality and Drift:**
- Use warnings and audits for questionable training inputs. `pipeline/build_train_data.py` emits a `warnings.warn(...)` when benchmark sources appear synthetic.
- Check feature drift against recorded training ranges. `utils/real_data_audit.py` calls `predictor.prepare_features(..., clip_to_training_range=False)` and reports rows below/above stored min/max bounds.

**Artifact Validation:**
- Confirm model-file existence, loadability, feature-count alignment, dummy prediction success, and feature-importance extraction in `ml/model_health_check.py`.

## Common Patterns

**Async and Long-Running Validation:**
```python
try:
    while True:
        observations, predictions, predictor_status, forecast_status = self.run_once()
        print(observations.to_string(index=False))
        time.sleep(interval_minutes * 60)
except KeyboardInterrupt:
    print("Pipeline stopped.")
```

This pattern in `pipeline/real_data_pipeline.py` is used for ongoing manual observation rather than automated test scheduling.

**Error Testing:**
```python
if valid.empty:
    raise ValueError("No valid quote rows found after validation.")
```

Input validation is mostly exercised by runtime imports in `app/forecast_support.py`, not by dedicated negative test cases.

**Recommended Verification Sequence For New Changes:**
1. Run `python ml/model_health_check.py` after touching model artifacts or feature order.
2. Run `python ml/evaluate_route_forecaster.py` after changing training, features, or forecasting logic.
3. Run `python utils/real_data_audit.py` after changing schema, ingestion, prediction persistence, or drift handling.
4. Run the relevant CLI wrapper (`data/import_quotes.py`, `pipeline/build_forecast_dataset.py`, `app/compare_external_benchmark.py`) when changing CSV import or forecast export behavior.

---

*Testing analysis: 2026-03-26*
