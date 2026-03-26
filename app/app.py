"""
Route Cost Forecasting — Live Streaming Dashboard
Flask + SSE + XGBoost + Background Pipeline

Design: Prime Intellect / Evil Rabbit / Factory AI aesthetic
- Ultra-dark, data-dense, terminal-inspired
- Stock-market-style real-time streaming
- CRT scanline overlay on terminal panel
"""

import json
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3
import time
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from flask import Flask, Response, jsonify, render_template_string, request

from app.stream_engine import engine, subscribe, unsubscribe

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_model.joblib")
FEATURES_PATH = os.path.join(PROJECT_ROOT, "ml", "benchmark_features.joblib")

app = Flask(__name__)


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ─── API Endpoints ──────────────────────────────────────────────

@app.route("/api/prices")
def api_prices():
    prices = engine.get_lane_prices()
    return jsonify(list(prices.values()))


@app.route("/api/stats")
def api_stats():
    prices = engine.get_lane_prices()
    vals = [p["price"] for p in prices.values()]
    accuracy = engine.get_accuracy_stats()
    return jsonify({
        "total_lanes": len(vals),
        "avg_price": round(float(np.mean(vals)), 2) if vals else 0,
        "min_price": round(float(np.min(vals)), 2) if vals else 0,
        "max_price": round(float(np.max(vals)), 2) if vals else 0,
        "ticks_generated": engine.tick_count,
        "predictions_made": engine.total_predictions,
        "uptime_s": int(time.time() - engine.start_time) if engine.start_time else 0,
        "accuracy": accuracy,
    })


@app.route("/api/ticks")
def api_ticks():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(engine.get_recent_ticks(limit))


@app.route("/api/accuracy")
def api_accuracy():
    return jsonify({
        "stats": engine.get_accuracy_stats(),
        "recent": engine.get_recent_accuracy(50),
    })


@app.route("/api/retrain_log")
def api_retrain_log():
    return jsonify(engine.get_retrain_log())


@app.route("/api/retrain", methods=["POST"])
def api_retrain():
    result = engine.retrain_model(trigger="manual")
    if result:
        return jsonify(result)
    return jsonify({"error": "Retrain failed — no training data"}), 500


