"""
Stream Engine — Live Market Tick Generator + ML Predictor + Accuracy Tracker

Background threads that:
1. Generate simulated market ticks (perturbed benchmark prices) every 2-3s
2. Run XGBoost predictions on each tick
3. Track prediction accuracy against actual outcomes
4. Expose SSE event stream for real-time browser consumption
5. Auto-retrain model weekly (Sunday midnight)
"""

import json
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import queue
import random
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.joblib")
FEATURES_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_features.joblib")
BACKUP_MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.backup.joblib")

# Global event queue for SSE subscribers
_subscribers = []
_lock = threading.Lock()


def _broadcast(event_data):
    """Push event to all SSE subscribers."""
    with _lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(event_data)
            except Exception:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def subscribe():
    """Create a new SSE subscriber queue."""
    q = queue.Queue(maxsize=200)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    """Remove an SSE subscriber queue."""
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_stream_tables():
    """Create tables for live streaming data."""
    conn = _connect()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS live_ticks (
        tick_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        lane_id INTEGER NOT NULL,
        lane_name TEXT NOT NULL,
        origin_port TEXT,
        destination_port TEXT,
        container_type TEXT,
        price_usd REAL NOT NULL,
        price_change REAL DEFAULT 0,
        price_change_pct REAL DEFAULT 0,
        volume INTEGER DEFAULT 1,
        source TEXT DEFAULT 'simulated'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS live_predictions (
        pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tick_id INTEGER NOT NULL,
        lane_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        current_price REAL,
        predicted_14d REAL,
        predicted_21d REAL,
        predicted_low_14d REAL,
        predicted_high_14d REAL,
        model_version TEXT,
        FOREIGN KEY (tick_id) REFERENCES live_ticks(tick_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS prediction_accuracy (
        accuracy_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        lane_id INTEGER NOT NULL,
        lane_name TEXT,
        predicted_price REAL,
        actual_price REAL,
        error_abs REAL,
        error_pct REAL,
        prediction_age_days INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS retrain_log (
        retrain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        train_samples INTEGER,
        test_mae REAL,
        test_r2 REAL,
        model_path TEXT,
        trigger TEXT DEFAULT 'scheduled'
    )""")

    conn.commit()
    conn.close()


class StreamEngine:
    """Core live streaming engine."""

    def __init__(self):
        init_stream_tables()
        self.model = None
        self.features = None
        self._load_model()
        self._lane_state = {}
        self._route_encoders = {}
        self._init_lane_state()
        self.running = False
        self.tick_count = 0
        self.total_predictions = 0
        self.start_time = None
        self._retrain_lock = threading.Lock()

    def _load_model(self):
        """Load or reload model from disk."""
        if os.path.exists(MODEL_PATH) and os.path.exists(FEATURES_PATH):
            self.model = joblib.load(MODEL_PATH)
            self.features = joblib.load(FEATURES_PATH)
            return True
        return False

    def _init_lane_state(self):
        """Load latest price per lane as the starting point for simulation."""
        conn = _connect()
        query = """
            SELECT bl.lane_id, bl.lane_name, bl.origin_port, bl.destination_port,
                   bl.container_type, bh.price_usd
            FROM benchmark_history bh
            JOIN benchmark_lanes bl ON bh.lane_id = bl.lane_id
            WHERE bh.date = (SELECT MAX(date) FROM benchmark_history WHERE lane_id = bl.lane_id)
            ORDER BY bl.lane_id
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        for idx, row in enumerate(df.itertuples(index=False)):
            lane_name = str(row.lane_name)
            self._route_encoders[lane_name] = idx
            self._lane_state[int(row.lane_id)] = {
                "lane_id": int(row.lane_id),
                "lane_name": lane_name,
                "origin_port": str(row.origin_port),
                "destination_port": str(row.destination_port),
                "container_type": str(row.container_type),
                "price": float(row.price_usd),
                "base_price": float(row.price_usd),
            }

    def generate_tick(self):
        """Generate a single simulated market tick for a random lane."""
        if not self._lane_state:
            return None

        lane_id = random.choice(list(self._lane_state.keys()))
        state = self._lane_state[lane_id]

        # Mean-reverting random walk with intraday volatility
        volatility = random.uniform(0.003, 0.015)
        mean_reversion = 0.02 * (state["base_price"] - state["price"]) / state["base_price"]
        shock = random.gauss(0, 1) * volatility
        drift = mean_reversion + shock

        new_price = max(state["price"] * (1 + drift), state["base_price"] * 0.5)
        price_change = new_price - state["price"]
        price_change_pct = (price_change / state["price"]) * 100 if state["price"] else 0
        state["price"] = new_price

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Store tick
        conn = _connect()
        c = conn.cursor()
        c.execute(
            """INSERT INTO live_ticks
               (timestamp, lane_id, lane_name, origin_port, destination_port,
                container_type, price_usd, price_change, price_change_pct, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, lane_id, state["lane_name"], state["origin_port"],
             state["destination_port"], state["container_type"],
             round(new_price, 2), round(price_change, 2),
             round(price_change_pct, 4), random.randint(1, 5)),
        )
        tick_id = c.lastrowid
        conn.commit()
        conn.close()

        self.tick_count += 1

        return {
            "type": "tick",
            "tick_id": tick_id,
            "timestamp": now,
            "lane_id": lane_id,
            "lane_name": state["lane_name"],
            "origin": state["origin_port"],
            "destination": state["destination_port"],
            "container_type": state["container_type"],
            "price": round(new_price, 2),
            "price_change": round(price_change, 2),
            "price_change_pct": round(price_change_pct, 2),
        }

    def _get_lag_features(self, lane_id, current_price):
        """Get price lag features from benchmark history for this lane."""
        conn = _connect()
        query = """
            SELECT bh.price_usd
            FROM (
                SELECT date, price_usd 
                FROM benchmark_history 
                WHERE lane_id = ? 
                ORDER BY date DESC 
                LIMIT 50
            ) bh
            ORDER BY bh.date ASC
        """
        df = pd.read_sql_query(query, conn, params=[lane_id])
        conn.close()

        prices_series = pd.concat([df["price_usd"], pd.Series([current_price])], ignore_index=True)
        prices_list = prices_series.tolist()[::-1] # most recent first
        
        # Quantitative features
        ema_4w = prices_series.ewm(span=4, adjust=False).mean()
        ema_12w = prices_series.ewm(span=12, adjust=False).mean()
        macd = ema_4w - ema_12w
        
        delta = prices_series.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean().fillna(0)
        ema_down = down.ewm(com=13, adjust=False).mean().fillna(0)
        rs = np.where(ema_down == 0, 100, ema_up / (ema_down + 1e-9))
        rsi = np.where(ema_down == 0, 100, 100 - (100 / (1 + rs)))
        
        roc_4w = prices_series.pct_change(periods=4).fillna(0)

        return {
            "price_lag_7d": prices_list[1] if len(prices_list) > 1 else current_price,
            "price_lag_14d": prices_list[2] if len(prices_list) > 2 else current_price,
            "price_lag_21d": prices_list[3] if len(prices_list) > 3 else current_price,
            "price_ma_4w": float(np.mean(prices_list[:min(4, len(prices_list))])),
            "price_volatility_4w": float(np.std(prices_list[:min(4, len(prices_list))])) if len(prices_list) > 1 else 0,
            "price_momentum": current_price - (prices_list[1] if len(prices_list) > 1 else current_price),
            "price_ema_4w": float(ema_4w.iloc[-1]),
            "price_ema_12w": float(ema_12w.iloc[-1]),
            "price_macd": float(macd.iloc[-1]),
            "price_rsi_14w": float(rsi[-1]) if len(rsi) > 0 else 50.0,
            "price_roc_4w": float(roc_4w.iloc[-1]),
        }

    def predict_tick(self, tick):
        """Run ML prediction for a tick."""
        if self.model is None or self.features is None or tick is None:
            return None

        lane_id = tick["lane_id"]
        state = self._lane_state.get(lane_id, {})
        current_price = tick["price"]
        now = datetime.now()

        distances = {
            ("Singapore", "New York"): 8285,
            ("Shanghai", "Los Angeles"): 5646,
            ("Shanghai", "Long Beach"): 5500,
            ("Dubai", "Mumbai"): 1044,
            ("Rotterdam", "New York"): 3650,
            ("Singapore", "Rotterdam"): 8760,
            ("Busan", "Los Angeles"): 5600,
            ("Hong Kong", "Los Angeles"): 5800,
        }
        distance = distances.get(
            (state.get("origin_port", ""), state.get("destination_port", "")), 5000
        )
        container_enc = 1 if state.get("container_type") == "40ft" else 0
        route_enc = self._route_encoders.get(state.get("lane_name", ""), 0)

        # Get lag features from benchmark history
        lag = self._get_lag_features(lane_id, current_price)
        cost_per_nm = current_price / distance if distance else 0
        premium = current_price / lag["price_ema_12w"] if lag["price_ema_12w"] else 1.0

        predictions = {}
        for horizon in [14, 21]:
            fdate = now + timedelta(days=horizon)
            month = fdate.month
            dow = fdate.weekday()
            quarter = (month - 1) // 3 + 1
            woy = int(fdate.isocalendar()[1])
            is_peak = 1 if month in [9, 10, 11, 12, 1, 2] else 0
            doy = fdate.timetuple().tm_yday

            feature_values = [
                current_price, distance, fdate.year, month, dow, quarter, woy,
                is_peak, doy, container_enc, route_enc, horizon,
                lag["price_lag_7d"],
                lag["price_lag_14d"],
                lag["price_lag_21d"],
                lag["price_ma_4w"],
                lag["price_volatility_4w"],
                lag["price_momentum"],
                lag["price_ema_4w"],
                lag["price_ema_12w"],
                lag["price_macd"],
                lag["price_rsi_14w"],
                lag["price_roc_4w"],
                cost_per_nm,
                premium,
            ]
            X = pd.DataFrame(
                [feature_values],
                columns=self.features,
            )
            # Model predicts % change — convert back to dollar forecast
            pct_change = float(self.model.predict(X)[0])
            predictions[f"predicted_{horizon}d"] = round(current_price * (1 + pct_change), 2)

        variance = current_price * 0.08
        pred_14 = predictions["predicted_14d"]
        predictions["predicted_low_14d"] = round(pred_14 - variance, 2)
        predictions["predicted_high_14d"] = round(pred_14 + variance, 2)

        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        # Store prediction
        conn = _connect()
        c = conn.cursor()
        c.execute(
            """INSERT INTO live_predictions
               (tick_id, lane_id, timestamp, current_price, predicted_14d, predicted_21d,
                predicted_low_14d, predicted_high_14d, model_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tick["tick_id"], lane_id, timestamp, current_price,
             round(pred_14, 2), round(predictions["predicted_21d"], 2),
             predictions["predicted_low_14d"], predictions["predicted_high_14d"],
             "xgb_benchmark_v1"),
        )
        conn.commit()
        conn.close()

        self.total_predictions += 1

        return {
            "type": "prediction",
            "tick_id": tick["tick_id"],
            "lane_id": lane_id,
            "lane_name": tick["lane_name"],
            "timestamp": timestamp,
            "current_price": round(current_price, 2),
            "predicted_14d": round(pred_14, 2),
            "predicted_21d": round(predictions["predicted_21d"], 2),
            "predicted_low_14d": predictions["predicted_low_14d"],
            "predicted_high_14d": predictions["predicted_high_14d"],
            "spread": round(predictions["predicted_high_14d"] - predictions["predicted_low_14d"], 2),
        }

    def check_accuracy(self, tick):
        """Compare current actual price with what was predicted earlier."""
        conn = _connect()

        # Find predictions made ~14 ticks ago for this lane
        query = """
            SELECT lp.predicted_14d, lp.current_price, lp.timestamp
            FROM live_predictions lp
            WHERE lp.lane_id = ?
            ORDER BY lp.pred_id DESC
            LIMIT 1 OFFSET 14
        """
        df = pd.read_sql_query(query, conn, params=[tick["lane_id"]])

        if df.empty:
            conn.close()
            return None

        predicted_price = float(df.iloc[0]["predicted_14d"])
        actual_price = tick["price"]
        error_abs = abs(actual_price - predicted_price)
        error_pct = (error_abs / predicted_price * 100) if predicted_price else 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        c = conn.cursor()
        c.execute(
            """INSERT INTO prediction_accuracy
               (timestamp, lane_id, lane_name, predicted_price, actual_price,
                error_abs, error_pct, prediction_age_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, tick["lane_id"], tick["lane_name"],
             round(predicted_price, 2), round(actual_price, 2),
             round(error_abs, 2), round(error_pct, 2), 14),
        )
        conn.commit()
        conn.close()

        return {
            "type": "accuracy",
            "timestamp": now,
            "lane_name": tick["lane_name"],
            "predicted": round(predicted_price, 2),
            "actual": round(actual_price, 2),
            "error_abs": round(error_abs, 2),
            "error_pct": round(error_pct, 2),
        }

    def get_accuracy_stats(self):
        """Get rolling accuracy statistics."""
        conn = _connect()
        query = """
            SELECT
                COUNT(*) as total_comparisons,
                AVG(error_abs) as mae,
                AVG(error_pct) as mape,
                MIN(error_pct) as best_pct,
                MAX(error_pct) as worst_pct
            FROM prediction_accuracy
            WHERE timestamp > datetime('now', '-1 hour')
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty or df.iloc[0]["total_comparisons"] == 0:
            return {"total_comparisons": 0, "mae": 0, "mape": 0, "best_pct": 0, "worst_pct": 0}

        row = df.iloc[0]
        return {
            "total_comparisons": int(row["total_comparisons"]),
            "mae": round(float(row["mae"] or 0), 2),
            "mape": round(float(row["mape"] or 0), 2),
            "best_pct": round(float(row["best_pct"] or 0), 2),
            "worst_pct": round(float(row["worst_pct"] or 0), 2),
        }

    def get_recent_accuracy(self, limit=50):
        """Get recent accuracy records for charting."""
        conn = _connect()
        df = pd.read_sql_query(
            "SELECT * FROM prediction_accuracy ORDER BY accuracy_id DESC LIMIT ?",
            conn, params=[limit]
        )
        conn.close()
        records = df.to_dict(orient="records")
        for r in records:
            for k, v in r.items():
                if isinstance(v, (np.integer,)):
                    r[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    r[k] = float(v)
        return records

    def get_lane_prices(self):
        """Get current simulated prices for all lanes."""
        return {
            lid: {
                "lane_id": s["lane_id"],
                "lane_name": s["lane_name"],
                "origin": s["origin_port"],
                "destination": s["destination_port"],
                "container_type": s["container_type"],
                "price": round(s["price"], 2),
                "base_price": round(s["base_price"], 2),
                "change_pct": round(
                    (s["price"] - s["base_price"]) / s["base_price"] * 100, 2
                ),
            }
            for lid, s in self._lane_state.items()
        }

    def get_recent_ticks(self, limit=100):
        """Get recent ticks for charting."""
        conn = _connect()
        df = pd.read_sql_query(
            "SELECT * FROM live_ticks ORDER BY tick_id DESC LIMIT ?",
            conn, params=[limit],
        )
        conn.close()
        records = df.to_dict(orient="records")
        for r in records:
            for k, v in r.items():
                if isinstance(v, (np.integer,)):
                    r[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    r[k] = float(v)
        return records

    def get_retrain_log(self):
        """Get retraining history."""
        conn = _connect()
        df = pd.read_sql_query(
            "SELECT * FROM retrain_log ORDER BY retrain_id DESC LIMIT 10", conn
        )
        conn.close()
        return df.to_dict(orient="records")

    def retrain_model(self, trigger="manual"):
        """Retrain the XGBoost model from accumulated data."""
        if self._retrain_lock.locked():
            return {
                "status": "busy",
                "error": "Retrain already in progress.",
                "trigger": trigger,
            }

        with self._retrain_lock:
            from pipeline.build_train_data import prepare_training_data
            from sklearn.metrics import mean_absolute_error, r2_score
            import xgboost as xgb
            from ml.train_model import _temporal_split

            _broadcast(json.dumps({
                "type": "system",
                "message": f"RETRAINING MODEL ({trigger})...",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }))

            X, y, df = prepare_training_data()
            if X is None or len(X) == 0:
                return {
                    "status": "failed",
                    "error": "No benchmark training data available for retraining.",
                    "trigger": trigger,
                }

            X_train, X_test, y_train, y_test = _temporal_split(X, y, df, test_ratio=0.2)

            model = xgb.XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
            )
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

            y_pred = model.predict(X_test)
            mae = float(mean_absolute_error(y_test, y_pred))
            r2 = float(r2_score(y_test, y_pred))

            # Backup and save
            if os.path.exists(MODEL_PATH):
                shutil.copy2(MODEL_PATH, BACKUP_MODEL_PATH)
            joblib.dump(model, MODEL_PATH)

            # Reload
            self.model = model

            # Log
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = _connect()
            c = conn.cursor()
            c.execute(
                """INSERT INTO retrain_log (timestamp, train_samples, test_mae, test_r2, model_path, trigger)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (now, len(X_train), round(mae, 2), round(r2, 4), MODEL_PATH, trigger),
            )
            conn.commit()
            conn.close()

            result = {
                "status": "ok",
                "type": "retrain",
                "timestamp": now,
                "train_samples": len(X_train),
                "test_mae": round(mae, 2),
                "test_r2": round(r2, 4),
                "trigger": trigger,
            }
            _broadcast(json.dumps(result))
            return result

    def _pipeline_loop(self):
        """Main background loop: generate tick → predict → check accuracy → broadcast."""
        while self.running:
            try:
                tick = self.generate_tick()
                if tick is None:
                    time.sleep(1)
                    continue

                prediction = self.predict_tick(tick)
                accuracy = self.check_accuracy(tick)

                # Build combined event
                event = {
                    "type": "update",
                    "tick": tick,
                    "prediction": prediction,
                    "accuracy": accuracy,
                    "engine_stats": {
                        "ticks": self.tick_count,
                        "predictions": self.total_predictions,
                        "uptime_s": int(time.time() - self.start_time) if self.start_time else 0,
                    },
                }
                _broadcast(json.dumps(event))

                # Vary interval for realistic feel
                time.sleep(random.uniform(1.5, 3.5))

            except Exception as e:
                print(f"[STREAM ERROR] {e}")
                time.sleep(2)

    def _retrain_scheduler(self):
        """Check for weekly retraining (Sunday midnight)."""
        while self.running:
            now = datetime.now()
            # Retrain on Sunday at midnight (or first tick past midnight)
            if now.weekday() == 6 and now.hour == 0 and now.minute < 5:
                self.retrain_model(trigger="scheduled_weekly")
                time.sleep(3600)  # Sleep 1 hour after retraining
            time.sleep(60)

    def start(self):
        """Start the streaming engine."""
        if self.running:
            return
        self.running = True
        self.start_time = time.time()

        # Pipeline thread
        t1 = threading.Thread(target=self._pipeline_loop, daemon=True)
        t1.start()

        # Retrain scheduler thread
        t2 = threading.Thread(target=self._retrain_scheduler, daemon=True)
        t2.start()

        print("[OK] Stream engine started (tick every 1.5-3.5s)")

    def stop(self):
        self.running = False


# Singleton engine instance
engine = StreamEngine()
