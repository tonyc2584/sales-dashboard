"""
loader.py: Handles file selection and loading for sales dashboard.
"""
import os
import pandas as pd
import logging
import streamlit as st
import time
from config import DATA_PATH

REQUIRED_COLUMNS = [
    'Order', 'Account', 'Name', 'Address', 'Description', 'Type', 'Entered', 'Sent',
    'Qty', 'List', 'Nett', 'Cost', 'Route', 'Reference', "P'list", 'FOC', 'O/T', 'Promo'
]

@st.cache_data(show_spinner=False)
def load_data(file_path):
    """Load Excel or CSV file and validate columns. Returns DataFrame or raises Exception."""
    t0 = time.time()
    ext = os.path.splitext(file_path)[1].lower()
    usecols = [
        'Order', 'Account', 'Name', 'Address', 'Description', 'Type', 'Entered', 'Sent',
        'Qty', 'List', 'Nett', 'Cost', 'Route', 'Reference', "P'list", 'FOC', 'O/T', 'Promo'
    ]
    try:
        if ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, sheet_name=0, usecols=usecols, dtype=str)
        elif ext == '.csv':
            try:
                df = pd.read_csv(file_path, encoding='utf-8', usecols=usecols, dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='cp1252', usecols=usecols, dtype=str)
        else:
            raise ValueError('Unsupported file type. Please upload .xlsx, .xls, or .csv')
    except Exception as e:
        logging.error(f"Error loading file: {e}")
        raise
    load_time = time.time() - t0
    print(f"File loaded in {load_time:.2f} seconds")
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        msg = f"Missing required columns: {', '.join(missing)}"
        logging.error(msg)
        raise ValueError(msg)
    # Remove dtype conversions here; handled in data_prep.py
    return df