@app.route("/stream")
def stream():
    """Server-Sent Events endpoint for real-time data."""
    def event_stream():
        q = subscribe()
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {data}\n\n"
                except Exception:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            unsubscribe(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Dashboard HTML ─────────────────────────────────────────────

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ROUTE COST FORECASTER // LIVE</title>
    <meta name="description" content="Legacy sandbox UI for the benchmark model">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        /* ═══ DESIGN SYSTEM ═══
           Prime Intellect: ultra-dark, data-first, sharp mono
           Evil Rabbit / Vercel: monochrome, stark contrast, rare accents
           Factory AI: terminal feed, CRT overlay, industrial status
        */
        :root {
            --black: #000000;
            --bg-0: #020204;
            --bg-1: #08080c;
            --bg-2: #0e0e14;
            --bg-3: #16161e;
            --bg-4: #1e1e28;
            --border-0: rgba(255,255,255,0.04);
            --border-1: rgba(255,255,255,0.08);
            --border-2: rgba(255,255,255,0.12);
            --text-0: #ffffff;
            --text-1: #b0b0be;
            --text-2: #6a6a7e;
            --text-3: #3a3a4e;
            --green: #00ff88;
            --green-dim: #00cc6a;
            --red: #ff3366;
            --red-dim: #cc2952;
            --cyan: #00ccff;
            --amber: #ffaa00;
            --purple: #aa77ff;
            --mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
            --sans: 'Inter', -apple-system, system-ui, sans-serif;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; overflow: hidden; }

        body {
            font-family: var(--sans);
            background: var(--black);
            color: var(--text-0);
        }

        /* ═══ LAYOUT ═══ */
        .shell {
            display: grid;
            grid-template-columns: 360px 1fr;
            grid-template-rows: 48px 1fr;
            height: 100vh;
            width: 100vw;
        }

        /* ═══ TOP BAR (ticker) ═══ */
        .ticker-bar {
            grid-column: 1 / -1;
            background: var(--bg-1);
            border-bottom: 1px solid var(--border-0);
            display: flex;
            align-items: center;
            overflow: hidden;
            position: relative;
        }

        .ticker-label {
            flex-shrink: 0;
            padding: 0 20px;
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-2);
            border-right: 1px solid var(--border-0);
            height: 100%;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .ticker-dot {
            width: 5px; height: 5px;
            background: var(--green);
            border-radius: 50%;
            box-shadow: 0 0 6px var(--green);
            animation: blink 1.5s ease-in-out infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .ticker-scroll {
            flex: 1;
            display: flex;
            align-items: center;
            gap: 0;
            overflow: hidden;
            white-space: nowrap;
        }

        .ticker-item {
            flex-shrink: 0;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 0 16px;
            font-family: var(--mono);
            font-size: 11px;
            border-right: 1px solid var(--border-0);
            height: 100%;
            transition: background 0.3s;
        }

        .ticker-item:hover {
            background: var(--bg-2);
        }

        .ticker-name {
            color: var(--text-1);
            font-weight: 500;
        }

        .ticker-price {
            color: var(--text-0);
            font-weight: 700;
        }

        .ticker-change {
            font-weight: 600;
            font-size: 10px;
        }

        .ticker-change.up { color: var(--green); }
        .ticker-change.down { color: var(--red); }

        /* ═══ LEFT PANEL: TERMINAL ═══ */
        .terminal-panel {
            background: var(--bg-0);
            border-right: 1px solid var(--border-0);
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
        }

        /* CRT scanline overlay */
        .terminal-panel::after {
            content: '';
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 1px,
                rgba(0,0,0,0.15) 1px,
                rgba(0,0,0,0.15) 2px
            );
            pointer-events: none;
            z-index: 10;
        }

        .terminal-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-0);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            z-index: 11;
        }

        .terminal-title {
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-2);
        }

        .terminal-status {
            display: flex;
            align-items: center;
            gap: 6px;
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 600;
            color: var(--green);
        }

        .terminal-feed {
            flex: 1;
            overflow-y: auto;
            padding: 12px 16px;
            display: flex;
            flex-direction: column;
            gap: 2px;
            position: relative;
            z-index: 5;
        }

        .terminal-feed::-webkit-scrollbar { width: 3px; }
        .terminal-feed::-webkit-scrollbar-track { background: transparent; }
        .terminal-feed::-webkit-scrollbar-thumb { background: var(--border-1); border-radius: 2px; }

        .log-line {
            font-family: var(--mono);
            font-size: 10px;
            line-height: 1.8;
            color: var(--text-2);
            animation: logIn 0.2s ease-out;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .log-line.highlight {
            color: var(--text-1);
        }

        @keyframes logIn {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .log-ts { color: var(--text-3); }
        .log-lane { color: var(--cyan); }
        .log-price { color: var(--green); font-weight: 600; }
        .log-pred { color: var(--amber); }
        .log-err { color: var(--red); }
        .log-sys { color: var(--purple); font-weight: 600; }

        .terminal-footer {
            padding: 10px 20px;
            border-top: 1px solid var(--border-0);
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
            display: flex;
            justify-content: space-between;
            position: relative;
            z-index: 11;
        }

        /* ═══ MAIN CONTENT ═══ */
        .main {
            background: var(--bg-0);
            overflow-y: auto;
            padding: 28px 36px;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .main::-webkit-scrollbar { width: 4px; }
        .main::-webkit-scrollbar-thumb { background: var(--border-1); border-radius: 2px; }

        /* ═══ HEADER ═══ */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .brand {
            font-family: var(--mono);
            font-size: 20px;
            font-weight: 300;
            letter-spacing: -0.5px;
        }

        .brand strong {
            font-weight: 800;
        }

        .brand-sub {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 4px;
        }

        .header-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .btn {
            font-family: var(--mono);
            font-size: 10px;
            font-weight: 600;
            padding: 7px 14px;
            border: 1px solid var(--border-1);
            background: transparent;
            color: var(--text-1);
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.2s;
        }

        .btn:hover {
            border-color: var(--text-0);
            color: var(--text-0);
        }

        .btn-accent {
            border-color: var(--green-dim);
            color: var(--green);
        }

        .btn-accent:hover {
            background: rgba(0,255,136,0.08);
            border-color: var(--green);
            box-shadow: 0 0 12px rgba(0,255,136,0.1);
        }

        /* ═══ KPI ROW ═══ */
        .kpi-row {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
        }

        .kpi {
            background: var(--bg-1);
            border: 1px solid var(--border-0);
            padding: 18px 20px;
            position: relative;
        }

        .kpi::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 1px;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .kpi:hover::before { opacity: 1; }
        .kpi:nth-child(1)::before { background: linear-gradient(90deg, var(--cyan), transparent); }
        .kpi:nth-child(2)::before { background: linear-gradient(90deg, var(--green), transparent); }
        .kpi:nth-child(3)::before { background: linear-gradient(90deg, var(--amber), transparent); }
        .kpi:nth-child(4)::before { background: linear-gradient(90deg, var(--purple), transparent); }
        .kpi:nth-child(5)::before { background: linear-gradient(90deg, var(--red), transparent); }

        .kpi-label {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 8px;
        }

        .kpi-value {
            font-family: var(--mono);
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -1px;
        }

        .kpi-sub {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
            margin-top: 6px;
        }

        /* ═══ CHARTS ═══ */
        .chart-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .chart-panel {
            background: var(--bg-1);
            border: 1px solid var(--border-0);
            padding: 20px;
        }

        .chart-panel.wide {
            grid-column: 1 / -1;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .chart-title {
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 700;
            color: var(--text-2);
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .chart-badge {
            font-family: var(--mono);
            font-size: 8px;
            font-weight: 700;
            padding: 3px 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
            background: rgba(0,255,136,0.06);
            color: var(--green);
            border: 1px solid rgba(0,255,136,0.12);
        }

        /* ═══ TABLE ═══ */
        .table-panel {
            background: var(--bg-1);
            border: 1px solid var(--border-0);
            overflow: hidden;
        }

        .tbl {
            width: 100%;
            border-collapse: collapse;
            font-family: var(--mono);
            font-size: 11px;
        }

        .tbl thead {
            background: var(--bg-2);
        }

        .tbl th {
            text-align: left;
            padding: 12px 14px;
            font-size: 8px;
            font-weight: 700;
            color: var(--text-3);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-bottom: 1px solid var(--border-0);
        }

        .tbl td {
            padding: 10px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.02);
            color: var(--text-1);
        }

        .tbl tbody tr {
            transition: background 0.15s;
        }

        .tbl tbody tr:hover {
            background: var(--bg-3);
        }

        .price-up { color: var(--green); }
        .price-down { color: var(--red); }

        .tag {
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
            letter-spacing: 0.5px;
        }

        .tag-feu { color: var(--cyan); background: rgba(0,204,255,0.08); }
        .tag-teu { color: var(--purple); background: rgba(170,119,255,0.08); }

        /* ═══ MODEL HEALTH ═══ */
        .model-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
        }

        .model-card {
            background: var(--bg-1);
            border: 1px solid var(--border-0);
            padding: 20px;
        }

        .model-card-title {
            font-family: var(--mono);
            font-size: 9px;
            font-weight: 700;
            color: var(--text-3);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 12px;
        }

        .model-metric {
            font-family: var(--mono);
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .model-desc {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
        }

        /* ═══ FOOTER ═══ */
        .footer-disclaimer {
            font-family: var(--mono);
            font-size: 9px;
            color: var(--text-3);
            padding: 16px 0;
            border-top: 1px solid var(--border-0);
            line-height: 1.8;
        }

        .footer-disclaimer strong {
            color: var(--amber);
        }
    </style>
</head>
<body>
<div class="shell">

    <!-- ═══ TICKER BAR ═══ -->
    <div class="ticker-bar">
        <div class="ticker-label">
            <div class="ticker-dot"></div>
            LIVE
        </div>
        <div class="ticker-scroll" id="ticker-scroll"></div>
    </div>

    <!-- ═══ TERMINAL PANEL ═══ -->
    <div class="terminal-panel">
        <div class="terminal-header">
            <div class="terminal-title">Stream Log</div>
            <div class="terminal-status">
                <div class="ticker-dot"></div>
                ACTIVE
            </div>
        </div>
        <div class="terminal-feed" id="terminal-feed"></div>
        <div class="terminal-footer">
            <span id="tick-counter">0 ticks</span>
            <span id="pred-counter">0 predictions</span>
        </div>
    </div>

    <!-- ═══ MAIN CONTENT ═══ -->
    <div class="main">

        <div class="header">
            <div>
                <div class="brand">ROUTE COST <strong>FORECASTER</strong></div>
                <div class="brand-sub">Legacy Sandbox UI &middot; Not Part Of Real-Data Planner Training</div>
            </div>
            <div class="header-controls">
                <div class="terminal-status" style="margin-right:12px">
                    <div class="ticker-dot"></div>
                    <span id="uptime-display">00:00:00</span>
                </div>
                <button class="btn btn-accent" onclick="triggerRetrain()">Retrain Model</button>
            </div>
        </div>

        <!-- KPIs -->
        <div class="kpi-row">
            <div class="kpi">
                <div class="kpi-label">Avg Lane Price</div>
                <div class="kpi-value" id="kpi-avg" style="color:var(--cyan)">--</div>
                <div class="kpi-sub">across all lanes</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Total Ticks</div>
                <div class="kpi-value" id="kpi-ticks" style="color:var(--green)">0</div>
                <div class="kpi-sub">market events</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Predictions</div>
                <div class="kpi-value" id="kpi-preds" style="color:var(--amber)">0</div>
                <div class="kpi-sub">model inferences</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Sandbox MAPE</div>
                <div class="kpi-value" id="kpi-mape" style="color:var(--purple)">--</div>
                <div class="kpi-sub">sandbox evaluation</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Model MAE</div>
                <div class="kpi-value" id="kpi-mae" style="color:var(--red)">--</div>
                <div class="kpi-sub">absolute error</div>
            </div>
        </div>

        <!-- Charts -->
        <div class="chart-grid">
            <div class="chart-panel wide">
                <div class="chart-header">
                    <div class="chart-title">Live Price Stream</div>
                    <div class="chart-badge">Streaming</div>
                </div>
                <div style="height:220px;position:relative">
                    <canvas id="liveChart"></canvas>
                </div>
            </div>
            <div class="chart-panel">
                <div class="chart-header">
                    <div class="chart-title">Prediction vs Sandbox Price</div>
                    <div class="chart-badge">Sandbox</div>
                </div>
                <div style="height:200px;position:relative">
                    <canvas id="accuracyChart"></canvas>
                </div>
            </div>
            <div class="chart-panel">
                <div class="chart-header">
                    <div class="chart-title">Sandbox Error Distribution</div>
                    <div class="chart-badge">Simulated</div>
                </div>
                <div style="height:200px;position:relative">
                    <canvas id="errorChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Forecast Table -->
        <div class="table-panel">
            <table class="tbl">
                <thead>
                    <tr>
                        <th>Route</th>
                        <th>Type</th>
                        <th>Live Price</th>
                        <th>Base Price</th>
                        <th>Change</th>
                        <th>14d Forecast</th>
                        <th>21d Forecast</th>
                        <th>Spread</th>
                    </tr>
                </thead>
                <tbody id="forecast-body"></tbody>
            </table>
        </div>

        <!-- Model Health -->
        <div class="model-grid" id="model-grid">
            <div class="model-card">
                <div class="model-card-title">Model Version</div>
                <div class="model-metric" style="color:var(--cyan)">XGBoost</div>
                <div class="model-desc">benchmark_model.joblib</div>
            </div>
            <div class="model-card">
                <div class="model-card-title">Comparisons</div>
                <div class="model-metric" id="model-comparisons" style="color:var(--green)">0</div>
                <div class="model-desc">prediction vs simulated checks</div>
            </div>
            <div class="model-card">
                <div class="model-card-title">Last Retrain</div>
                <div class="model-metric" id="model-retrain" style="color:var(--amber);font-size:14px">--</div>
                <div class="model-desc">legacy sandbox retrain</div>
            </div>
        </div>

        <div class="footer-disclaimer">
            <strong>LEGACY SANDBOX UI</strong> &mdash; This page is kept only for interface testing around the old benchmark model.
            It is not part of the real-data planner workflow. For portfolio use, present the planner trained on `quote_history` or `market_rate_history`, not this sandbox stream.
        </div>
    </div>
</div>

<script>
// ═══ CHART.JS DEFAULTS ═══
Chart.defaults.color = '#3a3a4e';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 10;

function fmt$(v) { return '$' + Number(v).toLocaleString('en-US', {maximumFractionDigits:0}); }
function fmtPct(v) { return (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%'; }
function fmtTime(s) {
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
    return [h,m,sec].map(x => String(x).padStart(2,'0')).join(':');
}

// ═══ STATE ═══
const laneData = {};  // lane_id -> { prices: [], predictions: [] }
let tickHistory = [];
let accuracyHistory = [];
let startTime = Date.now();

// ═══ LIVE PRICE CHART ═══
const liveCtx = document.getElementById('liveChart').getContext('2d');
const liveChart = new Chart(liveCtx, {
    type: 'line',
    data: { labels: [], datasets: [] },
    options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 0 },
        plugins: { legend: { display: false } },
        scales: {
            x: { display: true, grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { maxTicksLimit: 8 } },
            y: { position: 'right', grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { callback: v => '$'+v } }
        }
    }
});

// ═══ ACCURACY CHART ═══
const accCtx = document.getElementById('accuracyChart').getContext('2d');
const accuracyChart = new Chart(accCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            { label: 'Predicted', data: [], borderColor: '#ffaa00', borderWidth: 1.5, pointRadius: 2, tension: 0.3 },
            { label: 'Actual', data: [], borderColor: '#00ff88', borderWidth: 1.5, pointRadius: 2, tension: 0.3 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 0 },
        plugins: { legend: { labels: { boxWidth: 8, padding: 8 } } },
        scales: {
            x: { display: false },
            y: { position: 'right', grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { callback: v => '$'+v } }
        }
    }
});

// ═══ ERROR CHART ═══
const errCtx = document.getElementById('errorChart').getContext('2d');
const errorChart = new Chart(errCtx, {
    type: 'bar',
    data: { labels: [], datasets: [{ data: [], backgroundColor: 'rgba(255,51,102,0.4)', borderColor: '#ff3366', borderWidth: 1 }] },
    options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 0 },
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: { position: 'right', grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { callback: v => v+'%' } }
        }
    }
});

