import argparse
import io
import json
import math
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3
import uuid
from datetime import date, datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from data.real_data_fetcher import (
    DB_PATH,
    EXTERNAL_BENCHMARKS_TABLE,
    MARKET_RATE_HISTORY_TABLE,
    PORT_DATABASE,
    QUOTE_HISTORY_STAGING_TABLE,
    QUOTE_HISTORY_TABLE,
    ROUTE_FORECASTS_TABLE,
    RealDataFetcher,
)

WORKING_CURRENCY = "USD"
BENCHMARK_PROVIDER = "Compass/Xeneta"
BENCHMARK_SOURCE_URL = "https://www.compassft.com"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_PATH = os.path.join(BASE_DIR, "route_forecaster.joblib")
METRICS_PATH = os.path.join(BASE_DIR, "route_forecaster_metrics.json")
TRAINING_DATASET_PATH = os.path.join(BASE_DIR, "route_forecast_training_dataset.csv")
FUTURE_DATASET_PATH = os.path.join(BASE_DIR, "route_forecast_future_dataset.csv")

QUOTE_REQUIRED_COLUMNS = [
    "quote_date",
    "departure_window_start",
    "route_name",
    "origin_port",
    "destination_port",
    "container_type",
    "quoted_cost",
    "currency",
    "source",
]

BENCHMARK_REQUIRED_COLUMNS = [
    "forecast_date",
    "route_name",
    "container_type",
    "predicted_cost",
]

PUBLIC_BENCHMARK_ROUTES = [
    {
        "route_name": "Far East to North Europe",
        "slug": "xsicfene",
        "benchmark_id": 5043,
        "origin_port": "Shanghai",
        "destination_port": "Rotterdam",
        "container_type": "FEU",
    },
    {
        "route_name": "Far East to South America East Coast",
        "slug": "xsicfese",
        "benchmark_id": 5045,
        "origin_port": "Shanghai",
        "destination_port": "Santos",
        "container_type": "FEU",
    },
    {
        "route_name": "Far East to US West Coast",
        "slug": "xsicfeuw",
        "benchmark_id": 5047,
        "origin_port": "Shanghai",
        "destination_port": "Los Angeles",
        "container_type": "FEU",
    },
    {
        "route_name": "North Europe to Far East",
        "slug": "xsicnefe",
        "benchmark_id": 5049,
        "origin_port": "Rotterdam",
        "destination_port": "Shanghai",
        "container_type": "FEU",
    },
    {
        "route_name": "North Europe to South America East Coast",
        "slug": "xsicnese",
        "benchmark_id": 5051,
        "origin_port": "Rotterdam",
        "destination_port": "Santos",
        "container_type": "FEU",
    },
    {
        "route_name": "North Europe to US East Coast",
        "slug": "xsicneue",
        "benchmark_id": 5053,
        "origin_port": "Rotterdam",
        "destination_port": "New York",
        "container_type": "FEU",
    },
    {
        "route_name": "US East Coast to North Europe",
        "slug": "xsicuene",
        "benchmark_id": 5055,
        "origin_port": "New York",
        "destination_port": "Rotterdam",
        "container_type": "FEU",
    },
    {
        "route_name": "US West Coast to Far East",
        "slug": "xsicuwfe",
        "benchmark_id": 5057,
        "origin_port": "Los Angeles",
        "destination_port": "Shanghai",
        "container_type": "FEU",
    },
]

NUMERIC_FEATURES = [
    "distance_nm",
    "lead_time_days",
    "feature_month",
    "feature_quarter",
    "feature_week_of_year",
    "feature_day_of_week",
    "departure_month",
    "departure_quarter",
    "departure_week_of_year",
    "departure_day_of_week",
    "latest_observed_benchmark_cost",
    "lag_1d_cost",
    "lag_5d_cost",
    "rolling_mean_cost_7d",
    "rolling_mean_cost_28d",
    "rolling_median_cost_7d",
    "rolling_median_cost_14d",
    "rolling_median_cost_28d",
    "rolling_volatility_14d",
    "rolling_volatility_28d",
    "week_over_week_change",
    "momentum_14d",
    "history_count_28d",
    "lane_history_coverage_pct",
    "data_staleness_days",
]

CATEGORICAL_FEATURES = [
    "route_name",
    "origin_port",
    "destination_port",
    "container_type",
]

FUTURE_WEATHER_COLUMNS = [
    "forecast_avg_wind_speed",
    "forecast_max_wave_height",
    "forecast_low_visibility_frequency",
    "forecast_precipitation_total",
    "forecast_severe_weather_probability",
    "forecast_weather_volatility",
    "forecast_weather_data_coverage_pct",
    "forecast_horizon_gap_days",
]

TRAINING_MODE_QUOTE = "quote_history"
TRAINING_MODE_EXTERNAL = "external_benchmark_history"
MIN_TRAINING_ROWS = 150
RESIDUAL_BLEND_WEIGHT = 0.3
INTERVAL_CALIBRATION_QUANTILE = 0.7
INTERVAL_CALIBRATION_TEST_FRACTION = 0.15
_DISTANCE_CACHE = {}


def connect(db_path=DB_PATH):
    return sqlite3.connect(db_path)


def _baseline_cost_series(frame):
    if "latest_observed_benchmark_cost" in frame.columns:
        baseline = pd.to_numeric(frame["latest_observed_benchmark_cost"], errors="coerce")
    else:
        baseline = pd.Series(np.nan, index=frame.index, dtype=float)

    if baseline.isna().all() and "lag_1d_cost" in frame.columns:
        baseline = pd.to_numeric(frame["lag_1d_cost"], errors="coerce")

    return baseline.ffill().bfill()


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _primary_training_mode(training_modes):
    training_modes = [str(mode) for mode in training_modes if str(mode).strip()]
    if TRAINING_MODE_QUOTE in training_modes:
        return TRAINING_MODE_QUOTE
    if training_modes:
        return training_modes[0]
    return "unknown"


def describe_training_provenance(provenance):
    if not provenance:
        return "Training provenance unavailable."

    primary_mode = provenance.get("primary_training_mode", "unknown")
    quote_rows = _safe_int(provenance.get("quote_history_rows"))
    market_rows = _safe_int(provenance.get("market_rate_history_rows"))
    label = (
        "Benchmark-backed market forecaster"
        if provenance.get("is_benchmark_only")
        else "Quote-backed forecaster"
    )
    return (
        f"{label} | primary mode: {primary_mode} | "
        f"quote_history rows: {quote_rows} | market_rate_history rows: {market_rows}"
    )


def _route_interval_key(route_name, container_type):
    return f"{str(route_name)}||{str(container_type)}"


def _blend_prediction_from_residual(baseline_series, residual_prediction, blend_weight):
    baseline_series = pd.Series(baseline_series, copy=False)
    residual_prediction = pd.Series(residual_prediction, index=baseline_series.index, dtype=float)
    return baseline_series + float(blend_weight) * residual_prediction


def _interval_width_series(frame, route_interval_widths, global_interval_width):
    widths = []
    for row in frame[["route_name", "container_type"]].itertuples(index=False):
        key = _route_interval_key(row.route_name, row.container_type)
        widths.append(float(route_interval_widths.get(key, global_interval_width)))
    return pd.Series(widths, index=frame.index, dtype=float)


class FxRateProvider:
    def __init__(self):
        self._cache = {}

    def get_rate_to_usd(self, currency, quote_date):
        currency = str(currency).upper()
        if currency == WORKING_CURRENCY:
            return 1.0

        cache_key = (currency, str(quote_date))
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = f"https://api.frankfurter.app/{quote_date}"
        params = {"from": currency, "to": WORKING_CURRENCY}
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rate = float(payload["rates"][WORKING_CURRENCY])
        self._cache[cache_key] = rate
        return rate


def ensure_schema(db_path=DB_PATH):
    RealDataFetcher(db_path)


