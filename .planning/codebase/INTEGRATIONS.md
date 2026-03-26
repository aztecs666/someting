# External Integrations

## External APIs

### Open-Meteo Weather Forecast API
- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **File**: `data/real_data_fetcher.py:559-574`
- **Auth**: None required (free tier)
- **Usage**: Fetches hourly weather data (temperature, wind speed, visibility, precipitation, pressure) for origin/destination ports
- **Params**: `latitude`, `longitude`, `hourly` (temperature_2m, wind_speed_10m, wind_direction_10m, visibility, precipitation, pressure_msl), `forecast_days` (default 2)

### Open-Meteo Marine API
- **Endpoint**: `https://marine-api.open-meteo.com/v1/marine`
- **File**: `data/real_data_fetcher.py:576-591`
- **Auth**: None required (free tier)
- **Usage**: Fetches hourly marine data (wave height, wave direction, wave period) for port locations
- **Params**: `latitude`, `longitude`, `hourly` (wave_height, wave_direction, wave_period), `forecast_days` (default 2)

### FRED (Federal Reserve Economic Data)
- **Endpoint**: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCU483111483111`
- **File**: `data/fetch_fred_data.py:23-24`
- **Auth**: None required (direct CSV download)
- **Usage**: Downloads Producer Price Index: Deep Sea Freight Transportation (series `PCU483111483111`) for macroeconomic freight cost trends
- **Data**: Monthly index values, interpolated to weekly for model input

### Frankfurter FX Rate API
- **Endpoint**: `https://api.frankfurter.app/{quote_date}`
- **File**: `app/forecast_support.py:233-238`
- **Auth**: None required (free)
- **Usage**: Currency conversion for quote history imports (converts foreign currency to USD)
- **Params**: `from` (source currency), `to` (USD)
- **Class**: `FxRateProvider` with in-memory cache

### Compass/Xeneta Freight Benchmarks
- **Endpoint**: `https://www.compassft.com/wp-admin/admin-ajax.php`
- **File**: `app/forecast_support.py:504-513` (`PublicBenchmarkSync._download_route_history`)
- **Auth**: None required (public data via AJAX endpoint)
- **Usage**: Downloads historical freight rate benchmarks for 8 trade routes
- **Params**: `id` (benchmark_id), `action` (compassft_downloaddatas), `t` (timestamp cache-buster)
- **Benchmark slugs**: `xsicfene`, `xsicfese`, `xsicfeuw`, `xsicnefe`, `xsicnese`, `xsicneue`, `xsicuene`, `xsicuwfe`
- **Reference URL**: `https://www.compassft.com/indice/{slug}/`

## Databases

### SQLite — `data/shipments.db`
- **File**: `data/real_data_fetcher.py:21` (`DB_PATH`)
- **Connection**: `sqlite3.connect()` with WAL journal mode (`app/stream_engine.py:69-72`)
- **Tables**:
  - `ports` — 25 global port reference with lat/lon coordinates (hardcoded `PORT_DATABASE` in `data/real_data_fetcher.py:31-57`)
  - `route_watchlist` — 8 monitored trade lanes (`data/real_data_fetcher.py:59-68`)
  - `route_observations` — 80+ field observation snapshots with weather, port, and operational features (`data/real_data_fetcher.py:256-331`)
  - `route_predictions` — ML predictions per observation (shipping price, delay, efficiency, risk) (`data/real_data_fetcher.py:335-354`)
  - `quote_history` — Imported freight quotes with USD conversion, carrier, transit time, surcharges (`data/real_data_fetcher.py:394-427`)
  - `quote_history_staging` — Raw CSV staging for quote imports (`data/real_data_fetcher.py:381-391`)
  - `market_rate_history` — Synced Compass/Xeneta benchmarks with source URLs (`data/real_data_fetcher.py:429-455`)
  - `route_forecasts` — 14-20 day forecasts with confidence intervals, weather uplift, risk rankings (`data/real_data_fetcher.py:457-486`)
  - `external_benchmark_predictions` — Imported external benchmark comparisons with raw payloads (`data/real_data_fetcher.py:356-379`)
  - `live_ticks` — Simulated market ticks (price, change, volume, source) (`app/stream_engine.py:80-93`)
  - `live_predictions` — XGBoost predictions per tick (14d, 21d forecasts with confidence bands) (`app/stream_engine.py:95-107`)
  - `prediction_accuracy` — Prediction vs actual comparison tracking (MAE, MAPE) (`app/stream_engine.py:109-119`)
  - `retrain_log` — Model retraining history (timestamp, samples, MAE, R2) (`app/stream_engine.py:121-129`)
- **Also duplicated at**: `app/shipments.db`, `real data/shipments.db`, `real data/engineered_shipments.db`

### SQLite — `data/shipments.db` (Legacy Benchmark Tables)
- **Referenced in**: `pipeline/build_train_data.py:59-71`
- **Tables** (created by legacy scripts):
  - `benchmark_lanes` — Lane definitions with origin/destination ports, container types
  - `benchmark_history` — Historical price data with source tracking (`public_index`, `synthetic_seed`)

## Auth Providers
- **None** — No authentication, OAuth, or API key management found. All external APIs use free/public endpoints.

## Webhooks/Services
- **Server-Sent Events (SSE)** — Internal streaming mechanism (`app/stream_engine.py`)
  - Event types: `update` (tick+prediction+accuracy), `retrain`, `system`, `heartbeat`
  - Subscribers managed via `queue.Queue` with threading (`_subscribers`, `_broadcast`)
- **No external webhook integrations** found

## Data Sources

### CSV Import Files
- **Quote history CSVs** — Imported via `QuoteHistoryImporter.import_csv()` (`app/forecast_support.py:287`)
  - Required columns: `quote_date`, `departure_window_start`, `route_name`, `origin_port`, `destination_port`, `container_type`, `quoted_cost`, `currency`, `source`
  - CLI: `scripts/import_quotes.py <csv_path> [--source] [--db-path]`
- **External benchmark CSVs** — Imported via `ExternalBenchmarkImporter.import_csv()` (`app/forecast_support.py:420`)
  - Required columns: `forecast_date`, `route_name`, `container_type`, `predicted_cost`
  - Optional: `provider`, `predicted_delay_days`, `predicted_at`, `origin_port`, `destination_port`
  - CLI: `app/compare_external_benchmark.py --import-csv <path> [--provider]`

### Generated Datasets
- `app/route_forecast_training_dataset.csv` — Training dataset built from quote_history + market_rate_history
- `app/route_forecast_future_dataset.csv` — Future forecast features with weather data

### Port Reference Database (Hardcoded)
- 25 ports with lat/lon coordinates: Singapore, New York, Los Angeles, Shanghai, Dubai, Mumbai, Hamburg, Tokyo, Busan, Rotterdam, Hong Kong, Shenzhen, Ningbo, Antwerp, Long Beach, Santos, Sydney, Melbourne, Auckland, Chennai, Colombo, Port Klang, Bangkok, Ho Chi Minh, Manila (`data/real_data_fetcher.py:31-57`)
