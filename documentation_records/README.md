# Route Planning Forecaster

This project is now framed around a realistic internship constraint:

- private quote history is optional
- external benchmark history is the fallback training source when quotes are unavailable
- only real data should be used for training the planner

## What the project does

- builds route-planning training data from:
  - `quote_history` when you have real quotes
  - `market_rate_history` when you sync or import external benchmark series
- trains a 14-20 day route forecaster with low/base/high cost bands
- adds public-weather uplift and delay heuristics
- stores route forecasts in SQLite

## Important honesty rules

- if quote history is missing, the planner can train from real external benchmark history after you sync or import it
- no synthetic or fabricated commercial targets should be used for planner training
- external benchmark history is still a proxy for planning, not a replacement for private quote history
- the free weather source only covers 16 days, so 17-20 day forecasts include a horizon-gap penalty

## Database tables

Main planner tables:

- `quote_history`
- `market_rate_history`
- `route_forecasts`
- `external_benchmark_predictions`

Observable route snapshot tables:

- `route_watchlist`
- `route_observations`
- `route_predictions`

## Install

```bash
pip install -r requirements.txt
```

## Common commands

Import real quote history when available:

```bash
python scripts/import_quotes.py path\to\quotes.csv
```

Build planner training data:

```bash
python scripts/build_forecast_dataset.py --mode train
```

Train the planner:

```bash
python scripts/train_route_forecaster.py
```

Sync public benchmark history into `market_rate_history`:

```bash
python scripts/sync_public_benchmarks.py
```

Generate 14-20 day forecasts:

```bash
python scripts/forecast_routes.py
```

Evaluate the planner against the latest internet-synced benchmark history:

```bash
python scripts/evaluate_route_forecaster.py --sync-public
```

Import external forecast benchmarks and compare them:

```bash
python scripts/compare_external_benchmark.py --import-csv path\to\provider.csv --provider Freightos
python scripts/compare_external_benchmark.py --provider Freightos
```

Audit current state:

```bash
python scripts/real_data_audit.py
```

Run the observable snapshot pipeline:

```bash
python pipeline/real_data_pipeline.py
```

## Observable predictor status

The observable snapshot pipeline has two distinct stages:

- observation fetch and storage from public APIs
- optional legacy XGBoost snapshot prediction over those observations

The second stage requires these artifacts in `ml/`:

- `xgb_models.joblib`
- `xgb_features.joblib`

If those files are absent, `python pipeline/real_data_pipeline.py` still fetches observations and can still run the route forecaster, but it will explicitly report that the observable predictor was skipped. This is the current expected behavior in this repository.

There is not yet a documented training/export command for those legacy observable predictor artifacts, so treat that stage as optional until such a command is added.

## Training modes

`quote_history`

- best option
- uses actual quote rows with 14-20 day lead times

`external_benchmark_history`

- used when `market_rate_history` is available
- trains on external benchmark series as a planning proxy

The planner can train in a mixed real-data mode when you have only a small quote sample and need additional real external benchmark rows to reach a usable training size.

## Quote CSV contract

Required columns:

- `quote_date`
- `departure_window_start`
- `route_name`
- `origin_port`
- `destination_port`
- `container_type`
- `quoted_cost`
- `currency`
- `source`

Optional columns:

- `departure_window_end`
- `carrier`
- `transit_time_days`
- `surcharge_total`

## Output shape

Each `route_forecasts` row includes:

- `forecast_date`
- `departure_window_start`
- `departure_window_end`
- `route_name`
- `origin_port`
- `destination_port`
- `container_type`
- `expected_low_cost`
- `expected_base_cost`
- `expected_high_cost`
- `weather_cost_uplift`
- `expected_delay_days`
- `severe_weather_probability`
- `confidence_score`

## Current limitation

If you do not have private quote history, the planner can still train and forecast from real external benchmark history, but the model output should be presented as an external-benchmark planning proxy rather than as direct commercial quote prediction. If both `quote_history` and `market_rate_history` are empty, the planner should refuse training.