def _distance_nm(origin_port, destination_port):
    cache_key = (origin_port, destination_port)
    if cache_key in _DISTANCE_CACHE:
        return _DISTANCE_CACHE[cache_key]

    if origin_port not in PORT_DATABASE or destination_port not in PORT_DATABASE:
        return np.nan

    origin = PORT_DATABASE[origin_port]
    destination = PORT_DATABASE[destination_port]
    lat1 = math.radians(origin["lat"])
    lon1 = math.radians(origin["lon"])
    lat2 = math.radians(destination["lat"])
    lon2 = math.radians(destination["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    nm_distance = float(6371.0 * c * 0.539957)
    _DISTANCE_CACHE[cache_key] = nm_distance
    _DISTANCE_CACHE[(destination_port, origin_port)] = nm_distance
    return nm_distance


def _unsupported_lane_summary(frame):
    if frame is None or frame.empty:
        return []

    lane_cols = ["route_name", "origin_port", "destination_port", "container_type"]
    available_cols = [col for col in lane_cols if col in frame.columns]
    if len(available_cols) < 3 or "distance_nm" not in frame.columns:
        return []

    invalid = frame.loc[
        pd.to_numeric(frame["distance_nm"], errors="coerce").isna(),
        available_cols,
    ]
    if invalid.empty:
        return []

    invalid = invalid.drop_duplicates().fillna("UNKNOWN")
    summaries = []
    for row in invalid.itertuples(index=False):
        row_map = dict(zip(available_cols, row))
        summaries.append(
            f"{row_map.get('route_name', 'UNKNOWN')} "
            f"({row_map.get('origin_port', 'UNKNOWN')} -> {row_map.get('destination_port', 'UNKNOWN')}, "
            f"{row_map.get('container_type', 'UNKNOWN')})"
        )
    return summaries


def _raise_if_unsupported_lanes(frame, context_label):
    unsupported = _unsupported_lane_summary(frame)
    if unsupported:
        joined = "; ".join(unsupported[:5])
        raise ValueError(
            f"Unsupported lane distance mapping detected in {context_label}: {joined}. "
            "Add explicit port coverage before training or forecasting this lane."
        )


def _normalize_dataframe_columns(df):
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


class QuoteHistoryImporter:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.fx = FxRateProvider()
        ensure_schema(db_path)

    def import_csv(self, csv_path, source_override=None):
        df = _normalize_dataframe_columns(pd.read_csv(csv_path))
        import_batch_id = str(uuid.uuid4())

        conn = connect(self.db_path)
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute(
                f"""
                INSERT INTO {QUOTE_HISTORY_STAGING_TABLE} (import_batch_id, source_file, raw_row_json)
                VALUES (?, ?, ?)
                """,
                (
                    import_batch_id,
                    os.path.abspath(csv_path),
                    json.dumps(row.to_dict(), default=str),
                ),
            )

        missing_cols = [col for col in QUOTE_REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            conn.rollback()
            conn.close()
            raise ValueError(f"Missing required quote columns: {missing_cols}")

        df["quote_date"] = pd.to_datetime(df["quote_date"], errors="coerce").dt.date
        df["departure_window_start"] = pd.to_datetime(
            df["departure_window_start"], errors="coerce"
        ).dt.date
        if "departure_window_end" in df.columns:
            df["departure_window_end"] = pd.to_datetime(
                df["departure_window_end"], errors="coerce"
            ).dt.date
        else:
            df["departure_window_end"] = df["departure_window_start"]

        df["quoted_cost"] = pd.to_numeric(df["quoted_cost"], errors="coerce")
        df["transit_time_days"] = pd.to_numeric(
            df.get("transit_time_days"), errors="coerce"
        )
        df["surcharge_total"] = pd.to_numeric(
            df.get("surcharge_total"), errors="coerce"
        )

        valid_mask = (
            df["quote_date"].notna()
            & df["departure_window_start"].notna()
            & df["route_name"].astype(str).str.strip().ne("")
            & df["container_type"].astype(str).str.strip().ne("")
            & df["quoted_cost"].notna()
            & df["origin_port"].astype(str).str.strip().ne("")
            & df["destination_port"].astype(str).str.strip().ne("")
        )
        rejected = int((~valid_mask).sum())
        valid = df.loc[valid_mask].copy()

        if valid.empty:
            conn.commit()
            conn.close()
            raise ValueError("No valid quote rows found after validation.")

        inserted = 0
        for row in valid.itertuples(index=False):
            currency = str(row.currency).upper()
            rate = self.fx.get_rate_to_usd(currency, row.quote_date.isoformat())
            quoted_cost_usd = float(row.quoted_cost) * rate
            surcharge_total = (
                float(row.surcharge_total) if not pd.isna(row.surcharge_total) else None
            )
            surcharge_total_usd = surcharge_total * rate if surcharge_total is not None else None
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {QUOTE_HISTORY_TABLE} (
                    import_batch_id,
                    quote_date,
                    departure_window_start,
                    departure_window_end,
                    route_name,
                    origin_port,
                    destination_port,
                    container_type,
                    quoted_cost,
                    quoted_cost_usd,
                    currency,
                    fx_rate_to_usd,
                    carrier,
                    transit_time_days,
                    surcharge_total,
                    surcharge_total_usd,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_batch_id,
                    row.quote_date.isoformat(),
                    row.departure_window_start.isoformat(),
                    row.departure_window_end.isoformat() if row.departure_window_end else None,
                    str(row.route_name).strip(),
                    str(row.origin_port).strip(),
                    str(row.destination_port).strip(),
                    str(row.container_type).strip(),
                    float(row.quoted_cost),
                    quoted_cost_usd,
                    currency,
                    rate,
                    None
                    if "carrier" not in valid.columns or pd.isna(getattr(row, "carrier", None))
                    else str(row.carrier).strip(),
                    None if pd.isna(row.transit_time_days) else float(row.transit_time_days),
                    surcharge_total,
                    surcharge_total_usd,
                    source_override or str(row.source).strip(),
                ),
            )
            inserted += int(cursor.rowcount > 0)

        conn.commit()
        conn.close()
        return {
            "import_batch_id": import_batch_id,
            "source_file": os.path.abspath(csv_path),
            "rows_read": int(len(df)),
            "rows_valid": int(len(valid)),
            "rows_rejected": rejected,
            "rows_inserted": inserted,
        }


class ExternalBenchmarkImporter:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        ensure_schema(db_path)

    def import_csv(self, csv_path, provider_override=None):
        df = _normalize_dataframe_columns(pd.read_csv(csv_path))
        missing_cols = [col for col in BENCHMARK_REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required benchmark columns: {missing_cols}")

        df["forecast_date"] = pd.to_datetime(df["forecast_date"], errors="coerce").dt.date
        df["predicted_cost"] = pd.to_numeric(df["predicted_cost"], errors="coerce")
        if "predicted_delay_days" in df.columns:
            df["predicted_delay_days"] = pd.to_numeric(
                df["predicted_delay_days"], errors="coerce"
            )
        else:
            df["predicted_delay_days"] = np.nan

        if "provider" not in df.columns and provider_override is None:
            raise ValueError("Benchmark CSV must include provider or use --provider.")

        valid = df.loc[
            df["forecast_date"].notna()
            & df["route_name"].astype(str).str.strip().ne("")
            & df["container_type"].astype(str).str.strip().ne("")
            & df["predicted_cost"].notna()
        ].copy()
        if valid.empty:
            raise ValueError("No valid benchmark rows found.")

        conn = connect(self.db_path)
        cursor = conn.cursor()
        inserted = 0
        for _, row in valid.iterrows():
            provider = provider_override or str(row.get("provider", "")).strip()
            cursor.execute(
                f"""
                INSERT INTO {EXTERNAL_BENCHMARKS_TABLE} (
                    route_forecast_id,
                    observation_id,
                    provider,
                    forecast_date,
                    route_name,
                    origin_port,
                    destination_port,
                    container_type,
                    predicted_cost,
                    predicted_delay_days,
                    metric_name,
                    metric_value,
                    predicted_at,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    None,
                    provider,
                    row["forecast_date"].isoformat(),
                    str(row["route_name"]).strip(),
                    None if pd.isna(row.get("origin_port")) else str(row.get("origin_port")).strip(),
                    None if pd.isna(row.get("destination_port")) else str(row.get("destination_port")).strip(),
                    str(row["container_type"]).strip(),
                    float(row["predicted_cost"]),
                    None
                    if pd.isna(row["predicted_delay_days"])
                    else float(row["predicted_delay_days"]),
                    "predicted_cost",
                    float(row["predicted_cost"]),
                    None if pd.isna(row.get("predicted_at")) else str(row.get("predicted_at")),
                    json.dumps(row.to_dict(), default=str),
                ),
            )
            inserted += 1

        conn.commit()
        conn.close()
        return {"rows_inserted": inserted, "source_file": os.path.abspath(csv_path)}


class PublicBenchmarkSync:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        ensure_schema(db_path)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def _download_route_history(self, route_spec):
        response = self.session.get(
            f"{BENCHMARK_SOURCE_URL}/wp-admin/admin-ajax.php",
            params={
                "id": route_spec["benchmark_id"],
                "action": "compassft_downloaddatas",
                "t": f"{datetime.utcnow().timestamp():.6f}",
            },
            timeout=30,
        )
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        if df.empty or "Date" not in df.columns:
            raise ValueError(f"No benchmark history returned for {route_spec['route_name']}.")

        value_columns = [col for col in df.columns if col != "Date"]
        if not value_columns:
            raise ValueError(f"Missing benchmark value column for {route_spec['route_name']}.")

        df = df.rename(columns={"Date": "benchmark_date", value_columns[0]: "benchmark_cost"})
        df["benchmark_date"] = pd.to_datetime(df["benchmark_date"], errors="coerce").dt.date
        df["benchmark_cost"] = pd.to_numeric(df["benchmark_cost"], errors="coerce")
        df = df.loc[df["benchmark_date"].notna() & df["benchmark_cost"].notna()].copy()
        df["route_name"] = route_spec["route_name"]
        df["origin_port"] = route_spec["origin_port"]
        df["destination_port"] = route_spec["destination_port"]
        df["container_type"] = route_spec["container_type"]
        df["benchmark_slug"] = route_spec["slug"]
        df["benchmark_id"] = int(route_spec["benchmark_id"])
        return df

    def sync_all(self, routes=None):
        routes = routes or PUBLIC_BENCHMARK_ROUTES
        conn = connect(self.db_path)
        cursor = conn.cursor()
        inserted = 0
        history_rows = 0
        latest_dates = []

        for route_spec in routes:
            df = self._download_route_history(route_spec)
            history_rows += len(df)
            latest_dates.append(str(df["benchmark_date"].max()))
            source_url = f"{BENCHMARK_SOURCE_URL}/indice/{route_spec['slug']}/"

            for row in df.itertuples(index=False):
                cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO {MARKET_RATE_HISTORY_TABLE} (
                        provider,
                        benchmark_slug,
                        benchmark_id,
                        benchmark_date,
                        route_name,
                        origin_port,
                        destination_port,
                        container_type,
                        benchmark_cost,
                        benchmark_cost_usd,
                        currency,
                        source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        BENCHMARK_PROVIDER,
                        row.benchmark_slug,
                        int(row.benchmark_id),
                        row.benchmark_date.isoformat(),
                        row.route_name,
                        row.origin_port,
                        row.destination_port,
                        row.container_type,
                        float(row.benchmark_cost),
                        float(row.benchmark_cost),
                        WORKING_CURRENCY,
                        source_url,
                    ),
                )
                inserted += int(cursor.rowcount > 0)

        conn.commit()
        conn.close()
        return {
            "routes_synced": len(routes),
            "history_rows_seen": int(history_rows),
            "rows_upserted": int(inserted),
            "latest_history_date": max(latest_dates) if latest_dates else None,
        }


def sync_public_benchmarks(db_path=DB_PATH):
    return PublicBenchmarkSync(db_path).sync_all()


def load_quote_history(db_path=DB_PATH):
    ensure_schema(db_path)
    conn = connect(db_path)
    try:
        return pd.read_sql_query(
            f"SELECT * FROM {QUOTE_HISTORY_TABLE} ORDER BY quote_date, departure_window_start, quote_id",
            conn,
        )
    finally:
        conn.close()


def load_market_rate_history(db_path=DB_PATH):
    ensure_schema(db_path)
    conn = connect(db_path)
    try:
        return pd.read_sql_query(
            f"""
            SELECT *
            FROM {MARKET_RATE_HISTORY_TABLE}
            ORDER BY benchmark_date, route_name, market_rate_id
            """,
            conn,
        )
    finally:
        conn.close()


def _prepare_quote_history(quotes):
    if quotes is None or quotes.empty:
        return pd.DataFrame()

    prepared = quotes.copy()
    prepared["quote_date"] = pd.to_datetime(prepared["quote_date"], errors="coerce")
    prepared["departure_window_start"] = pd.to_datetime(
        prepared["departure_window_start"], errors="coerce"
    )
    prepared["departure_window_end"] = pd.to_datetime(
        prepared.get("departure_window_end"), errors="coerce"
    )
    prepared["quoted_cost_usd"] = pd.to_numeric(prepared["quoted_cost_usd"], errors="coerce")
    prepared = prepared.loc[
        prepared["quote_date"].notna()
        & prepared["departure_window_start"].notna()
        & prepared["quoted_cost_usd"].notna()
        & prepared["route_name"].astype(str).str.strip().ne("")
        & prepared["origin_port"].astype(str).str.strip().ne("")
        & prepared["destination_port"].astype(str).str.strip().ne("")
        & prepared["container_type"].astype(str).str.strip().ne("")
    ].copy()
    prepared["departure_window_end"] = prepared["departure_window_end"].fillna(
        prepared["departure_window_start"]
    )
    sort_cols = ["route_name", "container_type", "quote_date", "departure_window_start"]
    if "quote_id" in prepared.columns:
        sort_cols.append("quote_id")
    return prepared.sort_values(sort_cols).reset_index(drop=True)


def _prepare_market_history(history):
    if history is None or history.empty:
        return pd.DataFrame()

    prepared = history.copy()
    prepared["benchmark_date"] = pd.to_datetime(prepared["benchmark_date"], errors="coerce")
    prepared["benchmark_cost_usd"] = pd.to_numeric(
        prepared["benchmark_cost_usd"], errors="coerce"
    )
    prepared = prepared.loc[
        prepared["benchmark_date"].notna()
        & prepared["benchmark_cost_usd"].notna()
        & prepared["route_name"].astype(str).str.strip().ne("")
        & prepared["container_type"].astype(str).str.strip().ne("")
    ].copy()
    if "provider" not in prepared.columns:
        prepared["provider"] = BENCHMARK_PROVIDER
    prepared["provider"] = prepared["provider"].fillna(BENCHMARK_PROVIDER).astype(str)
    sort_cols = ["route_name", "container_type", "benchmark_date"]
    if "market_rate_id" in prepared.columns:
        sort_cols.append("market_rate_id")
    return prepared.sort_values(sort_cols).reset_index(drop=True)


def _add_cost_history_features(group_df, date_col, cost_col):
    group = group_df.sort_values(date_col).copy()
    group[date_col] = pd.to_datetime(group[date_col], errors="coerce")
    group[cost_col] = pd.to_numeric(group[cost_col], errors="coerce")
    history = group.set_index(date_col)[cost_col].astype(float).sort_index()
    lagged = history.shift(1)

    group["lag_1d_cost"] = lagged.values
    group["lag_5d_cost"] = lagged.shift(4).values
    group["rolling_mean_cost_7d"] = lagged.rolling("7D", min_periods=1).mean().values
    group["rolling_mean_cost_28d"] = lagged.rolling("28D", min_periods=1).mean().values
    group["rolling_median_cost_7d"] = lagged.rolling("7D", min_periods=1).median().values
    group["rolling_median_cost_14d"] = lagged.rolling("14D", min_periods=1).median().values
    group["rolling_median_cost_28d"] = lagged.rolling("28D", min_periods=1).median().values
    group["rolling_volatility_14d"] = lagged.rolling("14D", min_periods=2).std().values
    group["rolling_volatility_28d"] = lagged.rolling("28D", min_periods=2).std().values
    group["week_over_week_change"] = (lagged - lagged.shift(5)).values
    group["momentum_14d"] = (lagged - lagged.shift(10)).values
    group["history_count_28d"] = lagged.rolling("28D", min_periods=1).count().values
    coverage_cols = [
        "lag_1d_cost",
        "lag_5d_cost",
        "rolling_mean_cost_7d",
        "rolling_mean_cost_28d",
        "rolling_median_cost_7d",
        "rolling_median_cost_14d",
        "rolling_median_cost_28d",
        "rolling_volatility_14d",
        "rolling_volatility_28d",
        "week_over_week_change",
        "momentum_14d",
        "history_count_28d",
    ]
    group["lane_history_coverage_pct"] = group[coverage_cols].notna().mean(axis=1) * 100.0
    return group


def _attach_latest_benchmark_features(group_df, market_history):
    group = group_df.sort_values("quote_date").copy()
    group["latest_observed_benchmark_cost"] = group["lag_1d_cost"]
    group["data_staleness_days"] = np.nan

    if market_history is None or market_history.empty:
        return group

    benchmark_cols = ["benchmark_date", "benchmark_cost_usd"]
    merged = pd.merge_asof(
        group.sort_values("quote_date"),
        market_history[benchmark_cols].sort_values("benchmark_date"),
        left_on="quote_date",
        right_on="benchmark_date",
        direction="backward",
    )
    merged["latest_observed_benchmark_cost"] = merged["benchmark_cost_usd"].fillna(
        merged["lag_1d_cost"]
    )
    merged["data_staleness_days"] = (
        merged["quote_date"] - merged["benchmark_date"]
    ).dt.days.astype(float)
    merged["data_staleness_days"] = np.where(
        merged["latest_observed_benchmark_cost"].notna(),
        merged["data_staleness_days"].fillna(0.0),
        np.nan,
    )
    return merged.drop(columns=["benchmark_date", "benchmark_cost_usd"], errors="ignore")


def _attach_future_target_window(group_df, date_col, cost_col, day_start=14, day_end=20):
    group = group_df.sort_values(date_col).copy()
    date_values = pd.to_datetime(group[date_col], errors="coerce").dt.normalize()
    cost_values = pd.to_numeric(group[cost_col], errors="coerce")

    target_dates = []
    target_costs = []
    lead_times = []

    for current_date in date_values:
        if pd.isna(current_date):
            target_dates.append(pd.NaT)
            target_costs.append(np.nan)
            lead_times.append(np.nan)
            continue

        lower_bound = current_date + pd.Timedelta(days=day_start)
        upper_bound = current_date + pd.Timedelta(days=day_end)
        candidates = group.loc[
            date_values.between(lower_bound, upper_bound, inclusive="both")
            & cost_values.notna(),
            [date_col, cost_col],
        ].sort_values(date_col)

        if candidates.empty:
            target_dates.append(pd.NaT)
            target_costs.append(np.nan)
            lead_times.append(np.nan)
            continue

        target_row = candidates.iloc[0]
        target_date = pd.to_datetime(target_row[date_col], errors="coerce")
        target_dates.append(target_date)
        target_costs.append(float(target_row[cost_col]))
        lead_times.append(float((target_date.normalize() - current_date).days))

    group["target_observation_date"] = target_dates
    group["target_cost_usd"] = target_costs
    group["lead_time_days"] = lead_times
    return group


def _build_quote_training_rows(quotes, market_history):
    training_rows = []

    for _, group in quotes.groupby(["route_name", "container_type"], sort=False):
        engineered = _add_cost_history_features(group, "quote_date", "quoted_cost_usd")
        benchmark_group = market_history.loc[
            (market_history["route_name"] == group["route_name"].iloc[0])
            & (market_history["container_type"] == group["container_type"].iloc[0])
        ].copy()
        engineered = _attach_latest_benchmark_features(engineered, benchmark_group)
        engineered["lead_time_days"] = (
            engineered["departure_window_start"] - engineered["quote_date"]
        ).dt.days.astype(float)
        engineered = engineered.loc[
            engineered["lead_time_days"].between(14.0, 20.0, inclusive="both")
        ].copy()
        if engineered.empty:
            continue

        engineered["feature_date"] = engineered["quote_date"]
        engineered["target_observation_date"] = engineered["departure_window_start"]
        engineered["target_cost_usd"] = engineered["quoted_cost_usd"]
        engineered["feature_month"] = engineered["quote_date"].dt.month.astype(float)
        engineered["feature_quarter"] = engineered["quote_date"].dt.quarter.astype(float)
        engineered["feature_week_of_year"] = (
            engineered["quote_date"].dt.isocalendar().week.astype(float)
        )
        engineered["feature_day_of_week"] = engineered["quote_date"].dt.dayofweek.astype(float)
        engineered["departure_month"] = (
            engineered["departure_window_start"].dt.month.astype(float)
        )
        engineered["departure_quarter"] = (
            engineered["departure_window_start"].dt.quarter.astype(float)
        )
        engineered["departure_week_of_year"] = (
            engineered["departure_window_start"].dt.isocalendar().week.astype(float)
        )
        engineered["departure_day_of_week"] = (
            engineered["departure_window_start"].dt.dayofweek.astype(float)
        )
        engineered["distance_nm"] = engineered.apply(
            lambda row: _distance_nm(row["origin_port"], row["destination_port"]),
            axis=1,
        )
        _raise_if_unsupported_lanes(engineered, "quote-backed training rows")
        engineered["training_data_mode"] = TRAINING_MODE_QUOTE
        engineered["training_data_source"] = engineered["source"].fillna(
            TRAINING_MODE_QUOTE
        ).astype(str)
        training_rows.append(engineered)

    return training_rows


def _build_external_training_rows(external_history, training_mode):
    training_rows = []

    for _, group in external_history.groupby(["route_name", "container_type"], sort=False):
        engineered = _add_cost_history_features(group, "benchmark_date", "benchmark_cost_usd")
        engineered = _attach_future_target_window(
            engineered,
            "benchmark_date",
            "benchmark_cost_usd",
            day_start=14,
            day_end=20,
        )
        engineered = engineered.loc[
            engineered["target_observation_date"].notna()
            & engineered["target_cost_usd"].notna()
            & engineered["lead_time_days"].between(14.0, 20.0, inclusive="both")
        ].copy()
        if engineered.empty:
            continue

        engineered["feature_date"] = pd.to_datetime(
            engineered["benchmark_date"], errors="coerce"
        )
        engineered["departure_window_start"] = pd.to_datetime(
            engineered["target_observation_date"], errors="coerce"
        )
        engineered["departure_window_end"] = engineered["departure_window_start"]
        engineered["feature_month"] = engineered["feature_date"].dt.month.astype(float)
        engineered["feature_quarter"] = engineered["feature_date"].dt.quarter.astype(float)
        engineered["feature_week_of_year"] = (
            engineered["feature_date"].dt.isocalendar().week.astype(float)
        )
        engineered["feature_day_of_week"] = engineered["feature_date"].dt.dayofweek.astype(float)
        engineered["departure_month"] = (
            engineered["departure_window_start"].dt.month.astype(float)
        )
        engineered["departure_quarter"] = (
            engineered["departure_window_start"].dt.quarter.astype(float)
        )
        engineered["departure_week_of_year"] = (
            engineered["departure_window_start"].dt.isocalendar().week.astype(float)
        )
        engineered["departure_day_of_week"] = (
            engineered["departure_window_start"].dt.dayofweek.astype(float)
        )
        engineered["distance_nm"] = engineered.apply(
            lambda row: _distance_nm(row["origin_port"], row["destination_port"]),
            axis=1,
        )
        _raise_if_unsupported_lanes(engineered, "benchmark-backed training rows")
        engineered["latest_observed_benchmark_cost"] = engineered["lag_1d_cost"].fillna(
            engineered["benchmark_cost_usd"]
        )
        engineered["data_staleness_days"] = 0.0
        engineered["training_data_mode"] = training_mode
        engineered["training_data_source"] = engineered["provider"].fillna(
            training_mode
        ).astype(str)
        training_rows.append(engineered)

    return training_rows


def build_training_dataset(db_path=DB_PATH):
    quotes = _prepare_quote_history(load_quote_history(db_path))
    market_history = _prepare_market_history(load_market_rate_history(db_path))
    training_rows = []

    if not quotes.empty:
        training_rows.extend(_build_quote_training_rows(quotes, market_history))

    current_row_count = sum(len(frame) for frame in training_rows)
    if current_row_count < MIN_TRAINING_ROWS and not market_history.empty:
        training_rows.extend(
            _build_external_training_rows(market_history, TRAINING_MODE_EXTERNAL)
        )

    if not training_rows:
        return pd.DataFrame()

    training_df = pd.concat(training_rows, ignore_index=True)
    training_df = training_df.loc[:, ~training_df.columns.duplicated()]
    training_modes = (
        sorted(training_df["training_data_mode"].dropna().astype(str).unique().tolist())
        if "training_data_mode" in training_df.columns
        else []
    )
    provenance = {
        "quote_history_rows": int(len(quotes)),
        "market_rate_history_rows": int(len(market_history)),
        "training_data_modes": training_modes,
        "primary_training_mode": _primary_training_mode(training_modes),
        "is_benchmark_only": bool(training_modes) and TRAINING_MODE_QUOTE not in training_modes,
    }
    provenance["summary"] = describe_training_provenance(provenance)
    training_df.attrs["training_provenance"] = provenance
    ordered_cols = [
        "feature_date",
        "departure_window_start",
        "departure_window_end",
        "target_observation_date",
        "route_name",
        "origin_port",
        "destination_port",
        "container_type",
        "target_cost_usd",
        "training_data_mode",
        "training_data_source",
    ] + NUMERIC_FEATURES
    result = training_df[ordered_cols].sort_values(
        ["feature_date", "route_name", "departure_window_start"]
    )
    result.attrs["training_provenance"] = provenance
    return result


def build_preprocessor():
    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURES,
            ),
        ]
    )


def time_split(df, test_fraction=0.2):
    dates = np.array(sorted(pd.to_datetime(df["feature_date"]).dt.normalize().unique()))
    if len(dates) < 5:
        split_idx = max(1, int(len(df) * (1 - test_fraction)))
        split_idx = min(split_idx, len(df) - 1)
        return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()

    cutoff_idx = max(1, int(len(dates) * (1 - test_fraction)) - 1)
    cutoff_date = dates[cutoff_idx]
    train_df = df.loc[pd.to_datetime(df["feature_date"]) <= cutoff_date].copy()
    test_df = df.loc[pd.to_datetime(df["feature_date"]) > cutoff_date].copy()
    if test_df.empty:
        split_idx = max(1, int(len(df) * (1 - test_fraction)))
        split_idx = min(split_idx, len(df) - 1)
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
    return train_df, test_df


def _fit_residual_model(train_df, params):
    X_train = train_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y_train = train_df["target_cost_usd"].astype(float)
    baseline_train = _baseline_cost_series(train_df)

    model = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", GradientBoostingRegressor(loss="huber", **params)),
        ]
    )
    model.fit(X_train, y_train - baseline_train)
    return model


def _calibrate_route_interval_widths(train_df, params, blend_weight):
    if len(train_df) < MIN_TRAINING_ROWS:
        return {}, 0.0, 0

    fit_df, calib_df = time_split(train_df, test_fraction=INTERVAL_CALIBRATION_TEST_FRACTION)
    if fit_df.empty or calib_df.empty:
        return {}, 0.0, 0

    calibration_model = _fit_residual_model(fit_df, params)
    baseline_calib = _baseline_cost_series(calib_df)
    residual_pred = calibration_model.predict(calib_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES])
    calib_pred = _blend_prediction_from_residual(baseline_calib, residual_pred, blend_weight)
    calib_abs_error = np.abs(calib_df["target_cost_usd"].astype(float) - calib_pred)

    calibration_frame = calib_df[["route_name", "container_type"]].copy()
    calibration_frame["abs_error"] = calib_abs_error.values
    route_interval_widths = {
        _route_interval_key(route_name, container_type): round(float(width), 2)
        for (route_name, container_type), width in calibration_frame.groupby(
            ["route_name", "container_type"]
        )["abs_error"].quantile(INTERVAL_CALIBRATION_QUANTILE).items()
    }
    global_interval_width = round(
        float(calib_abs_error.quantile(INTERVAL_CALIBRATION_QUANTILE)), 2
    )
    return route_interval_widths, global_interval_width, int(len(calib_df))


def predict_forecaster_bundle(bundle, feature_frame):
    feature_columns = bundle.get("feature_columns", CATEGORICAL_FEATURES + NUMERIC_FEATURES)
    X = feature_frame[feature_columns]
    strategy = bundle.get("prediction_strategy", "absolute")

    if strategy == "residual_blend":
        baseline = _baseline_cost_series(feature_frame)
        blend_weight = float(bundle.get("residual_blend_weight", 1.0))
        residual_pred = bundle["base_model"].predict(X)
        base_pred = _blend_prediction_from_residual(baseline, residual_pred, blend_weight)

        route_interval_widths = bundle.get("route_interval_widths") or {}
        global_interval_width = float(bundle.get("global_interval_width", 0.0))
        if route_interval_widths or global_interval_width > 0.0:
            widths = _interval_width_series(
                feature_frame, route_interval_widths, global_interval_width
            )
            low_pred = base_pred - widths
            high_pred = base_pred + widths
        else:
            low_model = bundle.get("low_model")
            high_model = bundle.get("high_model")
            if low_model is not None and high_model is not None:
                low_pred = _blend_prediction_from_residual(
                    baseline, low_model.predict(X), blend_weight
                )
                high_pred = _blend_prediction_from_residual(
                    baseline, high_model.predict(X), blend_weight
                )
            else:
                low_pred = base_pred.copy()
                high_pred = base_pred.copy()

        low_pred = np.minimum(low_pred, high_pred)
        high_pred = np.maximum(low_pred, high_pred)
        return np.asarray(base_pred, dtype=float), np.asarray(low_pred, dtype=float), np.asarray(
            high_pred, dtype=float
        )

    low_model = bundle.get("low_model")
    high_model = bundle.get("high_model")
    base_pred = bundle["base_model"].predict(X)
    low_pred = low_model.predict(X) if low_model is not None else base_pred
    high_pred = high_model.predict(X) if high_model is not None else base_pred
    low_pred = np.minimum(low_pred, high_pred)
    high_pred = np.maximum(low_pred, high_pred)
    return np.asarray(base_pred, dtype=float), np.asarray(low_pred, dtype=float), np.asarray(
        high_pred, dtype=float
    )


def train_forecaster_bundle(training_df):
    if len(training_df) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"At least {MIN_TRAINING_ROWS} training rows are required to train the forecaster."
        )

    training_modes = (
        sorted(training_df["training_data_mode"].dropna().astype(str).unique().tolist())
        if "training_data_mode" in training_df.columns
        else []
    )
    training_sources = (
        sorted(training_df["training_data_source"].dropna().astype(str).unique().tolist())
        if "training_data_source" in training_df.columns
        else []
    )
    provenance = dict(training_df.attrs.get("training_provenance") or {})
    provenance.setdefault("training_data_modes", training_modes)
    provenance.setdefault("primary_training_mode", _primary_training_mode(training_modes))
    provenance.setdefault(
        "is_benchmark_only",
        bool(training_modes) and TRAINING_MODE_QUOTE not in training_modes,
    )
    provenance.setdefault("quote_history_rows", 0)
    provenance.setdefault("market_rate_history_rows", 0)
    provenance["summary"] = describe_training_provenance(provenance)

    train_df, test_df = time_split(training_df)

    y_test = test_df["target_cost_usd"].astype(float)

    residual_params = {
        "random_state": 42,
        "n_estimators": 400,
        "learning_rate": 0.03,
        "max_depth": 2,
        "min_samples_leaf": 6,
        "subsample": 0.9,
    }
    route_interval_widths, global_interval_width, calibration_rows = _calibrate_route_interval_widths(
        train_df,
        residual_params,
        RESIDUAL_BLEND_WEIGHT,
    )

    base_model = _fit_residual_model(train_df, residual_params)
    bundle = {
        "model_name": "route_planning_forecaster",
        "model_version": datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "trained_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "working_currency": WORKING_CURRENCY,
        "source_provider": ", ".join(training_sources[:3]) if training_sources else "unknown",
        "training_data_modes": training_modes,
        "training_data_sources": training_sources,
        "training_provenance": provenance,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "prediction_strategy": "residual_blend",
        "residual_blend_weight": RESIDUAL_BLEND_WEIGHT,
        "interval_strategy": "route_abs_error_quantile",
        "interval_calibration_quantile": INTERVAL_CALIBRATION_QUANTILE,
        "route_interval_widths": route_interval_widths,
        "global_interval_width": global_interval_width,
        "interval_calibration_rows": calibration_rows,
        "base_model": base_model,
        "low_model": None,
        "high_model": None,
        "feature_columns": CATEGORICAL_FEATURES + NUMERIC_FEATURES,
        "routes": sorted(training_df["route_name"].unique().tolist()),
        "container_types": sorted(training_df["container_type"].unique().tolist()),
        "history_start_date": str(pd.to_datetime(training_df["feature_date"]).min().date()),
        "history_end_date": str(pd.to_datetime(training_df["feature_date"]).max().date()),
        "latest_target_date": str(
            pd.to_datetime(training_df["departure_window_start"]).max().date()
        ),
        "training_row_count": int(len(training_df)),
    }

    base_pred, low_pred, high_pred = predict_forecaster_bundle(bundle, test_df)
    baseline_test = _baseline_cost_series(test_df)
    baseline_mae = float(mean_absolute_error(y_test, baseline_test))
    baseline_mape = float(
        np.mean(
            np.abs((y_test - baseline_test) / np.where(np.abs(y_test) < 1e-9, 1.0, y_test))
        )
        * 100.0
    )

    coverage = float(((y_test >= low_pred) & (y_test <= high_pred)).mean() * 100.0)
    rmse = float(np.sqrt(mean_squared_error(y_test, base_pred)))
    mape = float(
        np.mean(
            np.abs((y_test - base_pred) / np.where(np.abs(y_test) < 1e-9, 1.0, y_test))
        )
        * 100.0
    )
    metrics = {
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "route_count": int(training_df["route_name"].nunique()),
        "mae": round(float(mean_absolute_error(y_test, base_pred)), 2),
        "rmse": round(rmse, 2),
        "mape_pct": round(mape, 2),
        "baseline_mae": round(baseline_mae, 2),
        "baseline_mape_pct": round(baseline_mape, 2),
        "mae_improvement_vs_baseline_pct": round(
            float(((baseline_mae - mean_absolute_error(y_test, base_pred)) / baseline_mae) * 100.0)
            if baseline_mae > 0.0
            else 0.0,
            2,
        ),
        "interval_coverage_pct": round(coverage, 2),
        "avg_interval_width": round(float(np.mean(np.maximum(0.0, high_pred - low_pred))), 2),
        "prediction_strategy": "residual_blend",
        "residual_blend_weight": RESIDUAL_BLEND_WEIGHT,
        "interval_calibration_quantile": INTERVAL_CALIBRATION_QUANTILE,
        "interval_calibration_rows": calibration_rows,
        "training_cutoff_date": str(pd.to_datetime(train_df["feature_date"]).max().date()),
        "testing_start_date": str(pd.to_datetime(test_df["feature_date"]).min().date()),
        "training_data_modes": training_modes,
        "training_data_sources": training_sources,
        "training_provenance": provenance,
    }
    bundle["metrics"] = metrics
    return bundle, metrics


def save_forecaster_bundle(bundle, metrics=None, artifact_path=ARTIFACT_PATH, metrics_path=METRICS_PATH):
    joblib.dump(bundle, artifact_path)
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(
            (metrics or bundle["metrics"]) | {"model_version": bundle["model_version"]},
            fh,
            indent=2,
        )


def load_forecaster_bundle(artifact_path=ARTIFACT_PATH):
    return joblib.load(artifact_path)


class ForecastWeatherBuilder:
    def __init__(self):
        self.fetcher = RealDataFetcher(DB_PATH)
        self._weather_cache = {}
        self._marine_cache = {}

    def _load_forecast_payload(self, port_name, days_ahead):
        cache_key = (port_name, days_ahead)
        if cache_key not in self._weather_cache:
            meta = PORT_DATABASE[port_name]
            self._weather_cache[cache_key] = self.fetcher.fetch_weather_open_meteo(
                meta["lat"], meta["lon"], days_ahead=days_ahead
            )
            self._marine_cache[cache_key] = self.fetcher.fetch_marine_weather_open_meteo(
                meta["lat"], meta["lon"], days_ahead=days_ahead
            )
        return self._weather_cache[cache_key], self._marine_cache[cache_key]

    def _slice_hourly_for_date(self, weather_payload, marine_payload, target_date):
        target_str = target_date.isoformat()
        empty = {
            "wind_speed": [],
            "visibility": [],
            "precipitation": [],
            "wave_height": [],
            "severity": [],
        }
        if weather_payload is None:
            return empty

        weather_hourly = weather_payload.get("hourly", {})
        weather_times = weather_hourly.get("time", []) or []
        marine_hourly = (marine_payload or {}).get("hourly", {})
        marine_times = marine_hourly.get("time", []) or []

        marine_by_time = {}
        wave_values = marine_hourly.get("wave_height", []) or []
        for idx, timestamp in enumerate(marine_times):
            if idx < len(wave_values):
                marine_by_time[timestamp] = wave_values[idx]

        result = empty.copy()
        wind_values = weather_hourly.get("wind_speed_10m", []) or []
        visibility_values = weather_hourly.get("visibility", []) or []
        precipitation_values = weather_hourly.get("precipitation", []) or []

        for idx, timestamp in enumerate(weather_times):
            if not str(timestamp).startswith(target_str):
                continue
            wind = (
                float(wind_values[idx])
                if idx < len(wind_values) and wind_values[idx] is not None
                else np.nan
            )
            visibility = (
                float(visibility_values[idx])
                if idx < len(visibility_values) and visibility_values[idx] is not None
                else np.nan
            )
            precipitation = (
                float(precipitation_values[idx])
                if idx < len(precipitation_values) and precipitation_values[idx] is not None
                else np.nan
            )
            raw_wave_height = marine_by_time.get(timestamp, np.nan)
            wave_height = (
                np.nan if raw_wave_height is None else float(raw_wave_height)
            )

            result["wind_speed"].append(wind)
            result["visibility"].append(visibility)
            result["precipitation"].append(precipitation)
            result["wave_height"].append(wave_height)

            visibility_penalty = (
                max(0.0, (10000.0 - visibility) / 2500.0)
                if not math.isnan(visibility)
                else 0.0
            )
            precip_penalty = (
                max(0.0, precipitation / 5.0) if not math.isnan(precipitation) else 0.0
            )
            wave_penalty = max(0.0, wave_height) if not math.isnan(wave_height) else 0.0
            wind_penalty = max(0.0, wind / 40.0 * 6.0) if not math.isnan(wind) else 0.0
            result["severity"].append(
                min(10.0, wind_penalty + visibility_penalty + precip_penalty + wave_penalty)
            )

        return result

    def compute_route_weather_features(self, origin_port, destination_port, departure_date):
        departure_date = pd.Timestamp(departure_date).date()
        forecast_lead_days = max(0, (departure_date - date.today()).days)
        days_ahead = min(16, forecast_lead_days + 1)
        horizon_gap_days = max(0, forecast_lead_days + 1 - days_ahead)
        origin_weather, origin_marine = self._load_forecast_payload(origin_port, days_ahead)
        dest_weather, dest_marine = self._load_forecast_payload(destination_port, days_ahead)

        origin_slice = self._slice_hourly_for_date(origin_weather, origin_marine, departure_date)
        dest_slice = self._slice_hourly_for_date(dest_weather, dest_marine, departure_date)

        wind_values = [
            x for x in origin_slice["wind_speed"] + dest_slice["wind_speed"] if not np.isnan(x)
        ]
        visibility_values = [
            x for x in origin_slice["visibility"] + dest_slice["visibility"] if not np.isnan(x)
        ]
        precipitation_values = [
            x
            for x in origin_slice["precipitation"] + dest_slice["precipitation"]
            if not np.isnan(x)
        ]
        wave_values = [
            x for x in origin_slice["wave_height"] + dest_slice["wave_height"] if not np.isnan(x)
        ]
        severity_values = [
            x for x in origin_slice["severity"] + dest_slice["severity"] if not np.isnan(x)
        ]

        observed_points = sum(
            len(v) for v in [wind_values, visibility_values, precipitation_values, wave_values]
        )
        possible_points = sum(
            len(v)
            for v in [
                origin_slice["wind_speed"] + dest_slice["wind_speed"],
                origin_slice["visibility"] + dest_slice["visibility"],
                origin_slice["precipitation"] + dest_slice["precipitation"],
                origin_slice["wave_height"] + dest_slice["wave_height"],
            ]
        )
        coverage_pct = float((observed_points / possible_points) * 100.0) if possible_points else 0.0

        return {
            "forecast_avg_wind_speed": float(np.mean(wind_values)) if wind_values else np.nan,
            "forecast_max_wave_height": float(np.max(wave_values)) if wave_values else np.nan,
            "forecast_low_visibility_frequency": float(
                np.mean([value < 5000.0 for value in visibility_values]) * 100.0
            )
            if visibility_values
            else np.nan,
            "forecast_precipitation_total": float(np.sum(precipitation_values))
            if precipitation_values
            else np.nan,
            "forecast_severe_weather_probability": float(
                np.mean([value >= 7.0 for value in severity_values])
            )
            if severity_values
            else np.nan,
            "forecast_weather_volatility": float(np.std(severity_values))
            if severity_values
            else np.nan,
            "forecast_weather_data_coverage_pct": coverage_pct,
            "forecast_horizon_gap_days": float(horizon_gap_days),
        }


def _latest_combo_rows(quotes):
    date_col = "feature_date" if "feature_date" in quotes.columns else "quote_date"
    sort_cols = [date_col]
    if "departure_window_start" in quotes.columns:
        sort_cols.append("departure_window_start")
    if "quote_id" in quotes.columns:
        sort_cols.append("quote_id")
    elif "market_rate_id" in quotes.columns:
        sort_cols.append("market_rate_id")
    else:
        sort_cols.append("route_name")
    return (
        quotes.sort_values(sort_cols)
        .groupby(["route_name", "container_type"], as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def build_future_forecast_features(day_start=14, day_end=20, db_path=DB_PATH):
    training_df = build_training_dataset(db_path)
    if training_df.empty:
        return training_df

    _raise_if_unsupported_lanes(training_df, "future forecast feature generation")
    latest_rows = _latest_combo_rows(training_df)
    weather_builder = ForecastWeatherBuilder()
    forecast_rows = []
    today = date.today()

    for row in latest_rows.itertuples(index=False):
        history = training_df[
            (training_df["route_name"] == row.route_name)
            & (training_df["container_type"] == row.container_type)
            & (pd.to_datetime(training_df["feature_date"]) <= pd.to_datetime(row.feature_date))
        ].sort_values("feature_date")
        if history.empty:
            continue

        latest_history = history.iloc[-1].to_dict()
        latest_feature_date = pd.to_datetime(latest_history["feature_date"]).date()
        latest_distance = pd.to_numeric(pd.Series([latest_history.get("distance_nm")]), errors="coerce").iloc[0]
        if pd.isna(latest_distance):
            raise ValueError(
                f"Unsupported forecast lane: {row.route_name} ({row.origin_port} -> "
                f"{row.destination_port}, {row.container_type}) has no nautical-mile mapping."
            )
        latest_baseline_cost = pd.to_numeric(
            pd.Series([latest_history.get("latest_observed_benchmark_cost")]),
            errors="coerce",
        ).iloc[0]
        if pd.isna(latest_baseline_cost):
            raise ValueError(
                f"Unsupported forecast lane: {row.route_name} ({row.container_type}) is missing "
                "benchmark history coverage for forecast generation."
            )
        benchmark_staleness = latest_history.get("data_staleness_days", 0.0)
        if pd.isna(benchmark_staleness):
            benchmark_staleness = 0.0
        data_staleness_days = float(
            benchmark_staleness + max(0, (today - latest_feature_date).days)
        )
        for offset in range(day_start, day_end + 1):
            departure = today + timedelta(days=offset)
            weather_features = weather_builder.compute_route_weather_features(
                row.origin_port, row.destination_port, departure
            )

            feature_row = {
                "forecast_date": today.isoformat(),
                "departure_window_start": departure.isoformat(),
                "departure_window_end": departure.isoformat(),
                "route_name": row.route_name,
                "origin_port": row.origin_port,
                "destination_port": row.destination_port,
                "container_type": row.container_type,
                "distance_nm": float(latest_distance),
                "lead_time_days": float(offset),
                "feature_month": float(today.month),
                "feature_quarter": float((today.month - 1) // 3 + 1),
                "feature_week_of_year": float(pd.Timestamp(today).isocalendar().week),
                "feature_day_of_week": float(pd.Timestamp(today).dayofweek),
                "departure_month": float(departure.month),
                "departure_quarter": float((departure.month - 1) // 3 + 1),
                "departure_week_of_year": float(pd.Timestamp(departure).isocalendar().week),
                "departure_day_of_week": float(pd.Timestamp(departure).dayofweek),
                "latest_observed_benchmark_cost": float(
                    latest_history.get("latest_observed_benchmark_cost", np.nan)
                ),
                "lag_1d_cost": float(latest_history.get("lag_1d_cost", np.nan)),
                "lag_5d_cost": float(latest_history.get("lag_5d_cost", np.nan)),
                "rolling_mean_cost_7d": float(
                    latest_history.get("rolling_mean_cost_7d", np.nan)
                ),
                "rolling_mean_cost_28d": float(
                    latest_history.get("rolling_mean_cost_28d", np.nan)
                ),
                "rolling_median_cost_7d": float(
                    latest_history.get("rolling_median_cost_7d", np.nan)
                ),
                "rolling_median_cost_14d": float(
                    latest_history.get("rolling_median_cost_14d", np.nan)
                ),
                "rolling_median_cost_28d": float(
                    latest_history.get("rolling_median_cost_28d", np.nan)
                ),
                "rolling_volatility_14d": float(
                    latest_history.get("rolling_volatility_14d", np.nan)
                ),
                "rolling_volatility_28d": float(
                    latest_history.get("rolling_volatility_28d", np.nan)
                ),
                "week_over_week_change": float(
                    latest_history.get("week_over_week_change", np.nan)
                ),
                "momentum_14d": float(latest_history.get("momentum_14d", np.nan)),
                "history_count_28d": float(latest_history.get("history_count_28d", np.nan)),
                "lane_history_coverage_pct": float(
                    latest_history.get("lane_history_coverage_pct", 0.0)
                ),
                "data_staleness_days": data_staleness_days,
            }
            feature_row.update(weather_features)
            forecast_rows.append(feature_row)

    return pd.DataFrame(forecast_rows)


def estimate_weather_delay_days(weather_features):
    severe_probability = weather_features.get("forecast_severe_weather_probability", np.nan)
    wave_height = weather_features.get("forecast_max_wave_height", np.nan)
    wind_speed = weather_features.get("forecast_avg_wind_speed", np.nan)
    low_visibility_frequency = weather_features.get(
        "forecast_low_visibility_frequency", np.nan
    )

    score = 0.0
    if not np.isnan(severe_probability):
        score += severe_probability * 4.0
    if not np.isnan(wave_height):
        score += min(3.0, wave_height * 0.6)
    if not np.isnan(wind_speed):
        score += max(0.0, (wind_speed - 20.0) / 8.0)
    if not np.isnan(low_visibility_frequency):
        score += low_visibility_frequency / 40.0
    return round(float(max(0.0, score)), 2)


def estimate_weather_cost_uplift(baseline_cost, weather_features):
    severe_probability = weather_features.get("forecast_severe_weather_probability", np.nan)
    wave_height = weather_features.get("forecast_max_wave_height", np.nan)
    precipitation_total = weather_features.get("forecast_precipitation_total", np.nan)
    low_visibility_frequency = weather_features.get(
        "forecast_low_visibility_frequency", np.nan
    )
    weather_volatility = weather_features.get("forecast_weather_volatility", np.nan)

    uplift_pct = 0.0
    if not np.isnan(severe_probability):
        uplift_pct += severe_probability * 0.12
    if not np.isnan(wave_height):
        uplift_pct += min(0.08, wave_height * 0.015)
    if not np.isnan(precipitation_total):
        uplift_pct += min(0.04, precipitation_total * 0.002)
    if not np.isnan(low_visibility_frequency):
        uplift_pct += min(0.04, low_visibility_frequency / 1000.0)
    if not np.isnan(weather_volatility):
        uplift_pct += min(0.03, weather_volatility * 0.01)

    uplift_pct = float(min(0.25, max(0.0, uplift_pct)))
    return round(float(baseline_cost) * uplift_pct, 2)


def estimate_confidence_score(feature_row):
    history_coverage = float(feature_row.get("lane_history_coverage_pct", 0.0))
    weather_coverage = float(feature_row.get("forecast_weather_data_coverage_pct", 0.0))
    quote_count = float(feature_row.get("history_count_28d", 0.0))
    lead_time = float(feature_row.get("lead_time_days", 0.0))
    staleness_days = float(feature_row.get("data_staleness_days", 0.0))
    horizon_gap_days = float(feature_row.get("forecast_horizon_gap_days", 0.0))
    if math.isnan(history_coverage):
        history_coverage = 0.0
    if math.isnan(weather_coverage):
        weather_coverage = 0.0
    if math.isnan(quote_count):
        quote_count = 0.0
    if math.isnan(lead_time):
        lead_time = 0.0
    if math.isnan(staleness_days):
        staleness_days = 0.0
    if math.isnan(horizon_gap_days):
        horizon_gap_days = 0.0
    quote_density_bonus = min(20.0, quote_count * 2.0)
    lead_penalty = max(0.0, (lead_time - 14.0) * 2.0)
    staleness_penalty = min(20.0, max(0.0, staleness_days - 7.0) * 0.75)
    weather_gap_penalty = horizon_gap_days * 6.0
    confidence = (
        0.45 * history_coverage
        + 0.35 * weather_coverage
        + quote_density_bonus
        - lead_penalty
        - staleness_penalty
        - weather_gap_penalty
    )
    return round(float(max(5.0, min(100.0, confidence))), 2)


def persist_route_forecasts(forecast_df, bundle, db_path=DB_PATH):
    if forecast_df is None or forecast_df.empty:
        return 0

    conn = connect(db_path)
    try:
        cursor = conn.cursor()
        forecast_date = str(forecast_df["forecast_date"].iloc[0])
        rows = []
        for row in forecast_df.itertuples(index=False):
            rows.append(
                (
                    row.forecast_date,
                    row.departure_window_start,
                    row.departure_window_end,
                    row.route_name,
                    row.origin_port,
                    row.destination_port,
                    row.container_type,
                    bundle["model_name"],
                    bundle["model_version"],
                    float(row.market_baseline_cost),
                    float(row.expected_base_cost),
                    float(row.expected_low_cost),
                    float(row.expected_high_cost),
                    float(row.weather_cost_uplift),
                    float(row.expected_delay_days),
                    float(row.severe_weather_probability),
                    float(row.confidence_score),
                    float(row.data_coverage_pct),
                    int(row.rank_by_cost),
                    int(row.rank_by_risk),
                    json.dumps(
                        {col: row._asdict().get(col) for col in FUTURE_WEATHER_COLUMNS},
                        default=str,
                    ),
                    json.dumps(
                        {
                            col: row._asdict().get(col)
                            for col in CATEGORICAL_FEATURES + NUMERIC_FEATURES
                        },
                        default=str,
                    ),
                )
            )

        conn.execute("BEGIN")
        cursor.execute(
            f"DELETE FROM {ROUTE_FORECASTS_TABLE} WHERE forecast_date = ?",
            (forecast_date,),
        )
        cursor.executemany(
            f"""
            INSERT INTO {ROUTE_FORECASTS_TABLE} (
                forecast_date,
                departure_window_start,
                departure_window_end,
                route_name,
                origin_port,
                destination_port,
                container_type,
                model_name,
                model_version,
                market_baseline_cost,
                expected_base_cost,
                expected_low_cost,
                expected_high_cost,
                weather_cost_uplift,
                expected_delay_days,
                severe_weather_probability,
                confidence_score,
                data_coverage_pct,
                rank_by_cost,
                rank_by_risk,
                weather_summary_json,
                feature_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(rows)


def compare_latest_forecasts_to_benchmarks(db_path=DB_PATH, provider=None):
    conn = connect(db_path)
    provider_filter = ""
    params = []
    if provider:
        provider_filter = "AND b.provider = ?"
        params.append(provider)

    query = f"""
    SELECT
        f.forecast_date,
        f.departure_window_start,
        f.route_name,
        f.container_type,
        f.expected_low_cost,
        f.expected_base_cost,
        f.expected_high_cost,
        f.expected_delay_days,
        f.rank_by_cost,
        b.provider,
        b.predicted_cost,
        b.predicted_delay_days
    FROM {ROUTE_FORECASTS_TABLE} f
    JOIN {EXTERNAL_BENCHMARKS_TABLE} b
      ON b.forecast_date = f.forecast_date
     AND b.route_name = f.route_name
     AND b.container_type = f.container_type
    WHERE 1=1 {provider_filter}
    ORDER BY f.forecast_date, f.container_type, f.rank_by_cost
    """
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return df

    df["absolute_delta"] = df["expected_base_cost"] - df["predicted_cost"]
    df["percentage_delta"] = np.where(
        df["predicted_cost"].abs() > 1e-6,
        (df["absolute_delta"] / df["predicted_cost"]) * 100.0,
        np.nan,
    )

    df["provider_rank"] = (
        df.groupby(["forecast_date", "container_type"])["predicted_cost"]
        .rank(method="dense", ascending=True)
        .astype(int)
    )
    df["rank_difference"] = (df["rank_by_cost"] - df["provider_rank"]).abs()
    group_size = df.groupby(["forecast_date", "container_type"])["route_name"].transform("count")
    df["ranking_agreement_score"] = np.where(
        group_size > 1,
        1.0 - (df["rank_difference"] / (group_size - 1)),
        1.0,
    )
    return df


def build_arg_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--db-path", default=DB_PATH)
    return parser
