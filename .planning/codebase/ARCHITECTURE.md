# Architecture Documentation

## Pattern

**Pipeline + Service Architecture** — a multi-model ML pipeline with a real-time streaming dashboard. The system has two distinct tracks:

1. **Observable Data Pipeline**: Fetches route observations from public APIs, engineers features, and runs predictions (XGBoost). Designed to ingest *only* observed data (no fabricated operational fields).

2. **Route Forecaster Pipeline**: A separate GradientBoostingRegressor trained on quote history or external market benchmarks (Compass/Xeneta) for 14-20 day cost forecasting with residual-blend prediction strategy.

A Flask + SSE streaming dashboard provides a live market tick simulator with real-time ML predictions.

## Layers

| Directory | Role |
|-----------|------|
| `app/` | Flask web application: API routes, SSE streaming, live tick engine, route forecasting, real-time prediction |
| `data/` | Data acquisition layer: fetches from FRED macroeconomic API, Open-Meteo weather/marine APIs, imports CSV quotes |
| `ml/` | Model training and evaluation: XGBoost benchmark model, GradientBoosting route forecaster, evaluation scripts |
| `pipeline/` | Feature engineering, training dataset construction, benchmark management, orchestration of fetch→feature→predict flow |
| `scripts/` | CLI entry points (thin wrappers that delegate to modules). One-time migration script (`fix_paths.py`) |
| `utils/` | Audit utility for inspecting data quality, drift, and forecast duplicates |
| `skills/` | Senior data scientist skill pack (reference docs, experiment/feature/evaluation scripts) |

## Data Flow

### Stream 1: Observable Real-Data Pipeline

```
data/real_data_fetcher.py
  └─ RealDataFetcher.fetch_watchlist_observations()
      ├─ Queries Open-Meteo weather API (wind, visibility, precipitation, pressure)
      ├─ Queries Open-Meteo marine API (wave height, direction, period)
      ├─ Computes distance_nm from PORT_DATABASE (Haversine)
      └─ Saves to SQLite table: route_observations

pipeline/real_data_feature_engineering.py
  └─ RealDataFeatureEngineer.engineer_features()
      ├─ Derived: weather_risk_total, wind_risk, port_efficiency_diff,
      │  congestion_pressure, fuel_cost_avg, is_peak_season, compound_friction
      └─ Returns DataFrame with ~20 engineered features

app/real_time_predictor.py
  └─ RealTimePredictor.run_predictions()
      ├─ Loads observations from route_observations
      ├─ Prepares features via RealDataFeatureEngineer
      ├─ Clips to training ranges (drift detection)
      ├─ Predicts 6 targets: shipping_price, delay_days, route_efficiency,
      │  port_efficiency, cost_per_teu, total_risk_score
      └─ Saves to SQLite table: route_predictions

pipeline/real_data_pipeline.py
  └─ RealDataPipeline.run_once()
      └─ Orchestrates: fetch → predict → forecast
```

### Stream 2: Route Forecaster (Quote/Benchmark-Based)

```
data/fetch_fred_data.py
  └─ download_fred_freight_index()
      └─ Downloads Deep Sea Freight PPI (PCU483111483111) from FRED

pipeline/benchmark_manager.py
  └─ load_historical_benchmarks()
      └─ Seeds benchmark_lanes + benchmark_history tables with FRED-indexed prices

app/forecast_support.py
  ├─ QuoteHistoryImporter.import_csv()
  │    └─ Imports CSV quotes → quote_history table (with FX conversion)
  ├─ ExternalBenchmarkImporter.import_csv()
  │    └─ Imports benchmark CSVs → external_benchmark_predictions table
  ├─ PublicBenchmarkSync.sync_all()
  │    └─ Downloads from Compass/Xeneta → market_rate_history table
  └─ build_training_dataset()
       ├─ Joins quote_history + market_rate_history
       ├─ Builds lag features (1d, 5d), rolling stats (7d/14d/28d), volatility, momentum
       ├─ Attaches latest benchmark cost via merge_asof
       └─ Returns training DataFrame with ~25 numeric features + 4 categorical

ml/train_route_forecaster.py
  └─ train_forecaster_bundle()
      ├─ Residual-blend strategy: GradientBoostingRegressor on (y - baseline)
      ├─ Calibrates per-route interval widths
      └─ Saves joblib bundle → app/route_forecaster.joblib

app/forecast_routes.py
  └─ predict_forecaster_bundle()
      ├─ Generates 14-20 day forecasts
      ├─ Adds weather cost uplift, delay estimates, confidence scores
      └─ Persists to SQLite table: route_forecasts
```

### Stream 3: Live Streaming Dashboard

```
app/stream_engine.py
  └─ StreamEngine (singleton)
      ├─ _pipeline_loop(): generate_tick → predict_tick → check_accuracy → broadcast
      │   ├─ generate_tick(): mean-reverting random walk on benchmark_lanes prices
      │   ├─ predict_tick(): XGBoost prediction (14d/21d horizon) with EMA/MACD/RSI features
      │   └─ check_accuracy(): compares 14-tick-old predictions to current prices
      ├─ _retrain_scheduler(): weekly retrain (Sunday midnight)
      └─ SSE broadcast → all browser subscribers

app/app.py (Flask)
  ├─ GET / → Dashboard HTML (Chart.js + SSE)
  ├─ GET /stream → SSE endpoint
  ├─ GET /api/prices → current lane prices
  ├─ GET /api/stats → aggregate statistics
  ├─ GET /api/ticks → recent tick history
  ├─ GET /api/accuracy → prediction accuracy stats
  └─ POST /api/retrain → manual model retrain
```

