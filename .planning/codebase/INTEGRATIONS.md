# External Integrations

**Analysis Date:** 2026-03-26

## APIs & External Services

**Weather & Marine Forecasting:**
- Open-Meteo Forecast API - Supplies port weather observations and future forecast features for route scoring
  - Implementation: `data/real_data_fetcher.py` calls `https://api.open-meteo.com/v1/forecast`; `app/forecast_support.py` reuses it through `ForecastWeatherBuilder`
  - SDK/Client: `requests`
  - Auth: None detected
- Open-Meteo Marine API - Supplies wave-height and marine conditions for route risk and future forecast uplift
  - Implementation: `data/real_data_fetcher.py` calls `https://marine-api.open-meteo.com/v1/marine`; `app/forecast_support.py` caches results per port/day horizon
  - SDK/Client: `requests`
  - Auth: None detected

**Macroeconomic Benchmark Data:**
- FRED CSV endpoint for series `PCU483111483111` - Provides public freight index history used to seed `benchmark_history`
  - Implementation: `data/fetch_fred_data.py` downloads `https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCU483111483111`; `pipeline/benchmark_manager.py` transforms it into weekly lane benchmarks
  - SDK/Client: `pandas.read_csv` over HTTPS
  - Auth: None detected

**Freight Benchmark Provider:**
- CompassFT / Xeneta public benchmark history - Supplies route-level benchmark histories for planner training and evaluation
  - Implementation: `app/forecast_support.py` calls `https://www.compassft.com/wp-admin/admin-ajax.php` and stores results in `market_rate_history`
  - SDK/Client: `requests.Session`
  - Auth: No credentials detected; only a browser-style `User-Agent` header is set

**Foreign Exchange Rates:**
- Frankfurter API - Converts imported quote currencies into USD for the planner dataset
  - Implementation: `FxRateProvider` in `app/forecast_support.py` calls `https://api.frankfurter.app/{quote_date}`
  - SDK/Client: `requests`
  - Auth: None detected

**Frontend Assets:**
- Google Fonts - Loads `JetBrains Mono` and `Inter` in the HTML served by `app/app.py`
  - SDK/Client: browser `<link>` tag
  - Auth: Not applicable
- jsDelivr CDN for Chart.js - Loads dashboard charting code in `app/app.py`
  - SDK/Client: browser `<script>` tag
  - Auth: Not applicable

**File Imports:**
- Quote CSV import - Loads private or local quote history into SQLite through `data/import_quotes.py` and `QuoteHistoryImporter` in `app/forecast_support.py`
  - SDK/Client: local CSV via `pandas.read_csv`
  - Auth: Not applicable
- External benchmark CSV import - Loads third-party benchmark forecasts via `app/compare_external_benchmark.py` and `ExternalBenchmarkImporter` in `app/forecast_support.py`
  - SDK/Client: local CSV via `pandas.read_csv`
  - Auth: Not applicable

## Data Storage

**Databases:**
- SQLite database at `data/shipments.db`
  - Connection: direct path constants in `data/real_data_fetcher.py`, `app/app.py`, `app/stream_engine.py`, `pipeline/benchmark_manager.py`, `pipeline/build_train_data.py`, `app/real_time_predictor.py`, and `utils/real_data_audit.py`
  - Client: Python `sqlite3`
  - Main tables: `route_watchlist`, `route_observations`, `route_predictions`, `quote_history`, `market_rate_history`, `route_forecasts`, `external_benchmark_predictions`, `benchmark_lanes`, `benchmark_history`, and live-stream tables created in `app/stream_engine.py`
- Additional DB file committed at `app/shipments.db`
  - Connection: not used by the current `DB_PATH` constants, which point to `data/shipments.db`
  - Client: Not applicable

**File Storage:**
- Local filesystem only
- Model artifacts: `ml/benchmark_model.joblib`, `ml/benchmark_features.joblib`, `app/route_forecaster.joblib`
- Generated planner datasets and metrics: `app/route_forecast_training_dataset.csv`, `app/route_forecast_future_dataset.csv`, `app/route_forecaster_metrics.json`

**Caching:**
- In-memory only
- Distance cache: `DISTANCE_CACHE` in `data/real_data_fetcher.py`
- FX cache: `FxRateProvider._cache` in `app/forecast_support.py`
- Weather payload caches: `ForecastWeatherBuilder._weather_cache` and `_marine_cache` in `app/forecast_support.py`

## Authentication & Identity

**Auth Provider:**
- None
  - Implementation: No user login, OAuth flow, API token exchange, JWT handling, or secret-backed provider integration was detected under `E:\MLCollege\real data`

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- Console logging and CLI print statements in `pipeline/real_data_pipeline.py`, `pipeline/benchmark_manager.py`, `ml/train_model.py`, `ml/evaluate_route_forecaster.py`, and `data/fetch_fred_data.py`
- Audit/inspection tooling in `utils/real_data_audit.py`

## CI/CD & Deployment

**Hosting:**
- No managed hosting configuration detected
- Local Flask app in `app/app.py` serves on `0.0.0.0:5001`

**CI Pipeline:**
- None detected; no `.github/workflows`, Docker build files, or package build metadata were found

## Environment Configuration

**Required env vars:**
- None detected
- Configuration is path- and constant-based inside `data/real_data_fetcher.py`, `app/forecast_support.py`, `ml/train_model.py`, and `app/app.py`

**Secrets location:**
- Not applicable based on the current repo scan

## Webhooks & Callbacks

**Incoming:**
- None for third-party services
- Local HTTP interface exposed by `app/app.py`:
  - `GET /api/prices`
  - `GET /api/stats`
  - `GET /api/ticks`
  - `GET /api/accuracy`
  - `GET /api/retrain_log`
  - `POST /api/retrain`
  - `GET /stream` for server-sent events
  - `GET /` for the embedded dashboard

**Outgoing:**
- No webhook or callback emitters detected
- Outbound integrations are pull-based HTTP requests and local CSV imports only

---

*Integration audit: 2026-03-26*