// ═══ TERMINAL LOGGING ═══
const feed = document.getElementById('terminal-feed');
const MAX_LOG_LINES = 200;

function addLog(html, cls='') {
    const div = document.createElement('div');
    div.className = 'log-line' + (cls ? ' '+cls : '');
    div.innerHTML = html;
    feed.insertBefore(div, feed.firstChild);
    while (feed.children.length > MAX_LOG_LINES) feed.removeChild(feed.lastChild);
}

// ═══ TICKER UPDATE ═══
function updateTicker(prices) {
    const scroll = document.getElementById('ticker-scroll');
    scroll.innerHTML = prices.map(p => {
        const cls = p.change_pct >= 0 ? 'up' : 'down';
        const arrow = p.change_pct >= 0 ? '&#9650;' : '&#9660;';
        return `<div class="ticker-item">
            <span class="ticker-name">${p.origin}→${p.destination}</span>
            <span class="ticker-price">${fmt$(p.price)}</span>
            <span class="ticker-change ${cls}">${arrow} ${Math.abs(p.change_pct).toFixed(1)}%</span>
        </div>`;
    }).join('');
}

// ═══ TABLE UPDATE ═══
let latestPredictions = {};

function updateTable(prices) {
    const tbody = document.getElementById('forecast-body');
    tbody.innerHTML = prices.map(p => {
        const pred = latestPredictions[p.lane_id] || {};
        const cls = p.change_pct >= 0 ? 'price-up' : 'price-down';
        const tag = p.container_type === '40ft' ? 'tag-feu' : 'tag-teu';
        return `<tr>
            <td style="color:var(--text-0);font-weight:500">${p.origin} → ${p.destination}</td>
            <td><span class="tag ${tag}">${p.container_type}</span></td>
            <td style="font-weight:700">${fmt$(p.price)}</td>
            <td style="color:var(--text-2)">${fmt$(p.base_price)}</td>
            <td class="${cls}">${fmtPct(p.change_pct)}</td>
            <td>${pred.predicted_14d ? fmt$(pred.predicted_14d) : '--'}</td>
            <td>${pred.predicted_21d ? fmt$(pred.predicted_21d) : '--'}</td>
            <td style="color:var(--text-2)">${pred.spread ? fmt$(pred.spread) : '--'}</td>
        </tr>`;
    }).join('');
}