## Key Abstractions

### Core Classes

| Class | File | Role |
|-------|------|------|
| `RealDataFetcher` | `data/real_data_fetcher.py:95` | Fetches weather/marine data from Open-Meteo, builds route observations, manages SQLite schema (7+ tables) |
| `RealDataFeatureEngineer` | `pipeline/real_data_feature_engineering.py:23` | Engineers ~20 features from raw observations (weather interactions, congestion, fuel, seasonal) |
| `RealTimePredictor` | `app/real_time_predictor.py:41` | Loads XGBoost models, prepares features, predicts 6 targets, clips to training ranges, persists predictions |
| `RealDataPipeline` | `pipeline/real_data_pipeline.py:24` | Orchestrator: fetch → predict → forecast in one pass |
| `StreamEngine` | `app/stream_engine.py:135` | Singleton: generates simulated ticks, runs predictions, tracks accuracy, broadcasts SSE events, auto-retrains |
| `FxRateProvider` | `app/forecast_support.py:220` | Fetches live FX rates from frankfurter.app API for currency conversion |
| `QuoteHistoryImporter` | `app/forecast_support.py:281` | Imports CSV quote history with validation, FX conversion, staging table |
| `ExternalBenchmarkImporter` | `app/forecast_support.py:415` | Imports external provider benchmark CSVs |
| `PublicBenchmarkSync` | `app/forecast_support.py:497` | Downloads benchmark history from Compass/Xeneta |
| `ForecastWeatherBuilder` | `app/forecast_support.py:1210` | Builds weather features for future forecast windows |

### Key Functions

| Function | File | Role |
|----------|------|------|
| `build_training_dataset()` | `app/forecast_support.py:905` | Builds training data from quote_history + market_rate_history with time-series features |
| `train_forecaster_bundle()` | `app/forecast_support.py:1080` | Trains GradientBoosting with residual-blend strategy, calibrates intervals |
| `predict_forecaster_bundle()` | `app/forecast_support.py:1029` | Predicts with residual-blend: baseline + weighted residual, plus low/high intervals |
| `prepare_training_data()` | `pipeline/build_train_data.py:230` | Builds XGBoost training data from benchmark_history with quantitative finance features (EMA, MACD, RSI, ROC) |
| `train_model()` | `ml/train_model.py:66` | Trains XGBoost with temporal split, early stopping, naive baseline comparison |
| `sync_public_benchmarks()` | `app/forecast_support.py:594` | Downloads latest freight index data from public sources |

### Data Tables (SQLite)

| Table | Created By | Purpose |
|-------|-----------|---------|
| `route_observations` | `RealDataFetcher._init_database()` | Weather/marine/port snapshots per route |
| `route_predictions` | `RealDataFetcher._init_database()` | ML predictions for 6 targets |
| `quote_history` | `RealDataFetcher._init_database()` | Historical freight quotes with FX conversion |
| `market_rate_history` | `RealDataFetcher._init_database()` | Public benchmark rates (Compass/Xeneta) |
| `route_forecasts` | `RealDataFetcher._init_database()` | 14-20 day route cost forecasts |
| `external_benchmark_predictions` | `RealDataFetcher._init_database()` | Third-party provider comparisons |
| `benchmark_lanes` | `benchmark_manager.py` | Route lane definitions |
| `benchmark_history` | `benchmark_manager.py` | Historical benchmark prices (FRED-indexed) |
| `live_ticks` | `stream_engine.py` | Simulated market tick stream |
| `live_predictions` | `stream_engine.py` | Real-time ML predictions |
| `prediction_accuracy` | `stream_engine.py` | Accuracy tracking (pred vs actual) |
| `retrain_log` | `stream_engine.py` | Model retraining history |

## Entry Points

### Web Application
```bash
python app/app.py                    # Flask dashboard on :5001 with SSE streaming
```

### Training
```bash
python ml/train_model.py             # Train XGBoost benchmark model
python ml/train_route_forecaster.py  # Train GradientBoosting route forecaster
python scripts/train_route_forecaster.py  # Same via scripts wrapper
```

### Pipeline
```bash
python pipeline/real_data_pipeline.py   # Run one-shot: fetch → predict → forecast
python pipeline/build_train_data.py     # Build training dataset from benchmark_history
python pipeline/benchmark_manager.py    # Init tables, load FRED data, check sources
```

### Data Import
```bash
python data/real_data_fetcher.py       # Fetch route observations from Open-Meteo
python data/fetch_fred_data.py         # Download FRED freight index
python data/import_quotes.py <csv>     # Import quote history CSV
python scripts/import_quotes.py <csv>  # Same via scripts wrapper
python scripts/sync_public_benchmarks.py  # Download Compass/Xeneta benchmarks
```

### Evaluation & Audit
```bash
python ml/evaluate_route_forecaster.py       # Evaluate route forecaster
python ml/evaluate_route_forecaster.py --sync-public  # Sync + evaluate
python utils/real_data_audit.py              # Full data quality audit
python scripts/real_data_audit.py            # Same via scripts wrapper
python app/compare_external_benchmark.py     # Compare forecasts vs external providers
python ml/model_health_check.py              # Model health diagnostics
```

### Forecasting
```bash
python app/forecast_routes.py              # Generate 14-20 day route forecasts
python pipeline/build_forecast_dataset.py  # Build train or future forecast CSVs
```
