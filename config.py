# Configuration for Sales Dashboard
DATA_PATH = ''  # Default data file path
ALERT_THRESHOLD = 0.8  # 80% threshold for alerts
FORECAST_DAYS = 30
DATE_FORMAT = '%Y-%m-%d'
LOG_FILE = 'dashboard.log'
GEO_CACHE_FILE = 'geocode_cache_postcode.pkl'  # Path for geocode cache file
# Centralized column names for maintainability
REQUIRED_COLUMNS = [
    'Order', 'Account', 'Name', 'Address', 'Description', 'Type', 'Entered', 'Sent',
    'Qty', 'List', 'Nett', 'Cost', 'Route', 'Reference', "P'list", 'FOC', 'O/T', 'Promo'
]
NUMERIC_COLS = ['Qty', 'List', 'Nett', 'Cost']
CATEGORICAL_COLS = ['Order', 'Account', 'Name', 'Address', 'Description', 'Type', 'Route', 'Reference', "P'list", 'FOC', 'O/T', 'Promo']