// ═══ SSE CONNECTION ═══
let evtSource = null;

function connectSSE() {
    if (evtSource) evtSource.close();
    evtSource = new EventSource('/stream');

    evtSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'heartbeat') return;
            if (data.type === 'update') handleUpdate(data);
            if (data.type === 'retrain') handleRetrain(data);
            if (data.type === 'system') addLog(`<span class="log-sys">[SYS] ${data.message}</span>`, 'highlight');
        } catch(err) { console.error('SSE parse error:', err); }
    };

    evtSource.onerror = function() {
        addLog('<span class="log-err">[CONN] Stream disconnected. Reconnecting...</span>', 'highlight');
    };
}

function handleUpdate(data) {
    const tick = data.tick;
    const pred = data.prediction;
    const acc = data.accuracy;
    const stats = data.engine_stats;

    // Terminal log
    const ts = tick.timestamp.split(' ')[1];
    const chgCls = tick.price_change >= 0 ? 'log-price' : 'log-err';
    const arrow = tick.price_change >= 0 ? '▲' : '▼';
    let logHtml = `<span class="log-ts">${ts}</span> <span class="log-lane">${tick.lane_name}</span> ` +
        `<span class="${chgCls}">${fmt$(tick.price)} ${arrow}${Math.abs(tick.price_change_pct).toFixed(2)}%</span>`;
    if (pred) {
        logHtml += ` <span class="log-pred">→ 14d:${fmt$(pred.predicted_14d)}</span>`;
    }
    if (acc) {
        logHtml += ` <span class="log-err">err:${acc.error_pct.toFixed(1)}%</span>`;
    }
    addLog(logHtml, 'highlight');

    // Update counters
    document.getElementById('tick-counter').textContent = stats.ticks + ' ticks';
    document.getElementById('pred-counter').textContent = stats.predictions + ' preds';
    document.getElementById('kpi-ticks').textContent = stats.ticks.toLocaleString();
    document.getElementById('kpi-preds').textContent = stats.predictions.toLocaleString();
    document.getElementById('uptime-display').textContent = fmtTime(stats.uptime_s);

    // Store prediction
    if (pred) {
        latestPredictions[tick.lane_id] = pred;
    }

    // Update live chart
    tickHistory.push({ ts: ts, price: tick.price, lane: tick.lane_name });
    if (tickHistory.length > 60) tickHistory.shift();
    liveChart.data.labels = tickHistory.map(t => t.ts);
    liveChart.data.datasets = [{
        data: tickHistory.map(t => t.price),
        borderColor: '#00ff88',
        borderWidth: 1.5,
        backgroundColor: 'rgba(0,255,136,0.05)',
        fill: true,
        pointRadius: 0,
        tension: 0.3
    }];
    liveChart.update('none');

    // Accuracy chart
    if (acc) {
        accuracyHistory.push(acc);
        if (accuracyHistory.length > 30) accuracyHistory.shift();
        const labels = accuracyHistory.map((a, i) => i);
        accuracyChart.data.labels = labels;
        accuracyChart.data.datasets[0].data = accuracyHistory.map(a => a.predicted);
        accuracyChart.data.datasets[1].data = accuracyHistory.map(a => a.actual);
        accuracyChart.update('none');

        errorChart.data.labels = labels;
        errorChart.data.datasets[0].data = accuracyHistory.map(a => a.error_pct);
        errorChart.update('none');
    }
}

