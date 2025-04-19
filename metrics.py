"""
metrics.py: KPI and advanced metrics calculations for sales dashboard.
"""
import pandas as pd
import numpy as np
import holidays
import streamlit as st
import logging
from typing import Dict, Any
from functools import lru_cache


@lru_cache(maxsize=1)
def get_uk_holidays():
    return holidays.country_holidays('GB')


def compute_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate top-level KPIs for dashboard cards."""
    total_nett = df['Nett'].sum()
    total_orders = pd.Series(df['Order'].unique()).nunique()
    total_units = df['Qty'].sum()
    avg_order_value = total_nett / total_orders if total_orders else 0
    avg_margin = df['Margin_%'].mean() if not df.empty else 0
    uk_holidays = get_uk_holidays()
    def business_days(row):
        if pd.isnull(row['Entered']) or pd.isnull(row['Sent']):
            return None
        days = pd.bdate_range(row['Entered'], row['Sent'], holidays=uk_holidays)
        return len(days) - 1 if len(days) > 0 else 0
    turnaround_days = df.apply(business_days, axis=1)
    avg_turnaround = turnaround_days.dropna().mean() if not turnaround_days.dropna().empty else 0
    return {
        'Total Nett Sales': total_nett,
        'Total Orders': total_orders,
        'Total Units Sold': total_units,
        'Average Order Value': avg_order_value,
        'Average Margin %': avg_margin,
        'Average Turnaround': avg_turnaround
    }

@st.cache_data(show_spinner=False)
def compute_advanced_metrics(df: pd.DataFrame, forecast_days: int = 30) -> Dict[str, Any]:
    """Calculate moving averages, customer inactivity, forecast, and anomaly detection. Also forecasts unique order count per day."""
    from prophet import Prophet
    from datetime import timedelta
    results = {}
    # 7-day moving average of daily Nett
    daily = df.groupby('Entered')['Nett'].sum().sort_index()
    ma7 = daily.rolling(7).mean()
    results['7d_ma'] = ma7
    # Customers with no orders in past 30 days
    cutoff = df['Entered'].max() - pd.Timedelta(days=30)
    recent_customers = set(df[df['Entered'] > cutoff]['Name'])
    all_customers = set(df['Name'])
    inactive_customers = list(all_customers - recent_customers)
    results['inactive_customers'] = inactive_customers
    # Prophet forecast of Nett for next forecast_days with confidence intervals
    forecast_df = pd.DataFrame({'ds': daily.index, 'y': daily.values})
    daily_orders = df.groupby('Entered')['Order'].nunique().sort_index()
    forecast_orders_df = pd.DataFrame({'ds': daily_orders.index, 'y': daily_orders.values})
    if len(forecast_df) > 10 and len(forecast_orders_df) > 10:
        m_nett = Prophet(interval_width=0.95, daily_seasonality=True)
        m_nett.fit(forecast_df)
        future_nett = m_nett.make_future_dataframe(periods=forecast_days)
        forecast_nett = m_nett.predict(future_nett)
        forecast_nett.set_index('ds', inplace=True)
        results['forecast'] = forecast_nett['yhat']
        results['forecast_lower'] = forecast_nett['yhat_lower']
        results['forecast_upper'] = forecast_nett['yhat_upper']
        m_orders = Prophet(interval_width=0.95, daily_seasonality=True)
        m_orders.fit(forecast_orders_df)
        future_orders = m_orders.make_future_dataframe(periods=forecast_days)
        forecast_orders = m_orders.predict(future_orders)
        forecast_orders.set_index('ds', inplace=True)
        results['forecast_orders'] = forecast_orders['yhat']
    else:
        results['forecast'] = pd.Series(dtype=float)
        results['forecast_lower'] = pd.Series(dtype=float)
        results['forecast_upper'] = pd.Series(dtype=float)
        results['forecast_orders'] = pd.Series(dtype=float)
    mean = daily.mean()
    std = daily.std()
    low_days = daily[daily < mean - 2 * std].index.tolist()
    results['low_days'] = low_days
    logging.info("Advanced metrics calculated.")
    return results