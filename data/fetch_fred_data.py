"""
Real Macroeconomic Data Fetcher for Freight Benchmarks
Downloads Producer Price Index: Deep Sea Freight Transportation (PCU483111483111)
from the Federal Reserve Economic Data (FRED) API.

This replaces the synthetic data generation with real-world shipping cost trends
from 2014-present, capturing phenomena like the 2021-2022 COVID supply chain crisis.
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import sqlite3
import pandas as pd
import requests
from datetime import datetime, timedelta

# Free public FRED API key (often works without registration for simple pulls,
# but we'll use a known public proxy or simple download if needed).
# Actually, FRED allows direct CSV downloads without an API key.
FRED_SERIES_ID = "PCU483111483111"
FRED_CSV_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={FRED_SERIES_ID}"

DB_PATH = os.path.join(PROJECT_ROOT, "data", "shipments.db")


def download_fred_freight_index():
    """Download the historical monthly Deep Sea Freight PPI from FRED."""
    print(f"[*] Downloading real macroeconomic freight data from FRED (Series: {FRED_SERIES_ID})...")
    
    try:
        # Download directly as CSV (no API key required for this endpoint)
        df = pd.read_csv(FRED_CSV_URL)
        df.columns = ["date", "index_value"]
        
        # Clean data (remove '.' which FRED uses for missing values)
        df["index_value"] = pd.to_numeric(df["index_value"], errors="coerce")
        df = df.dropna()
        df["date"] = pd.to_datetime(df["date"])
        
        # Filter to last 5 years to be relevant (2019-2024)
        cutoff_date = pd.to_datetime("today") - pd.DateOffset(years=5)
        df = df[df["date"] >= cutoff_date].copy()
        
        print(f"[OK] Downloaded {len(df)} monthly records from {df['date'].min().strftime('%Y-%m')} to {df['date'].max().strftime('%Y-%m')}")
        return df
    
    except Exception as e:
        print(f"[!] Failed to download FRED data: {e}")
        return None

def interpolate_monthly_to_weekly(df_monthly):
    """
    FRED provides monthly data (first day of each month).
    We interpolate this to weekly data points to simulate high-frequency market ticks.
    """
    if df_monthly is None or df_monthly.empty:
        return None
        
    df_monthly = df_monthly.set_index("date")
    
    # Create daily date range and interpolate
    daily_idx = pd.date_range(start=df_monthly.index.min(), end=df_monthly.index.max(), freq='D')
    df_daily = df_monthly.reindex(daily_idx)
    df_daily["index_value"] = df_daily["index_value"].interpolate(method='linear')
    
    # Resample to weekly (every Monday)
    df_weekly = df_daily.resample('W-MON').last().reset_index()
    df_weekly.columns = ["date", "index_value"]
    
    return df_weekly

if __name__ == "__main__":
    df = download_fred_freight_index()
    if df is not None:
        print("\nMonthly Data Sample:")
        print(df.tail())
        
        df_weekly = interpolate_monthly_to_weekly(df)
        print(f"\nInterpolated Weekly Data Sample ({len(df_weekly)} weeks):")
        print(df_weekly.tail())
