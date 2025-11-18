# === customer_revenue_churn_dashboard/app.py ===
# Streamlit app: Customer Revenue & Churn Intelligence Dashboard
# Files included in this single code document (split below):
#  - app.py                (this file, Streamlit UI + main)
#  - auth.py               (authentication helpers using MongoDB + bcrypt)
#  - data_utils.py         (data loading / cleaning / feature engineering)
#  - requirements.txt      (packages required)
#
# Place the uploaded CSV at: /mnt/data/7982c6fa-dd11-4c21-8843-813b9667a239-project1-retail-raw-dataset.csv
# Configure Streamlit secrets (recommended) with:
# [mongo]
# uri = "<your_mongodb_uri>"
# db = "customer_dashboard"
#
# If you do not set MongoDB secrets, the app will fall back to a small local JSON store for users.

# ------------------------- app.py -------------------------
import streamlit as st
from auth import AuthManager
from data_utils import DataManager
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import altair as alt
from datetime import datetime

st.set_page_config(layout="wide", page_title="Customer Revenue & Churn Intelligence")

# --- constants ---
CSV_PATH = "/mnt/data/7982c6fa-dd11-4c21-8843-813b9667a239-project1-retail-raw-dataset.csv"

# --- init managers ---
auth = AuthManager()
data_mgr = DataManager(csv_path=CSV_PATH)

# --- Login page ---
st.sidebar.title("Login")
mode = st.sidebar.radio("Entry as", ("User", "Admin"))
username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login"):
    user = auth.authenticate(username=username, password=password)
    if not user:
        st.sidebar.error("Invalid credentials")
    else:
        st.session_state['user'] = user
        st.sidebar.success(f"Logged in as {user['username']}")

# Admin create users
if 'user' in st.session_state and st.session_state['user'].get('role') == 'admin':
    st.sidebar.markdown("---")
    st.sidebar.subheader("Admin: Create new user")
    new_username = st.sidebar.text_input("New username")
    new_password = st.sidebar.text_input("New password", type="password")
    new_role = st.sidebar.selectbox("Role", ["user","admin"]) 
    if st.sidebar.button("Create user"):
        try:
            auth.create_user(new_username, new_password, new_role)
            st.sidebar.success("User created")
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")

# Require login
if 'user' not in st.session_state:
    st.title("Please login to access the dashboard")
    st.write("Use admin account to create users via the sidebar after logging in.")
    st.stop()

user = st.session_state['user']

# Load & preprocess data (done once and cached)
with st.spinner("Loading and preparing dataset..."):
    df = data_mgr.load_and_prepare()

# Top bar: Overview KPIs
st.header("Customer Revenue & Churn Intelligence Dashboard")
col1, col2, col3, col4 = st.columns(4)

# KPI calculations
total_revenue = df['revenue'].sum()
active_customers = df[df['status'] == 'active']['customer_id'].nunique()
churned_customers = df[df['status'] == 'churned']['customer_id'].nunique()
churn_rate = (churned_customers / (active_customers + churned_customers)) if (active_customers + churned_customers) > 0 else 0
avg_order_value = df['revenue'].sum() / df['order_id'].nunique() if df['order_id'].nunique()>0 else 0

col1.metric("Total Revenue", f"₹{total_revenue:,.0f}")
col2.metric("Churn Rate", f"{churn_rate*100:.2f}%")
col3.metric("Active Customers", f"{active_customers}")
col4.metric("Avg Order Value", f"₹{avg_order_value:,.0f}")

# Filters
st.sidebar.markdown("## Filters")
city_filter = st.sidebar.multiselect("City", options=sorted(df['city'].dropna().unique()), default=sorted(df['city'].dropna().unique()))
segment_filter = st.sidebar.multiselect("Segment", options=sorted(df['segment'].dropna().unique()), default=sorted(df['segment'].dropna().unique()))
date_range = st.sidebar.date_input("Date range", value=(df['order_date'].min(), df['order_date'].max()))

# apply filters
df_filtered = df[(df['city'].isin(city_filter)) & (df['segment'].isin(segment_filter)) & (df['order_date'] >= pd.to_datetime(date_range[0])) & (df['order_date'] <= pd.to_datetime(date_range[1]))]

# Revenue trend & churn trend
st.subheader("Revenue & Churn Trends")
rev_trend = df_filtered.groupby('order_month').agg({'revenue':'sum'}).reset_index()
churn_trend = df_filtered.groupby('order_month').agg({'churn_flag':'sum'}).reset_index()