function handleRetrain(data) {
    addLog(`<span class="log-sys">[RETRAIN] MAE:$${data.test_mae} R2:${data.test_r2} samples:${data.train_samples}</span>`, 'highlight');
    document.getElementById('model-retrain').textContent = data.timestamp;
}

// ═══ PERIODIC FULL REFRESH ═══
async function fullRefresh() {
    try {
        const [statsRes, pricesRes] = await Promise.all([
            fetch('/api/stats'), fetch('/api/prices')
        ]);
        const stats = await statsRes.json();
        const prices = await pricesRes.json();

        document.getElementById('kpi-avg').textContent = fmt$(stats.avg_price);
        document.getElementById('kpi-ticks').textContent = stats.ticks_generated.toLocaleString();
        document.getElementById('kpi-preds').textContent = stats.predictions_made.toLocaleString();

        if (stats.accuracy.total_comparisons > 0) {
            document.getElementById('kpi-mape').textContent = stats.accuracy.mape.toFixed(1) + '%';
            document.getElementById('kpi-mae').textContent = fmt$(stats.accuracy.mae);
            document.getElementById('model-comparisons').textContent = stats.accuracy.total_comparisons;
        }

        updateTicker(prices);
        updateTable(prices);
    } catch(e) { console.error('Refresh error:', e); }
}

async function triggerRetrain() {
    addLog('<span class="log-sys">[SYS] Manual retrain triggered...</span>', 'highlight');
    try {
        const res = await fetch('/api/retrain', { method: 'POST' });
        const data = await res.json();
        if (data.error) {
            addLog(`<span class="log-err">[RETRAIN FAILED] ${data.error}</span>`, 'highlight');
        }
    } catch(e) {
        addLog(`<span class="log-err">[RETRAIN ERROR] ${e}</span>`, 'highlight');
    }
}

// ═══ INIT ═══
connectSSE();
fullRefresh();
setInterval(fullRefresh, 10000);
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


if __name__ == "__main__":
    engine.start()
    print("[OK] Route Cost Forecaster LIVE at http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
