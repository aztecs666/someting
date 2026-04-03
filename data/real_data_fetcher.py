"""
Observable route data fetcher.

This module stores only observed route and port conditions plus transparent
derived values. It does not fabricate shipment-level operational fields.
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt

import numpy as np
import pandas as pd
import requests

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
OBSERVED_TABLE = "route_observations"
WATCHLIST_TABLE = "route_watchlist"
PREDICTIONS_TABLE = "route_predictions"
EXTERNAL_BENCHMARKS_TABLE = "external_benchmark_predictions"
QUOTE_HISTORY_STAGING_TABLE = "quote_history_staging"
QUOTE_HISTORY_TABLE = "quote_history"
MARKET_RATE_HISTORY_TABLE = "market_rate_history"
ROUTE_FORECASTS_TABLE = "route_forecasts"

PORT_DATABASE = {
    "Singapore": {"lat": 1.2644, "lon": 103.8222, "country": "Singapore"},
    "New York": {"lat": 40.6892, "lon": -74.0445, "country": "USA"},
    "Los Angeles": {"lat": 33.7283, "lon": -118.2620, "country": "USA"},
    "Shanghai": {"lat": 31.2304, "lon": 121.4737, "country": "China"},
    "Dubai": {"lat": 25.276987, "lon": 55.296249, "country": "UAE"},
    "Mumbai": {"lat": 18.9647, "lon": 72.8258, "country": "India"},
    "Hamburg": {"lat": 53.5511, "lon": 9.9937, "country": "Germany"},
    "Tokyo": {"lat": 35.6532, "lon": 139.8395, "country": "Japan"},
    "Busan": {"lat": 35.1796, "lon": 129.0756, "country": "South Korea"},
    "Rotterdam": {"lat": 51.9244, "lon": 4.4777, "country": "Netherlands"},
    "Hong Kong": {"lat": 22.3193, "lon": 114.1694, "country": "China"},
    "Shenzhen": {"lat": 22.5431, "lon": 114.0579, "country": "China"},
    "Ningbo": {"lat": 29.8683, "lon": 121.5440, "country": "China"},
    "Antwerp": {"lat": 51.2194, "lon": 4.4025, "country": "Belgium"},
    "Long Beach": {"lat": 33.7701, "lon": -118.1937, "country": "USA"},
    "Santos": {"lat": -23.9608, "lon": -46.3336, "country": "Brazil"},
    "Sydney": {"lat": -33.8688, "lon": 151.2093, "country": "Australia"},
    "Melbourne": {"lat": -37.8136, "lon": 144.9631, "country": "Australia"},
    "Auckland": {"lat": -36.8485, "lon": 174.7633, "country": "New Zealand"},
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "country": "India"},
    "Colombo": {"lat": 6.9271, "lon": 79.8612, "country": "Sri Lanka"},
    "Port Klang": {"lat": 2.9991, "lon": 101.3864, "country": "Malaysia"},
    "Bangkok": {"lat": 13.7563, "lon": 100.5018, "country": "Thailand"},
    "Ho Chi Minh": {"lat": 10.8231, "lon": 106.6297, "country": "Vietnam"},
    "Manila": {"lat": 14.5995, "lon": 120.9842, "country": "Philippines"},
}

DEFAULT_WATCHLIST = [
    ("Far East to North Europe", "Shanghai", "Rotterdam"),
    ("Far East to South America East Coast", "Shanghai", "Santos"),
    ("Far East to US West Coast", "Shanghai", "Los Angeles"),
    ("North Europe to Far East", "Rotterdam", "Shanghai"),
    ("North Europe to South America East Coast", "Rotterdam", "Santos"),
    ("North Europe to US East Coast", "Rotterdam", "New York"),
    ("US East Coast to North Europe", "New York", "Rotterdam"),
    ("US West Coast to Far East", "Los Angeles", "Shanghai"),
]

DISTANCE_CACHE = {}


def _clean_numeric(values, fallback):
    cleaned = []
    for value in values or [fallback]:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if np.isnan(numeric):
            continue
        cleaned.append(numeric)
    return cleaned or [float(fallback)]


def _safe_nan_reduce(values, reducer):
    array = np.asarray(values, dtype=float)
    if array.size == 0 or np.isnan(array).all():
        return np.nan
    return float(reducer(array))


class RealDataFetcher:
    """Fetch observable route snapshots for a monitored lane watchlist."""

    def __init__(
        self,
        db_path=DB_PATH,
        initialize=True,
        seed_reference_data=True,
        allow_maintenance=True,
    ):
        self.db_path = db_path
        if initialize:
            self._init_database(allow_maintenance=allow_maintenance)
        if seed_reference_data:
            self._seed_reference_data()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _table_columns(self, cursor, table_name):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    def _migrate_external_benchmark_table(self, cursor):
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (EXTERNAL_BENCHMARKS_TABLE,),
        )
        if cursor.fetchone() is None:
            return

        existing_columns = self._table_columns(cursor, EXTERNAL_BENCHMARKS_TABLE)
        if "forecast_date" in existing_columns and "route_name" in existing_columns:
            return

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {EXTERNAL_BENCHMARKS_TABLE}_new (
                benchmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_forecast_id INTEGER,
                observation_id INTEGER,
                provider TEXT NOT NULL,
                forecast_date TEXT,
                route_name TEXT,
                origin_port TEXT,
                destination_port TEXT,
                container_type TEXT,
                predicted_cost REAL,
                predicted_delay_days REAL,
                metric_name TEXT,
                metric_value REAL,
                predicted_at TEXT,
                raw_payload TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(route_forecast_id) REFERENCES {ROUTE_FORECASTS_TABLE}(forecast_id),
                FOREIGN KEY(observation_id) REFERENCES {OBSERVED_TABLE}(observation_id)
            )
            """
        )
        cursor.execute(
            f"""
            INSERT INTO {EXTERNAL_BENCHMARKS_TABLE}_new (
                benchmark_id,
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
                raw_payload,
                created_at
            )
            SELECT
                benchmark_id,
                NULL,
                observation_id,
                provider,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                CASE WHEN metric_name = 'predicted_cost' THEN metric_value ELSE NULL END,
                CASE WHEN metric_name = 'predicted_delay_days' THEN metric_value ELSE NULL END,
                metric_name,
                metric_value,
                predicted_at,
                raw_payload,
                created_at
            FROM {EXTERNAL_BENCHMARKS_TABLE}
            """
        )
        cursor.execute(f"DROP TABLE {EXTERNAL_BENCHMARKS_TABLE}")
        cursor.execute(
            f"ALTER TABLE {EXTERNAL_BENCHMARKS_TABLE}_new RENAME TO {EXTERNAL_BENCHMARKS_TABLE}"
        )

    def _deduplicate_route_forecasts(self, cursor):
        cursor.execute(
            f"""
            DELETE FROM {ROUTE_FORECASTS_TABLE}
            WHERE forecast_id NOT IN (
                SELECT MAX(forecast_id)
                FROM {ROUTE_FORECASTS_TABLE}
                GROUP BY
                    forecast_date,
                    departure_window_start,
                    departure_window_end,
                    route_name,
                    origin_port,
                    destination_port,
                    container_type
            )
            """
        )

    def _ensure_route_forecast_unique_index(self, cursor):
        cursor.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_{ROUTE_FORECASTS_TABLE}_unique_window
            ON {ROUTE_FORECASTS_TABLE}(
                forecast_date,
                departure_window_start,
                departure_window_end,
                route_name,
                origin_port,
                destination_port,
                container_type
            )
            """
        )

    def _init_database(self, allow_maintenance=True):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ports (
                port_name TEXT PRIMARY KEY,
                country TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                source TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {WATCHLIST_TABLE} (
                route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_name TEXT NOT NULL UNIQUE,
                origin_port TEXT NOT NULL,
                destination_port TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {OBSERVED_TABLE} (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                route_id INTEGER NOT NULL,
                route_name TEXT NOT NULL,
                origin_port TEXT NOT NULL,
                destination_port TEXT NOT NULL,
                source_weather TEXT,
                source_marine TEXT,
                source_schedule TEXT,
                source_port_calls TEXT,
                source_notes TEXT,
                year INTEGER,
                month INTEGER,
                quarter INTEGER,
                day_of_week INTEGER,
                is_weekend INTEGER,
                is_holiday_season INTEGER,
                distance_nm REAL,
                base_transit_time REAL,
                schedule_eta_origin TEXT,
                schedule_eta_destination TEXT,
                actual_arrival_origin TEXT,
                actual_departure_origin TEXT,
                actual_arrival_destination TEXT,
                actual_departure_destination TEXT,
                weather_severity_origin REAL,
                weather_severity_destination REAL,
                storm_probability REAL,
                temp_deviation_origin REAL,
                temp_deviation_destination REAL,
                wind_speed_origin REAL,
                wind_speed_destination REAL,
                visibility_nm REAL,
                wave_height REAL,
                weather_delay_risk REAL,
                weather_delay_occurred REAL,
                pressure_msl_origin REAL,
                pressure_msl_destination REAL,
                precipitation_origin REAL,
                precipitation_destination REAL,
                port_congestion_origin REAL,
                port_congestion_destination REAL,
                port_efficiency_origin REAL,
                port_efficiency_destination REAL,
                vessels_at_port_origin REAL,
                vessels_at_port_destination REAL,
                crane_availability REAL,
                labor_dispute_risk REAL,
                customs_complexity REAL,
                fuel_price_origin REAL,
                fuel_price_destination REAL,
                container_count REAL,
                container_weight_teus REAL,
                total_teus REAL,
                carrier_premium_factor REAL,
                container_premium_factor REAL,
                baf_factor REAL,
                exchange_rate_index REAL,
                insurance_rate REAL,
                peak_season_surcharge REAL,
                port_charges_origin REAL,
                port_charges_destination REAL,
                demand_factor REAL,
                operational_risk_score REAL,
                market_index REAL,
                carrier TEXT,
                container_type TEXT,
                cargo_type TEXT,
                demand_level TEXT,
                data_quality_score REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(route_id) REFERENCES {WATCHLIST_TABLE}(route_id)
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PREDICTIONS_TABLE} (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER NOT NULL,
                predicted_at TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT,
                observed_feature_coverage_pct REAL,
                drift_feature_count INTEGER,
                predicted_shipping_price REAL,
                predicted_delay_days REAL,
                predicted_route_efficiency REAL,
                predicted_port_efficiency REAL,
                predicted_cost_per_teu REAL,
                predicted_total_risk_score REAL,
                FOREIGN KEY(observation_id) REFERENCES {OBSERVED_TABLE}(observation_id)
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {EXTERNAL_BENCHMARKS_TABLE} (
                benchmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_forecast_id INTEGER,
                observation_id INTEGER,
                provider TEXT NOT NULL,
                forecast_date TEXT,
                route_name TEXT,
                origin_port TEXT,
                destination_port TEXT,
                container_type TEXT,
                predicted_cost REAL,
                predicted_delay_days REAL,
                metric_name TEXT,
                metric_value REAL,
                predicted_at TEXT,
                raw_payload TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(route_forecast_id) REFERENCES {ROUTE_FORECASTS_TABLE}(forecast_id),
                FOREIGN KEY(observation_id) REFERENCES {OBSERVED_TABLE}(observation_id)
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {QUOTE_HISTORY_STAGING_TABLE} (
                staging_id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_batch_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                raw_row_json TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {QUOTE_HISTORY_TABLE} (
                quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_batch_id TEXT NOT NULL,
                quote_date TEXT NOT NULL,
                departure_window_start TEXT NOT NULL,
                departure_window_end TEXT,
                route_name TEXT NOT NULL,
                origin_port TEXT NOT NULL,
                destination_port TEXT NOT NULL,
                container_type TEXT NOT NULL,
                quoted_cost REAL NOT NULL,
                quoted_cost_usd REAL NOT NULL,
                currency TEXT NOT NULL,
                fx_rate_to_usd REAL NOT NULL,
                carrier TEXT,
                transit_time_days REAL,
                surcharge_total REAL,
                surcharge_total_usd REAL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    quote_date,
                    departure_window_start,
                    route_name,
                    origin_port,
                    destination_port,
                    container_type,
                    quoted_cost_usd,
                    source
                )
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MARKET_RATE_HISTORY_TABLE} (
                market_rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                benchmark_slug TEXT NOT NULL,
                benchmark_id INTEGER NOT NULL,
                benchmark_date TEXT NOT NULL,
                route_name TEXT NOT NULL,
                origin_port TEXT NOT NULL,
                destination_port TEXT NOT NULL,
                container_type TEXT NOT NULL,
                benchmark_cost REAL NOT NULL,
                benchmark_cost_usd REAL NOT NULL,
                currency TEXT NOT NULL,
                source_url TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    provider,
                    benchmark_slug,
                    benchmark_date,
                    route_name,
                    container_type
                )
            )
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {ROUTE_FORECASTS_TABLE} (
                forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date TEXT NOT NULL,
                departure_window_start TEXT NOT NULL,
                departure_window_end TEXT NOT NULL,
                route_name TEXT NOT NULL,
                origin_port TEXT NOT NULL,
                destination_port TEXT NOT NULL,
                container_type TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                market_baseline_cost REAL NOT NULL,
                expected_base_cost REAL NOT NULL,
                expected_low_cost REAL NOT NULL,
                expected_high_cost REAL NOT NULL,
                weather_cost_uplift REAL NOT NULL,
                expected_delay_days REAL NOT NULL,
                severe_weather_probability REAL NOT NULL,
                confidence_score REAL NOT NULL,
                data_coverage_pct REAL NOT NULL,
                rank_by_cost INTEGER,
                rank_by_risk INTEGER,
                weather_summary_json TEXT,
                feature_snapshot_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if allow_maintenance:
            self._migrate_external_benchmark_table(cursor)
            self._deduplicate_route_forecasts(cursor)
        self._ensure_route_forecast_unique_index(cursor)

        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{OBSERVED_TABLE}_observed_at ON {OBSERVED_TABLE}(observed_at)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{OBSERVED_TABLE}_route ON {OBSERVED_TABLE}(route_id)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{PREDICTIONS_TABLE}_observation ON {PREDICTIONS_TABLE}(observation_id)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{QUOTE_HISTORY_TABLE}_route_date ON {QUOTE_HISTORY_TABLE}(route_name, container_type, quote_date)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{MARKET_RATE_HISTORY_TABLE}_route_date ON {MARKET_RATE_HISTORY_TABLE}(route_name, container_type, benchmark_date)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{ROUTE_FORECASTS_TABLE}_route_date ON {ROUTE_FORECASTS_TABLE}(route_name, container_type, departure_window_start)"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{EXTERNAL_BENCHMARKS_TABLE}_forecast ON {EXTERNAL_BENCHMARKS_TABLE}(provider, forecast_date, route_name, container_type)"
        )

        conn.commit()
        conn.close()

    def _seed_reference_data(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT OR REPLACE INTO ports (port_name, country, latitude, longitude, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    port_name,
                    port_meta["country"],
                    port_meta["lat"],
                    port_meta["lon"],
                    "local_port_reference",
                )
                for port_name, port_meta in PORT_DATABASE.items()
            ],
        )

        cursor.executemany(
            f"""
            INSERT OR IGNORE INTO {WATCHLIST_TABLE} (route_name, origin_port, destination_port)
            VALUES (?, ?, ?)
            """,
            DEFAULT_WATCHLIST,
        )

        conn.commit()
        conn.close()

    def get_watchlist(self):
        conn = self._connect()
        try:
            return pd.read_sql_query(
                f"SELECT route_id, route_name, origin_port, destination_port FROM {WATCHLIST_TABLE} WHERE active = 1 ORDER BY route_id",
                conn,
            )
        finally:
            conn.close()

    def fetch_weather_open_meteo(self, lat, lon, days_ahead=2):
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,visibility,precipitation,pressure_msl",
            "timezone": "auto",
            "forecast_days": days_ahead,
        }
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            print(f"Weather API error for ({lat}, {lon}): {exc}")
            return None

    def fetch_marine_weather_open_meteo(self, lat, lon, days_ahead=2):
        url = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "wave_height,wave_direction,wave_period",
            "timezone": "auto",
            "forecast_days": days_ahead,
        }
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            print(f"Marine API error for ({lat}, {lon}): {exc}")
            return None

    def calculate_distance_nm(self, origin_port, destination_port):
        cache_key = (origin_port, destination_port)
        if cache_key in DISTANCE_CACHE:
            return DISTANCE_CACHE[cache_key]

        origin = PORT_DATABASE[origin_port]
        destination = PORT_DATABASE[destination_port]
        lat1 = radians(origin["lat"])
        lon1 = radians(origin["lon"])
        lat2 = radians(destination["lat"])
        lon2 = radians(destination["lon"])

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        km_distance = 6371.0 * c
        nm_distance = km_distance * 0.539957

        DISTANCE_CACHE[cache_key] = nm_distance
        DISTANCE_CACHE[(destination_port, origin_port)] = nm_distance
        return nm_distance

    def calculate_weather_delay_risk(self, weather_data, marine_data):
        if not weather_data:
            return np.nan, np.nan

        hourly = weather_data.get("hourly", {})
        wind_speeds = _clean_numeric(hourly.get("wind_speed_10m", [0.0]), 0.0)
        visibilities = _clean_numeric(hourly.get("visibility", [10000.0]), 10000.0)
        precipitations = _clean_numeric(hourly.get("precipitation", [0.0]), 0.0)

        waves = []
        if marine_data:
            waves = _clean_numeric(
                marine_data.get("hourly", {}).get("wave_height", [0.0]), 0.0
            )

        avg_wind = float(np.mean(wind_speeds))
        avg_visibility = float(np.mean(visibilities))
        total_precip = float(np.sum(precipitations))
        wave_height = float(np.mean(waves)) if waves else 0.0

        severity = (avg_wind / 40.0) * 6.0 + (10000.0 - avg_visibility) / 2500.0 + total_precip / 5.0 + wave_height
        severity = float(np.clip(severity, 0.0, 10.0))
        storm_probability = float(np.clip((avg_wind - 25.0) / 20.0 + wave_height / 4.0, 0.0, 1.0))
        return severity, storm_probability

    def extract_weather_snapshot(self, weather_data, marine_data):
        if not weather_data:
            return {
                "severity": np.nan,
                "storm_probability": np.nan,
                "temperature": np.nan,
                "temp_deviation": np.nan,
                "wind_speed": np.nan,
                "visibility_nm": np.nan,
                "wave_height": np.nan,
                "pressure_msl": np.nan,
                "precipitation": np.nan,
            }

        hourly = weather_data.get("hourly", {})
        temps = _clean_numeric(hourly.get("temperature_2m", []), np.nan)
        winds = _clean_numeric(hourly.get("wind_speed_10m", []), np.nan)
        visibilities = _clean_numeric(hourly.get("visibility", []), np.nan)
        precipitations = _clean_numeric(hourly.get("precipitation", []), 0.0)
        pressures = _clean_numeric(hourly.get("pressure_msl", []), np.nan)

        waves = _clean_numeric(
            (marine_data or {}).get("hourly", {}).get("wave_height", []), np.nan
        )
        severity, storm_probability = self.calculate_weather_delay_risk(
            weather_data, marine_data
        )

        current_temp = float(temps[0]) if temps else np.nan
        baseline_temp = float(np.mean(temps[:24])) if temps else np.nan
        visibility_nm = float(np.mean(visibilities[:12]) / 1852.0) if visibilities else np.nan
        wave_height = float(np.mean(waves[:12])) if waves else np.nan

        return {
            "severity": severity,
            "storm_probability": storm_probability,
            "temperature": current_temp,
            "temp_deviation": current_temp - baseline_temp if temps else np.nan,
            "wind_speed": float(np.mean(winds[:12])) if winds else np.nan,
            "visibility_nm": visibility_nm,
            "wave_height": wave_height,
            "pressure_msl": float(np.mean(pressures[:12])) if pressures else np.nan,
            "precipitation": float(np.sum(precipitations[:12])) if precipitations else np.nan,
        }

    def build_route_observation(self, route_row):
        observed_at = datetime.utcnow()
        origin = PORT_DATABASE[route_row.origin_port]
        destination = PORT_DATABASE[route_row.destination_port]

        weather_origin = self.fetch_weather_open_meteo(origin["lat"], origin["lon"])
        marine_origin = self.fetch_marine_weather_open_meteo(origin["lat"], origin["lon"])
        weather_destination = self.fetch_weather_open_meteo(
            destination["lat"], destination["lon"]
        )
        marine_destination = self.fetch_marine_weather_open_meteo(
            destination["lat"], destination["lon"]
        )

        origin_snapshot = self.extract_weather_snapshot(weather_origin, marine_origin)
        destination_snapshot = self.extract_weather_snapshot(
            weather_destination, marine_destination
        )

        distance_nm = round(
            float(self.calculate_distance_nm(route_row.origin_port, route_row.destination_port)),
            2,
        )
        weather_delay_risk = float(
            _safe_nan_reduce(
                [
                    origin_snapshot["severity"],
                    destination_snapshot["severity"],
                ],
                np.nanmean,
            )
        )
        data_quality_fields = [
            origin_snapshot["severity"],
            destination_snapshot["severity"],
            origin_snapshot["wind_speed"],
            destination_snapshot["wind_speed"],
            distance_nm,
        ]
        observed_values = sum(
            not (value is None or (isinstance(value, float) and np.isnan(value)))
            for value in data_quality_fields
        )
        data_quality_score = round((observed_values / len(data_quality_fields)) * 100.0, 2)

        return {
            "observed_at": observed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "route_id": int(route_row.route_id),
            "route_name": route_row.route_name,
            "origin_port": route_row.origin_port,
            "destination_port": route_row.destination_port,
            "source_weather": "Open-Meteo Forecast API",
            "source_marine": "Open-Meteo Marine API",
            "source_schedule": None,
            "source_port_calls": None,
            "source_notes": (
                "DCSA-style observable lane snapshot. Unavailable operational and "
                "commercial fields remain NULL until a real carrier/TMS/port feed is connected."
            ),
            "year": observed_at.year,
            "month": observed_at.month,
            "quarter": (observed_at.month - 1) // 3 + 1,
            "day_of_week": observed_at.weekday(),
            "is_weekend": int(observed_at.weekday() >= 5),
            "is_holiday_season": int(observed_at.month in [11, 12, 1]),
            "distance_nm": distance_nm,
            "base_transit_time": None,
            "schedule_eta_origin": None,
            "schedule_eta_destination": None,
            "actual_arrival_origin": None,
            "actual_departure_origin": None,
            "actual_arrival_destination": None,
            "actual_departure_destination": None,
            "weather_severity_origin": origin_snapshot["severity"],
            "weather_severity_destination": destination_snapshot["severity"],
            "storm_probability": _safe_nan_reduce(
                [
                    origin_snapshot["storm_probability"],
                    destination_snapshot["storm_probability"],
                ],
                np.nanmax,
            ),
            "temp_deviation_origin": origin_snapshot["temp_deviation"],
            "temp_deviation_destination": destination_snapshot["temp_deviation"],
            "wind_speed_origin": origin_snapshot["wind_speed"],
            "wind_speed_destination": destination_snapshot["wind_speed"],
            "visibility_nm": _safe_nan_reduce(
                [origin_snapshot["visibility_nm"], destination_snapshot["visibility_nm"]],
                np.nanmin,
            ),
            "wave_height": _safe_nan_reduce(
                [origin_snapshot["wave_height"], destination_snapshot["wave_height"]],
                np.nanmax,
            ),
            "weather_delay_risk": weather_delay_risk,
            "weather_delay_occurred": float(weather_delay_risk >= 7.0)
            if not np.isnan(weather_delay_risk)
            else np.nan,
            "pressure_msl_origin": origin_snapshot["pressure_msl"],
            "pressure_msl_destination": destination_snapshot["pressure_msl"],
            "precipitation_origin": origin_snapshot["precipitation"],
            "precipitation_destination": destination_snapshot["precipitation"],
            "port_congestion_origin": None,
            "port_congestion_destination": None,
            "port_efficiency_origin": None,
            "port_efficiency_destination": None,
            "vessels_at_port_origin": None,
            "vessels_at_port_destination": None,
            "crane_availability": None,
            "labor_dispute_risk": None,
            "customs_complexity": None,
            "fuel_price_origin": None,
            "fuel_price_destination": None,
            "container_count": None,
            "container_weight_teus": None,
            "total_teus": None,
            "carrier_premium_factor": None,
            "container_premium_factor": None,
            "baf_factor": None,
            "exchange_rate_index": None,
            "insurance_rate": None,
            "peak_season_surcharge": None,
            "port_charges_origin": None,
            "port_charges_destination": None,
            "demand_factor": None,
            "operational_risk_score": None,
            "market_index": None,
            "carrier": None,
            "container_type": None,
            "cargo_type": None,
            "demand_level": None,
            "data_quality_score": data_quality_score,
        }

    def save_observation(self, observation):
        conn = self._connect()
        cursor = conn.cursor()
        columns = list(observation.keys())
        placeholders = ", ".join(["?"] * len(columns))
        cursor.execute(
            f"""
            INSERT INTO {OBSERVED_TABLE} ({", ".join(columns)})
            VALUES ({placeholders})
            """,
            [observation[col] for col in columns],
        )
        observation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return observation_id

    def fetch_watchlist_observations(self):
        watchlist = self.get_watchlist()
        saved = []
        for route_row in watchlist.itertuples(index=False):
            observation = self.build_route_observation(route_row)
            observation_id = self.save_observation(observation)
            saved.append(
                {
                    "observation_id": observation_id,
                    "route_name": route_row.route_name,
                    "origin_port": route_row.origin_port,
                    "destination_port": route_row.destination_port,
                    "observed_at": observation["observed_at"],
                    "data_quality_score": observation["data_quality_score"],
                }
            )
        return pd.DataFrame(saved)

    def get_observations_dataframe(self, limit=100):
        conn = self._connect()
        try:
            return pd.read_sql_query(
                f"SELECT * FROM {OBSERVED_TABLE} ORDER BY observation_id DESC LIMIT {int(limit)}",
                conn,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    fetcher = RealDataFetcher()
    df = fetcher.fetch_watchlist_observations()
    print(df.to_string(index=False))
