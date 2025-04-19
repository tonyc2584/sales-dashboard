"""
data_prep.py: Data cleaning and feature engineering for sales dashboard.
"""
import pandas as pd
import logging
import streamlit as st
import time
import numpy as np
from config import NUMERIC_COLS, CATEGORICAL_COLS

@st.cache_data(show_spinner=False)
def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, transform, and add features to the sales data. Do not deduplicate by Order. Include all rows regardless of Nett value."""
    t0 = time.time()
    # Parse Entered and Sent as datetime (UK format: dayfirst)
    date_formats = ["%d/%m/%Y", "%d/%m/%Y %H:%M:%S"]
    for col in ['Entered', 'Sent']:
        parsed = None
        for fmt in date_formats:
            try:
                parsed = pd.to_datetime(df[col], format=fmt, errors='raise')
                df[col] = parsed
                break
            except Exception:
                continue
        if parsed is None:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
    # Convert numeric columns to float
    for col in NUMERIC_COLS:
        df.loc[:, col] = pd.to_numeric(df[col], errors='coerce')
    # Convert categorical columns to category
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df.loc[:, col] = df[col].astype('category')
    # Add Gross_Margin and Margin_%
    df.loc[:, 'Gross_Margin'] = df['Nett'] - df['Cost']
    # Avoid division by zero for Margin_% using masking
    df['Margin_%'] = np.nan
    mask = df['Nett'] != 0
    df.loc[mask, 'Margin_%'] = np.round(df.loc[mask, 'Gross_Margin'] / df.loc[mask, 'Nett'] * 100, 1)
    prep_time = time.time() - t0
    logging.info(f"Data preparation completed in {prep_time:.2f} seconds")
    return df