chart1, chart2 = st.columns(2)
with chart1:
    st.markdown("**Revenue Trend (monthly)**")
    rev_chart = alt.Chart(rev_trend).mark_line(point=True).encode(x='order_month:T', y='revenue:Q')
    st.altair_chart(rev_chart, use_container_width=True)
with chart2:
    st.markdown("**Churn Trend (monthly churn count)**")
    churn_chart = alt.Chart(churn_trend).mark_line(point=True).encode(x='order_month:T', y='churn_flag:Q')
    st.altair_chart(churn_chart, use_container_width=True)

# Customers explorer
st.subheader("Customers Explorer")
search_term = st.text_input("Search customer by name or email")
if search_term:
    results = data_mgr.search_customers(df_filtered, search_term)
    st.write(results)

# Customer profile view
st.markdown("---")
selected_customer = st.selectbox("Select customer to view profile", options=sorted(df_filtered['customer_name'].dropna().unique()))
if selected_customer:
    profile = data_mgr.customer_profile(df_filtered, selected_customer)
    st.write(profile['summary'])
    st.dataframe(profile['transactions'])
    # small visualization: spend over time
    chart = alt.Chart(profile['transactions']).mark_bar().encode(x='order_date:T', y='revenue:Q')
    st.altair_chart(chart, use_container_width=True)

# Churn & Risk analysis
st.subheader("Churn & Risk Analysis")
by_segment = df_filtered.groupby('segment').agg({'revenue':'sum','churn_flag':'sum','customer_id':'nunique'}).reset_index()
st.dataframe(by_segment)

st.markdown("**Visualizations of churn by segment / city**")
seg_chart = alt.Chart(df_filtered).mark_bar().encode(x='segment:N', y='churn_flag:Q', color='city:N')
st.altair_chart(seg_chart, use_container_width=True)

# Support issue insights (placeholder based on dataset fields)
st.subheader("Support / Issue Insights")
if 'ticket_count' in df_filtered.columns:
    tickets = df_filtered.groupby('customer_id').agg({'ticket_count':'sum'}).reset_index().sort_values('ticket_count', ascending=False).head(10)
    st.write(tickets)
else:
    st.write("No ticket data in dataset; show top customers by refunds / complaints if present")

st.markdown("---")
st.caption(f"Logged in as: {user['username']} ({user.get('role')})")

# ------------------------- auth.py -------------------------
# (supporting module) - includes a simple auth manager using MongoDB & bcrypt

# Below we include code for auth.py and data_utils.py. When you copy files into your project,
# split the sections into separate files: auth.py, data_utils.py, and app.py.

# === auth.py ===
import streamlit as _st
from pymongo import MongoClient
import bcrypt
import json
import os

class AuthManager:
    def __init__(self):
        # read mongo config from st.secrets if available
        try:
            mongo_conf = _st.secrets['mongo']
            self.client = MongoClient(mongo_conf['uri'])
            self.db = self.client.get_database(mongo_conf.get('db', 'customer_dashboard'))
            self.users = self.db['users']
            # ensure an admin exists
            if self.users.count_documents({}) == 0:
                # create a default admin: admin / admin123 (please change)
                self.create_user('admin','admin123','admin')
        except Exception as e:
            # fallback to local json file
            self.users = None
            self.local_store = os.path.join(os.getcwd(), 'local_users.json')
            if not os.path.exists(self.local_store):
                with open(self.local_store, 'w') as f:
                    json.dump([], f)

    def _read_local(self):
        with open(self.local_store, 'r') as f:
            return json.load(f)
    def _write_local(self, data):
        with open(self.local_store, 'w') as f:
            json.dump(data, f, indent=2)

    def create_user(self, username, password, role='user'):
        if not username or not password:
            raise ValueError('username and password required')
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_doc = {'username': username, 'password': pw_hash, 'role': role}
        if self.users is not None:
            if self.users.count_documents({'username':username})>0:
                raise ValueError('user exists')
            self.users.insert_one(user_doc)
        else:
            data = self._read_local()
            if any(u['username']==username for u in data):
                raise ValueError('user exists')
            data.append(user_doc)
            self._write_local(data)

    def authenticate(self, username, password):
        if self.users is not None:
            doc = self.users.find_one({'username':username})
            if not doc:
                return None
            if bcrypt.checkpw(password.encode('utf-8'), doc['password'].encode('utf-8')):
                return {'username':doc['username'],'role':doc.get('role','user')}
            return None
        else:
            data = self._read_local()
            doc = next((u for u in data if u['username']==username), None)
            if not doc: return None
            if bcrypt.checkpw(password.encode('utf-8'), doc['password'].encode('utf-8')):
                return {'username':doc['username'],'role':doc.get('role','user')}
            return None

