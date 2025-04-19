"""
charts.py: Plotly chart generation for sales dashboard.
"""
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import pickle
import os
import logging
import re
from typing import Optional

def extract_uk_postcode(address: str) -> Optional[str]:
    """Extract the UK postcode from an address string."""
    if not isinstance(address, str):
        return None
    match = re.search(r"([A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2})", address.upper())
    if match:
        return match.group(1)
    return None

def line_chart(df: pd.DataFrame, ma_col: Optional[int] = None, freq: str = 'D') -> go.Figure:
    """Line chart of Nett by date with optional moving average overlay. freq: 'D', 'W', 'M'"""
    freq = 'ME' if freq == 'M' else freq
    df = df.copy()
    df = df[df['Entered'].notna()]
    df = df.set_index('Entered').sort_index()
    grouped = df['Nett'].resample(freq).sum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grouped.index, y=grouped.values, mode='lines', name='Nett'))
    if ma_col is not None:
        ma = grouped.rolling(ma_col).mean()
        fig.add_trace(go.Scatter(x=ma.index, y=ma.values, mode='lines', name=f'{ma_col}-day MA'))
    fig.update_layout(title='Nett Sales Over Time', xaxis_title='Date', yaxis_title='Nett', template='simple_white')
    return fig

def bar_chart(df: pd.DataFrame, by: str, value: str = 'Nett', top_n: int = 10) -> px.bar:
    """Bar chart for top N breakdowns by value."""
    grouped = df.groupby(by)[value].sum()
    grouped = pd.to_numeric(grouped, errors='coerce')  # Ensure numeric dtype
    grouped = grouped.nlargest(top_n).reset_index()
    fig = px.bar(grouped, x=by, y=value, title=f'Top {top_n} {by} by {value}', labels={by: by, value: value})
    return fig

def heatmap_chart(df: pd.DataFrame) -> px.imshow:
    """Heatmap of Route vs O/T sales (sum Nett)."""
    pivot = df.pivot_table(index='Route', columns='O/T', values='Nett', aggfunc='sum', fill_value=0, observed=False)
    pivot = pivot.infer_objects(copy=False)  # Remove FutureWarning about downcasting
    fig = px.imshow(pivot, labels=dict(x='O/T', y='Route', color='Nett'), title='Route vs O/T Sales Heatmap')
    return fig

def pie_chart(df: pd.DataFrame) -> px.pie:
    """Pie chart of sales share by O/T."""
    grouped = df.groupby('O/T')['Nett'].sum().reset_index()
    fig = px.pie(grouped, names='O/T', values='Nett', title='Sales Share by O/T')
    return fig

def map_view(df: pd.DataFrame, only_cached: bool = True, top_n: int = 100) -> Optional[folium.Map]:
    """Map sales by postcode area or post-town if possible, colour-scale by Nett sum. Handles geocoding errors and caches results. Only uses cached postcodes if only_cached=True. Limits to top_n postcodes."""
    from config import GEO_CACHE_FILE

    df = df.copy()
    if 'Address' not in df.columns or df['Address'].isnull().all():
        st.warning("No address data available for mapping.")
        return None
    df['Postcode'] = df['Address'].apply(extract_uk_postcode)
    postcodes = df['Postcode'].dropna().unique()
    cache_file = GEO_CACHE_FILE
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            postcode_map = pickle.load(f)
    else:
        postcode_map = {}
    updated = False
    geolocator = Nominatim(user_agent="sales_dashboard", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=2, error_wait_seconds=2)
    if not only_cached:
        for pc in postcodes:
            if pc not in postcode_map:
                try:
                    location = geocode(pc + ", UK")
                    if location:
                        postcode_map[pc] = (location.latitude, location.longitude)
                    else:
                        postcode_map[pc] = (None, None)
                except Exception as e:
                    postcode_map[pc] = (None, None)
                    logging.warning(f"Geocoding failed for postcode '{pc}': {e}")
                updated = True
        if updated:
            with open(cache_file, "wb") as f:
                pickle.dump(postcode_map, f)
    df['lat'] = df['Postcode'].map(lambda x: postcode_map.get(x, (None, None))[0])
    df['lon'] = df['Postcode'].map(lambda x: postcode_map.get(x, (None, None))[1])
    df = df[df['lat'].notna() & df['lon'].notna()]
    if df.empty:
        st.warning("No geocoded postcodes available for mapping.")
        return None
    agg = df.groupby(['Postcode', 'lat', 'lon']).agg({
        'Nett': 'sum',
        'Order': 'count',
        'Address': 'first',
        'Name': lambda x: ', '.join(sorted(set(x.dropna())))
    }).reset_index()
    agg['Nett'] = pd.to_numeric(agg['Nett'], errors='coerce')  # Ensure numeric dtype
    agg = agg.nlargest(top_n, 'Nett')
    m = folium.Map(location=[df['lat'].mean(), df['lon'].mean()], zoom_start=6)
    marker_cluster = MarkerCluster().add_to(m)
    for _, row in agg.iterrows():
        popup = f"Postcode: {row['Postcode']}<br>Nett: £{row['Nett']:,.2f}<br>Orders: {row['Order']}<br>Sample Address: {row['Address']}<br>Names: {row['Name']}"
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6 + max(2, min(row['Nett'] / 1000, 20)),
            color='blue',
            fill=True,
            fill_color='green',
            fill_opacity=0.6,
            popup=popup
        ).add_to(marker_cluster)
    return m

def forecast_chart(adv_metrics: dict) -> go.Figure:
    """Plotly forecast chart with confidence intervals from advanced metrics."""
    forecast = adv_metrics.get('forecast')
    lower = adv_metrics.get('forecast_lower')
    upper = adv_metrics.get('forecast_upper')
    if forecast is None or forecast.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=forecast.index, y=forecast.values, mode='lines', name='Forecast', line=dict(color='royalblue')
    ))
    fig.add_trace(go.Scatter(
        x=lower.index, y=lower.values, mode='lines', name='Lower CI', line=dict(width=0), showlegend=False
    ))
    fig.add_trace(go.Scatter(
        x=upper.index, y=upper.values, mode='lines', name='Upper CI', fill='tonexty', fillcolor='rgba(65,105,225,0.2)', line=dict(width=0), showlegend=False
    ))
    fig.update_layout(
        title='Nett Sales Forecast (Prophet)',
        xaxis_title='Date',
        yaxis_title='Nett',
        template='simple_white'
    )
    return fig