"""
app.py: Streamlit app entry point for sales dashboard.
"""
import streamlit as st
import logging
import locale
import time
import sqlite3
import bcrypt
from loader import load_data
from data_prep import prepare_data
from metrics import compute_kpis, compute_advanced_metrics
from charts import line_chart, bar_chart, heatmap_chart, pie_chart, map_view, forecast_chart
import config

DB_PATH = 'users.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT
        -- status column may be missing in old DBs
    )''')
    # Add status column if it doesn't exist
    try:
        c.execute('ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT "pending"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    # Add is_admin column if it doesn't exist
    try:
        c.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()

# Admin credentials are now stored in the database.
# To log in as admin, you need a user with is_admin=1, status='approved', and a set password.
# There is no default admin user unless you create one in the database.

# To create an admin user, you can manually insert into the database, e.g.:
# INSERT INTO users (username, password_hash, status, is_admin) VALUES ('admin', <hashed_password>, 'approved', 1)
# Or, you can add a function to create an admin user if not exists.

# Example helper (not in production code):
# def ensure_admin_user():
#     # This function is for development only. Do NOT use in production.
#     # In production, create an admin user manually using create_admin_user or direct DB insert.

def create_admin_user(username, password):
    """
    Create an admin user with the given username and password.
    If the user already exists, update their password and set as admin/approved.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    c.execute('SELECT username FROM users WHERE username = ?', (username,))
    if c.fetchone():
        # Update existing user to admin and approved
        c.execute('UPDATE users SET password_hash=?, status=?, is_admin=? WHERE username=?',
                  (password_hash, 'approved', 1, username))
    else:
        # Insert new admin user
        c.execute('INSERT INTO users (username, password_hash, status, is_admin) VALUES (?, ?, ?, ?)',
                  (username, password_hash, 'approved', 1))
    conn.commit()
    conn.close()

def register_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return False, 'Username already requested or exists.'
    # All new users are not admin by default, set password_hash to empty string for NOT NULL constraint
    c.execute('INSERT INTO users (username, password_hash, status, is_admin) VALUES (?, ?, ?, ?)', (username, '', 'pending', 0))
    conn.commit()
    conn.close()
    return True, 'Registration request submitted for admin approval.'

def set_user_password(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    c.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))
    conn.commit()
    conn.close()

def check_login_db(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT password_hash, status, is_admin FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    password_hash, status, is_admin = row
    # If approved and password not set, return special value
    if (status == 'approved' or is_admin == 1) and (not password_hash or password_hash == ''):
        return "set_password"
    # Normal login
    if (status == 'approved' or is_admin == 1) and password_hash and bcrypt.checkpw(password.encode(), password_hash):
        return True
    return False

def get_pending_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE status = "pending"')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_approved_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE status = "approved" AND is_admin = 0')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def delete_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()

def reset_user_password(username, new_password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    c.execute('UPDATE users SET password_hash = ? WHERE username = ?', (password_hash, username))
    conn.commit()
    conn.close()

def reset_admin_password(new_password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    c.execute('UPDATE users SET password_hash = ? WHERE is_admin = 1', (password_hash,))
    conn.commit()
    conn.close()

def approve_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET status = "approved" WHERE username = ?', (username,))
    conn.commit()
    conn.close()

def reject_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET status = "rejected" WHERE username = ?', (username,))
    conn.commit()
    conn.close()

def is_admin_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT is_admin FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

def login_or_register():
    st.sidebar.title("Login or Register")
    action = st.sidebar.radio("Select action", ("Login", "Register"))
    username = st.sidebar.text_input("Username")
    if action == "Register":
        if st.sidebar.button("Request Registration"):
            if username:
                success, msg = register_user(username)
                if success:
                    st.sidebar.success(msg)
                else:
                    st.sidebar.error(msg)
            else:
                st.sidebar.warning("Please enter username.")
        st.session_state["login_username"] = username
    else:
        password = st.sidebar.text_input("Password", type="password")
        set_pw = False
        if st.sidebar.button("Login"):
            login_result = check_login_db(username, password)
            if login_result == "set_password":
                st.session_state["set_password_user"] = username
                set_pw = True
            elif login_result is True:
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = username
                st.session_state["is_admin"] = is_admin_user(username)
                st.sidebar.success("Login successful!")
            else:
                st.sidebar.error("Invalid username, password, or not approved yet.")
        else:
            set_pw = "set_password_user" in st.session_state and st.session_state["set_password_user"] == username

        # Password setup flow
        if set_pw:
            st.sidebar.info("Set your password for the first time.")
            new_pw = st.sidebar.text_input("New Password", type="password", key="new_pw")
            confirm_pw = st.sidebar.text_input("Confirm Password", type="password", key="confirm_pw")
            if st.sidebar.button("Set Password"):
                if not new_pw or not confirm_pw:
                    st.sidebar.warning("Please enter and confirm your new password.")
                elif new_pw != confirm_pw:
                    st.sidebar.error("Passwords do not match.")
                else:
                    set_user_password(username, new_pw)
                    st.sidebar.success("Password set! Please log in.")
                    st.session_state.pop("set_password_user", None)
        st.session_state["login_username"] = username
    return st.session_state.get("authenticated", False)

def admin_panel():
    st.header("Admin Panel")
    st.write("Approve or reject pending user registrations below.")
    pending = get_pending_users()
    if not pending:
        st.info("No pending registrations.")
    for user in pending:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"Approve {user}"):
                approve_user(user)
                st.success(f"Approved {user}")
        with col2:
            if st.button(f"Reject {user}"):
                reject_user(user)
                st.warning(f"Rejected {user}")

    st.markdown("---")
    st.subheader("Approved Users")
    approved_users = get_approved_users()
    if not approved_users:
        st.info("No approved users.")
    else:
        for user in approved_users:
            col1, col2, col3 = st.columns([2,1,2])
            with col1:
                st.write(user)
            with col2:
                if st.button(f"Delete {user}"):
                    delete_user(user)
                    st.warning(f"Deleted {user}")
                    st.experimental_rerun()
            with col3:
                with st.expander(f"Reset password for {user}"):
                    new_pw = st.text_input(f"New password for {user}", type="password", key=f"reset_{user}")
                    if st.button(f"Set New Password for {user}"):
                        if not new_pw:
                            st.warning("Enter a new password.")
                        else:
                            reset_user_password(user, new_pw)
                            st.success(f"Password reset for {user}")

    st.markdown("---")
    st.subheader("Admin Password")
    with st.expander("Change admin password"):
        new_admin_pw = st.text_input("New admin password", type="password", key="reset_admin_pw")
        if st.button("Set New Admin Password"):
            if not new_admin_pw:
                st.warning("Enter a new admin password.")
            else:
                reset_admin_password(new_admin_pw)
                st.success("Admin password has been changed.")

st.set_page_config(page_title="Optimum Sales Dashboard", layout="wide")

# Set UK locale for currency and date formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_GB.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'English_United_Kingdom.1252')
    except locale.Error:
        pass  # Fallback: do not crash if locale is not available

def hide_sidebar():
    """
    Hides the Streamlit sidebar using custom CSS.
    """
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        </style>
        """,
        unsafe_allow_html=True,
    )

def main():
    init_db()
    # ensure_admin_user()  # This function is for development only. Do NOT use in production.
    # In production, create an admin user manually using create_admin_user or direct DB insert.
    if not login_or_register():
        st.warning("Please log in to access the dashboard.")
        st.stop()

    # Sidebar visibility toggle
    if 'sidebar_hidden' not in st.session_state:
        st.session_state['sidebar_hidden'] = True
    st.sidebar.checkbox("Hide sidebar after login", value=st.session_state['sidebar_hidden'], key='sidebar_hidden')

    # Top row: Log Out and Admin Panel (if admin) - move to very top after login
    show_admin_panel = False
    if st.session_state.get("authenticated", False):
        cols = st.columns([1, 1, 8])
        with cols[0]:
            if st.button("Log Out"):
                st.session_state.clear()
                st.stop()
        is_admin = st.session_state.get("is_admin", False)
        with cols[1]:
            if is_admin:
                if st.button("Admin Panel"):
                    st.session_state["show_admin_panel"] = not st.session_state.get("show_admin_panel", False)
        show_admin_panel = st.session_state.get("show_admin_panel", False)

    # Sidebar hide logic (now optional)
    if st.session_state.get("authenticated", False):
        if st.session_state.get("sidebar_hidden", True):
            st.markdown(
                """
                <style>
                [data-testid=\"stSidebar\"] {display: none;}
                </style>
                """,
                unsafe_allow_html=True,
            )

    # Show admin panel in full width if toggled
    if show_admin_panel:
        admin_panel()
        st.stop()

    # Hide the sidebar when logged in (optional)
    authenticated = st.session_state.get("authenticated", False)
    if authenticated and st.session_state.get("sidebar_hidden", True):
        hide_sidebar()

    st.title("📊 Optimum Sales Dashboard")
    st.write("Upload an Annapurna Report 19: Sales by Job data file (.xlsx, .xls, .csv) to get started.")

    # File upload and selection logic
    if 'uploaded_files' not in st.session_state:
        st.session_state['uploaded_files'] = {}
    uploaded_file = st.file_uploader("Choose a file", type=["xlsx", "xls", "csv"])
    if uploaded_file is not None:
        st.session_state['uploaded_files'][uploaded_file.name] = uploaded_file.getvalue()
        st.session_state['last_file_name'] = uploaded_file.name
    file_options = list(st.session_state['uploaded_files'].keys())
    selected_file = None
    if file_options:
        default_idx = file_options.index(st.session_state.get('last_file_name', file_options[0])) if 'last_file_name' in st.session_state else 0
        selected_name = st.selectbox("Select a previously uploaded file", options=file_options, index=default_idx)
        selected_file = st.session_state['uploaded_files'][selected_name]
        st.session_state['last_file_name'] = selected_name
    df = None
    if selected_file is not None:
        import os
        import time
        try:
            import pandas as pd
            import tempfile
            t0 = time.time()
            with st.spinner("Loading and preparing data, please wait..."):
                tmp_path = None
                info_msg = st.empty()
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=selected_name[-5:]) as tmp:
                        tmp.write(selected_file)
                        tmp_path = tmp.name
                    load_start = time.time()
                    raw_df = load_data(tmp_path)
                    load_time = time.time() - load_start
                    info_msg.info(f"File loaded in {load_time:.2f} seconds")
                    prep_start = time.time()
                    df = prepare_data(raw_df)
                    prep_time = time.time() - prep_start
                    info_msg.info(f"Data prepared in {prep_time:.2f} seconds")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
            info_msg.info(f"Loaded {len(df)} rows in {time.time() - t0:.2f} seconds.")

            # Date range, Name, and O/T filters side by side
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            with filter_col1:
                min_date = df['Entered'].min()
                max_date = df['Entered'].max()
                start_date, end_date = st.date_input(
                    "Select date range (DD/MM/YYYY)",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    format="DD/MM/YYYY"
                )
            with filter_col2:
                names = df['Name'].dropna().unique().tolist()
                selected_name = st.selectbox("Filter by Customer Name", options=["All"] + sorted(names), key="single_name")
            with filter_col3:
                ot_values = df['O/T'].dropna().unique().tolist()
                selected_ot = st.selectbox("Filter by O/T", options=["All"] + sorted(ot_values), key="ot_filter")

            # --- Apply filters in sequence to a fresh copy of df ---
            filtered_df = df.copy()
            filtered_df = filtered_df[(filtered_df['Entered'] >= pd.to_datetime(start_date)) & (filtered_df['Entered'] <= pd.to_datetime(end_date))]
            if selected_name != "All":
                filtered_df = filtered_df[filtered_df['Name'] == selected_name]
            if selected_ot != "All":
                filtered_df = filtered_df[filtered_df['O/T'] == selected_ot]

            # --- Chart and KPI caching ---
            chart_filters = {
                'start_date': str(start_date),
                'end_date': str(end_date),
                'selected_name': selected_name,
                'selected_ot': selected_ot,  # Add O/T filter to cache key
                'freq': st.session_state.get('freq', 'Monthly'),
                'forecast_days': st.session_state.get('forecast_days', 30)
            }

            # KPIs
            if (
                'last_kpi_filters' not in st.session_state or
                st.session_state['last_kpi_filters'] != chart_filters or
                'last_kpis' not in st.session_state
            ):
                with st.spinner("Calculating KPIs..."):
                    kpis = compute_kpis(filtered_df)
                st.session_state['last_kpi_filters'] = chart_filters.copy()
                st.session_state['last_kpis'] = kpis
            else:
                kpis = st.session_state['last_kpis']
            kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
            def gbp(val):
                try:
                    return locale.currency(val, symbol=True, grouping=True)
                except Exception:
                    return f"£{val:,.2f}"
            kpi1.metric("Total Nett Sales", gbp(kpis['Total Nett Sales']))
            kpi2.metric("Total Orders", kpis['Total Orders'])
            kpi3.metric("Total Units Sold", int(kpis['Total Units Sold']))
            kpi4.metric("Avg Order Value", gbp(kpis['Average Order Value']))
            kpi5.metric("Avg Margin %", f"{kpis['Average Margin %']:.1f}%")
            kpi6.metric("Avg Turnaround (days)", f"{kpis['Average Turnaround']:.2f}")

            # Visualizations
            st.subheader("Sales Trends & Breakdown")
            freq = st.radio("Time Granularity", options=["Daily", "Weekly", "Monthly"], horizontal=True, key="freq")
            freq_map = {"Daily": 'D', "Weekly": 'W', "Monthly": 'M'}
            # Line chart cache
            line_chart_key = f"line_chart_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{chart_filters['selected_ot']}_{freq}"
            if (
                'last_line_chart_key' not in st.session_state or
                st.session_state['last_line_chart_key'] != line_chart_key or
                'last_line_chart' not in st.session_state
            ):
                t0 = time.time()
                with st.spinner("Loading sales trend chart..."):
                    line_fig = line_chart(filtered_df, ma_col=7, freq=freq_map[freq])
                st.session_state['last_line_chart_key'] = line_chart_key
                st.session_state['last_line_chart'] = line_fig
                chart_msg = f"Sales trend chart calculated in {time.time() - t0:.2f} seconds"
            else:
                line_fig = st.session_state['last_line_chart']
                chart_msg = "Sales trend chart loaded from cache."
            st.plotly_chart(line_fig, use_container_width=True)
            st.caption(chart_msg)

            # Prophet forecast with confidence intervals (now under Nett Sales Over Time)
            t0 = time.time()
            st.subheader("Nett Sales Forecast")
            st.markdown("""
            <small>
            <b>How is this forecast calculated?</b><br>
            The forecast uses the Prophet model to predict daily Nett sales and unique order counts for the selected future period. Prophet is trained on your historical sales data, capturing trends and seasonality. The chart shows the predicted sales (blue line) and a confidence interval (shaded area). Forecasted KPIs below the chart are based on these predictions.
            </small>
            """, unsafe_allow_html=True)
            forecast_days = st.number_input("Forecast how many days into the future?", min_value=7, max_value=180, value=30, step=1, key="forecast_days")
            run_forecast = st.button("Run Forecast")
            adv = None
            forecast_key = f"forecast_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{forecast_days}"
            if run_forecast or ('last_forecast_key' in st.session_state and st.session_state['last_forecast_key'] == forecast_key and 'last_forecast_adv' in st.session_state):
                with st.spinner("Running Prophet forecast, please wait..."):
                    if run_forecast or 'last_forecast_adv' not in st.session_state or st.session_state['last_forecast_key'] != forecast_key:
                        adv = compute_advanced_metrics(filtered_df, forecast_days=forecast_days)
                        st.session_state['last_forecast_key'] = forecast_key
                        st.session_state['last_forecast_adv'] = adv
                    else:
                        adv = st.session_state['last_forecast_adv']
                st.plotly_chart(forecast_chart(adv), use_container_width=True)
                st.write(f"Forecast chart and KPIs calculated in {time.time() - t0:.2f} seconds")
                # After the forecast chart, show forecasted KPIs for the future date range
                if adv.get('forecast') is not None and not adv['forecast'].empty and adv.get('forecast_orders') is not None and not adv['forecast_orders'].empty:
                    last_actual = filtered_df['Entered'].max()
                    forecast_future = adv['forecast'][adv['forecast'].index > last_actual]
                    forecast_lower = adv['forecast_lower'][adv['forecast_lower'].index > last_actual]
                    forecast_upper = adv['forecast_upper'][adv['forecast_upper'].index > last_actual]
                    forecast_orders_future = adv['forecast_orders'][adv['forecast_orders'].index > last_actual]
                    total_nett = forecast_future.sum()
                    total_orders = int(round(forecast_orders_future.sum()))
                    avg_order_value = total_nett / total_orders if total_orders else 0
                    avg_margin = filtered_df['Margin_%'].mean() if not filtered_df.empty else 0
                    kpi1f, kpi2f, kpi3f, kpi4f = st.columns(4)
                    kpi1f.metric("Forecasted Nett Sales", gbp(total_nett))
                    kpi2f.metric("Forecasted Orders", total_orders)
                    kpi3f.metric("Forecasted Avg Order Value", gbp(avg_order_value))
                    kpi4f.metric("Forecasted Avg Margin %", f"{avg_margin:.1f}%")
                    st.markdown(f"**Forecasted Nett Range:** {gbp(forecast_lower.sum())} - {gbp(forecast_upper.sum())}")

            # Bar charts cache
            bar_desc_key = f"bar_desc_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{chart_filters['selected_ot']}"
            bar_name_key = f"bar_name_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{chart_filters['selected_ot']}"
            col1, col2 = st.columns(2)
            with col1:
                if ('last_bar_desc_key' not in st.session_state or st.session_state['last_bar_desc_key'] != bar_desc_key or 'last_bar_desc_chart' not in st.session_state):
                    t0 = time.time()
                    with st.spinner("Loading top descriptions chart..."):
                        bar_desc_fig = bar_chart(filtered_df, by='Description', value='Nett', top_n=10)
                    st.session_state['last_bar_desc_key'] = bar_desc_key
                    st.session_state['last_bar_desc_chart'] = bar_desc_fig
                    bar_desc_msg = f"Top descriptions chart generated in {time.time() - t0:.2f} seconds."
                else:
                    bar_desc_fig = st.session_state['last_bar_desc_chart']
                    bar_desc_msg = "Top descriptions chart loaded from cache."
                st.plotly_chart(bar_desc_fig, use_container_width=True)
                st.caption(bar_desc_msg)
            with col2:
                if ('last_bar_name_key' not in st.session_state or st.session_state['last_bar_name_key'] != bar_name_key or 'last_bar_name_chart' not in st.session_state):
                    t0 = time.time()
                    with st.spinner("Loading top customers chart..."):
                        bar_name_fig = bar_chart(filtered_df, by='Name', value='Nett', top_n=10)
                    st.session_state['last_bar_name_key'] = bar_name_key
                    st.session_state['last_bar_name_chart'] = bar_name_fig
                    bar_name_msg = f"Top customers chart generated in {time.time() - t0:.2f} seconds."
                else:
                    bar_name_fig = st.session_state['last_bar_name_chart']
                    bar_name_msg = "Top customers chart loaded from cache."
                st.plotly_chart(bar_name_fig, use_container_width=True)
                st.caption(bar_name_msg)

            # Heatmap and Pie chart cache
            heatmap_key = f"heatmap_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{chart_filters['selected_ot']}"
            pie_key = f"pie_{chart_filters['start_date']}_{chart_filters['end_date']}_{chart_filters['selected_name']}_{chart_filters['selected_ot']}"
            col3, col4 = st.columns(2)
            with col3:
                if ('last_heatmap_key' not in st.session_state or st.session_state['last_heatmap_key'] != heatmap_key or 'last_heatmap_chart' not in st.session_state):
                    t0 = time.time()
                    with st.spinner("Loading heatmap..."):
                        heatmap_fig = heatmap_chart(filtered_df)
                    st.session_state['last_heatmap_key'] = heatmap_key
                    st.session_state['last_heatmap_chart'] = heatmap_fig
                    heatmap_msg = f"Heatmap generated in {time.time() - t0:.2f} seconds."
                else:
                    heatmap_fig = st.session_state['last_heatmap_chart']
                    heatmap_msg = "Heatmap loaded from cache."
                st.plotly_chart(heatmap_fig, use_container_width=True)
                st.caption(heatmap_msg)
            with col4:
                if ('last_pie_key' not in st.session_state or st.session_state['last_pie_key'] != pie_key or 'last_pie_chart' not in st.session_state):
                    t0 = time.time()
                    with st.spinner("Loading pie chart..."):
                        pie_fig = pie_chart(filtered_df)
                    st.session_state['last_pie_key'] = pie_key
                    st.session_state['last_pie_chart'] = pie_fig
                    pie_msg = f"Pie chart generated in {time.time() - t0:.2f} seconds."
                else:
                    pie_fig = st.session_state['last_pie_chart']
                    pie_msg = "Pie chart loaded from cache."
                st.plotly_chart(pie_fig, use_container_width=True)
                st.caption(pie_msg)

            # Map Visualisation Controls
            st.subheader("Map: UK Sales by Address/Postcode Area")
            from streamlit_folium import st_folium
            col_map1, col_map2, col_map3 = st.columns([1,1,2])
            with col_map1:
                only_cached = st.checkbox("Only use cached postcodes (fast)", value=True, key="only_cached")
            with col_map2:
                top_n = st.number_input("Max postcodes to show", min_value=10, max_value=1000, value=1000, step=10, key="top_n")
            with col_map3:
                show_map = st.toggle("Show Map", value=st.session_state.get('show_map', False), key="show_map_toggle")
            st.session_state['show_map'] = show_map
            # Reset map if file changes
            if uploaded_file is not None and (st.session_state.get('last_file') != uploaded_file.name):
                st.session_state['show_map'] = False
                st.session_state['last_file'] = uploaded_file.name
                st.session_state.pop('last_map_filters', None)
                st.session_state.pop('last_map', None)
                st.session_state.pop('last_map_details', None)
            # Map caching logic
            map_filters = {
                'name_filter': selected_name,
                'date_range': (str(start_date), str(end_date)),
                'only_cached': only_cached,
                'top_n': top_n
            }
            if st.session_state['show_map']:
                # Always regenerate the map for full interactivity
                t0 = time.time()
                with st.spinner("Generating map, this may take a moment..."):
                    folium_map = map_view(filtered_df, only_cached=only_cached, top_n=top_n)
                    # Calculate sales details for the map
                    map_df = filtered_df.copy()
                    if 'Postcode' not in map_df.columns:
                        from charts import extract_uk_postcode
                        map_df['Postcode'] = map_df['Address'].apply(extract_uk_postcode)
                    map_df = map_df[map_df['Postcode'].notna()]
                    map_df = map_df.groupby('Postcode').agg({'Nett': 'sum', 'Order': 'count'}).reset_index()
                    total_nett = map_df['Nett'].sum()
                    total_orders = map_df['Order'].sum()
                    postcode_count = map_df['Postcode'].nunique()
                    map_details = {
                        'total_nett': total_nett,
                        'total_orders': total_orders,
                        'postcode_count': postcode_count
                    }
                    st.session_state['last_map_details'] = map_details
                st.write(f"Map generated in {time.time() - t0:.2f} seconds")
                if folium_map:
                    st_folium(folium_map, width=None, height=600)
                    if map_details:
                        st.info(f"Total Nett: £{map_details['total_nett']:,.2f} | Total Orders: {map_details['total_orders']} | Postcodes Shown: {map_details['postcode_count']}")
                    else:
                        st.warning("No map details available. Try toggling the map off and on again or changing a filter.")

            # --- Time Comparison: Year-over-Year (YoY) Comparison Chart ---
            with st.expander("Year-over-Year Comparison", expanded=False):
                if st.button("Show YoY Chart"):
                    t0 = time.time()
                    if filtered_df['Entered'].dt.year.nunique() > 1:
                        yoy = filtered_df.copy()
                        yoy['Year'] = yoy['Entered'].dt.year
                        yoy['Month'] = yoy['Entered'].dt.month
                        yoy_grouped = yoy.groupby(['Year', 'Month'])['Nett'].sum().reset_index()
                        yoy_pivot = yoy_grouped.pivot(index='Month', columns='Year', values='Nett').sort_index()
                        st.line_chart(yoy_pivot, use_container_width=True)
                    else:
                        st.info("Not enough years of data for YoY comparison.")
                    st.write(f"YoY chart calculated in {time.time() - t0:.2f} seconds")

            # --- Cumulative Sales Chart ---
            with st.expander("Cumulative Nett Sales", expanded=False):
                if st.button("Show Cumulative Chart"):
                    t0 = time.time()
                    cum_df = filtered_df.sort_values('Entered')
                    cum_df['Cumulative Nett'] = cum_df['Nett'].cumsum()
                    st.line_chart(cum_df.set_index('Entered')['Cumulative Nett'], use_container_width=True)
                    st.write(f"Cumulative chart calculated in {time.time() - t0:.2f} seconds")

            # --- Sales Funnel Visualization ---
            with st.expander("Sales Funnel Visualization", expanded=False):
                if st.button("Show Funnel Chart"):
                    t0 = time.time()
                    funnel_df = filtered_df.copy()
                    funnel_df['Ordered'] = ~funnel_df['Order'].isna()
                    funnel_df['SentFlag'] = ~funnel_df['Sent'].isna()
                    funnel_counts = [
                        funnel_df['Ordered'].sum(),
                        funnel_df['SentFlag'].sum()
                    ]
                    funnel_labels = ['Orders Entered', 'Orders Sent']
                    import plotly.graph_objects as go
                    funnel_trace = go.Funnel(
                        y=funnel_labels,
                        x=funnel_counts,
                        textinfo="value+percent initial"
                    )
                    funnel_fig = go.Figure(funnel_trace)
                    funnel_fig.update_layout(title="Order to Sent Funnel")
                    st.plotly_chart(funnel_fig, use_container_width=True)
                    st.write(f"Funnel chart calculated in {time.time() - t0:.2f} seconds")

            # --- Customer Segmentation ---
            with st.expander("Customer Segmentation", expanded=False):
                if st.button("Show Segmentation Chart"):
                    t0 = time.time()
                    seg_df = filtered_df.groupby('Name').agg({
                        'Nett': 'sum',
                        'Order': pd.Series.nunique
                    }).rename(columns={'Order': 'Order Count'}).reset_index()
                    seg_df['Segment'] = pd.qcut(seg_df['Nett'], 4, labels=['Low', 'Mid-Low', 'Mid-High', 'High'])
                    import plotly.express as px
                    seg_fig = px.scatter(seg_df, x='Order Count', y='Nett', color='Segment', hover_name='Name',
                                         title='Customer Segmentation by Sales Volume and Frequency')
                    st.plotly_chart(seg_fig, use_container_width=True)
                    st.write(f"Customer segmentation calculated in {time.time() - t0:.2f} seconds")

            # --- Churn Prediction ---
            with st.expander("Churn Prediction", expanded=False):
                if st.button("Show Churn Table"):
                    t0 = time.time()
                    last_date = filtered_df['Entered'].max()
                    churn_df = filtered_df.groupby('Name')['Entered'].max().reset_index()
                    churn_df['Days Since Last Order'] = (last_date - churn_df['Entered']).dt.days
                    churned = churn_df[churn_df['Days Since Last Order'] > 90]
                    st.write(f"Customers at risk of churn (>90 days since last order): {len(churned)}")
                    st.dataframe(churned[['Name', 'Days Since Last Order']])
                    st.write(f"Churn prediction calculated in {time.time() - t0:.2f} seconds")

            # --- Product/Description Analysis ---
            with st.expander("Product/Description Analysis", expanded=False):
                if st.button("Show Product Analysis"):
                    t0 = time.time()
                    prod_df = filtered_df.groupby('Description').agg({'Nett': 'sum', 'Order': pd.Series.nunique}).reset_index()
                    prod_df['Nett'] = pd.to_numeric(prod_df['Nett'], errors='coerce')  # Ensure numeric dtype
                    top_products = prod_df.nlargest(10, 'Nett')
                    bottom_products = prod_df.nsmallest(10, 'Nett')
                    st.write("Top 10 Products by Nett Sales:")
                    st.dataframe(top_products)
                    st.write("Bottom 10 Products by Nett Sales:")
                    st.dataframe(bottom_products)
                    # Only show trends for top 5 products in the chart
                    prod_trend = filtered_df[filtered_df['Description'].isin(top_products['Description'].head(5))]
                    prod_trend = prod_trend.groupby(['Entered', 'Description'])['Nett'].sum().reset_index()
                    import plotly.express as px
                    prod_trend_fig = px.line(
                        prod_trend,
                        x='Entered',
                        y='Nett',
                        color='Description',
                        title='Product Sales Trends (Top 5)',
                        category_orders={'Description': top_products['Description'].head(5).tolist()}
                    )
                    st.plotly_chart(prod_trend_fig, use_container_width=True)
                    st.write(f"Product/description analysis calculated in {time.time() - t0:.2f} seconds")

            # --- Margin Analysis ---
            with st.expander("Margin Analysis", expanded=False):
                if st.button("Show Margin Analysis"):
                    t0 = time.time()
                    margin_threshold = st.slider("Highlight orders with margin below (%)", min_value=0, max_value=100, value=20)
                    low_margin_df = filtered_df[filtered_df['Margin_%'] < margin_threshold]
                    st.write(f"Orders with margin below {margin_threshold}%: {len(low_margin_df)}")
                    st.dataframe(low_margin_df[['Order', 'Name', 'Nett', 'Margin_%']])
                    import plotly.express as px
                    margin_fig = px.histogram(filtered_df, x='Margin_%', nbins=30, title='Margin % Distribution')
                    st.plotly_chart(margin_fig, use_container_width=True)
                    st.write(f"Margin analysis calculated in {time.time() - t0:.2f} seconds")

            # --- Advanced metrics (moved to bottom) ---
            with st.expander("Advanced Metrics", expanded=False):
                if st.button("Show Advanced Metrics"):
                    t0 = time.time()
                    adv = compute_advanced_metrics(filtered_df, forecast_days=forecast_days)
                    st.write(f"Advanced metrics calculated in {time.time() - t0:.2f} seconds")
                    st.write("**Inactive customers (no orders in 30 days):**", adv['inactive_customers'])
                    st.write("**Days with Nett >2 SD below mean:**", [d.strftime('%Y-%m-%d') for d in adv['low_days']])
                    st.line_chart(adv['7d_ma'], use_container_width=True)
                
        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.text(traceback.format_exc())
    else:
        st.info("Awaiting file upload...")

if __name__ == "__main__":
    main()