# ------------------------- data_utils.py -------------------------
# Data loading, cleaning, segmentation, and helper functions

# === data_utils.py ===
import pandas as pd
import numpy as np
from datetime import datetime

class DataManager:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def load_raw(self):
        df = pd.read_csv(self.csv_path)
        return df

    def load_and_prepare(self):
        df = self.load_raw()
        # Basic cleaning and normalization (adapt to your CSV's columns)
        # Try to be robust in case column names vary; map common names
        col_map = {}
        # common possible columns used in app
        # order id, customer id, customer name, email, order date, revenue, city, segment, status, tickets
        possible = {
            'order_id':['order_id','orderid','invoice_id'],
            'customer_id':['customer_id','cust_id','customerid'],
            'customer_name':['customer_name','name','customer'],
            'email':['email','cust_email'],
            'order_date':['order_date','date','purchase_date'],
            'revenue':['amount','revenue','spent','price','total'],
            'city':['city','location'],
            'segment':['segment','cust_segment'],
            'status':['status','cust_status'],
            'ticket_count':['ticket_count','tickets']
        }
        for canonical, options in possible.items():
            for o in options:
                if o in df.columns:
                    col_map[o] = canonical
        df = df.rename(columns=col_map)

        # fill missing expected columns
        for c in ['order_id','customer_id','customer_name','order_date','revenue','city','segment','status']:
            if c not in df.columns:
                df[c] = np.nan

        # convert date
        try:
            df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
        except Exception:
            df['order_date'] = pd.NaT

        # revenue numeric
        df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)

        # simple churn flag logic: if status column exists and equals 'churned' or 'inactive'
        df['status'] = df['status'].fillna('active')
        df['churn_flag'] = df['status'].apply(lambda x: 1 if str(x).lower() in ('churned','inactive','lost') else 0)

        # create order_month for trends
        df['order_month'] = df['order_date'].dt.to_period('M').dt.to_timestamp()

        # fill customer_name
        df['customer_name'] = df['customer_name'].fillna('Unknown')

        # ensure ids are strings
        df['customer_id'] = df['customer_id'].astype(str)
        df['order_id'] = df['order_id'].astype(str)

        # default segment and city
        df['segment'] = df['segment'].fillna('Unknown')
        df['city'] = df['city'].fillna('Unknown')

        return df

    def search_customers(self, df, term):
        term = str(term).lower()
        out = df[df['customer_name'].str.lower().str.contains(term) | df.get('email',pd.Series()).astype(str).str.lower().str.contains(term)]
        if out.empty:
            return pd.DataFrame()
        return out[['customer_id','customer_name','email','city','segment']].drop_duplicates().reset_index(drop=True)

    def customer_profile(self, df, customer_name):
        cust_df = df[df['customer_name']==customer_name].sort_values('order_date')
        summary = {
            'customer_name': customer_name,
            'total_spent': cust_df['revenue'].sum(),
            'orders': cust_df['order_id'].nunique(),
            'last_active': cust_df['order_date'].max()
        }
        return {'summary': summary, 'transactions': cust_df[['order_date','order_id','revenue','city','segment']].reset_index(drop=True)}

# ------------------------- requirements.txt -------------------------
# streamlit
# pymongo
# bcrypt
# pandas
# numpy
# matplotlib
# altair

# ------------------------- End of code bundle -------------------------

# Notes:
# 1) Copy the parts into three files: app.py, auth.py, data_utils.py. Install packages from requirements.txt.
# 2) Configure Streamlit secrets to include your MongoDB URI (recommended) or let the app use a local JSON fallback.
# 3) The code assumes a flexible CSV; column-mapping tries to detect common column names. If your CSV has different names, adjust data_utils.col_map.
# 4) The admin default account is created automatically when using MongoDB. Default admin credentials are `admin` / `admin123` - please change.
# 5) This is a starting implementation that fulfills the requested features: login/admin user creation (via MongoDB), reads attached CSV, data cleaning, visualizations, filters, customer explorer, churn analysis, and support insights placeholder.

# To run locally:
#   pip install -r requirements.txt
#   streamlit run app.py

# If you'd like, I can split this into separate files in the canvas, or create a deployable repo structure.
