import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
import json
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

SAVED_ROUTES_GID = "1477617688" 

MAX_DEADHEAD_MILES = 60
HOURLY_FLOOR_RATE = 25.00
REVIEW_PER_STOP_LIMIT = 23.00 

TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_RED = "#ef4444"
TB_BLUE = "#3b82f6"
TB_LIGHT_BLUE = "#e6f0fa"

POD_CONFIGS = {
    "Blue Pod": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}, "color": "blue"},
    "Green Pod": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}, "color": "green"},
    "Orange Pod": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}, "color": "orange"},
    "Purple Pod": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}, "color": "purple"},
    "Red Pod": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}, "color": "red"}
}

STATE_MAP = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC"
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Network Command Center", layout="wide")

# --- UI STYLING (All white text converted to black) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    .stApp {{ background-color: #f4f5f7 !important; color: #000000 !important; font-family: 'Roboto', sans-serif !important; }}
    h1, h2, h3 {{ color: {TB_PURPLE} !important; font-weight: 800 !important; }}
    div[data-testid="stExpander"] {{ border: 1px solid #d0d4e4 !important; border-radius: 8px !important; margin-bottom: 12px; }}
    div[data-testid="stExpander"] details summary {{ background-color: {TB_LIGHT_BLUE} !important; padding: 12px !important; border-radius: 8px 8px 0 0 !important; }}
    div[data-testid="stExpander"] details summary p {{ color: #000000 !important; font-weight: 700 !important; font-size: 16px !important; }}
    .metric-box {{ border-left: 5px solid {TB_PURPLE}; padding: 12px 15px; margin-bottom: 15px; background: white; border-radius: 0 4px 4px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .metric-title {{ font-size: 11px; text-transform: uppercase; color: #000000 !important; font-weight: 800; }}
    .metric-value {{ font-size: 20px; color: #000000 !important; font-weight: 800; }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #000000 !important; font-weight: 700 !important; border-radius: 6px !important; width: 100%; border: 1px solid #323338 !important; }}
    .stButton>button:hover {{ background-color: {TB_GREEN} !important; color: #000000 !important; }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
@st.cache_data(ttl=300)
def load_sent_records_from_sheet(sheet_url):
    try:
        export_url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid={SAVED_ROUTES_GID}"
        df = pd.read_csv(export_url)
        sent_tasks = set()
        df.columns = [c.strip().lower() for c in df.columns]
        if 'json payload' in df.columns:
            for payload_str in df['json payload'].dropna():
                try:
                    payload_data = json.loads(payload_str)
                    t_ids = payload_data.get('taskIds', '')
                    if t_ids:
                        split_ids = str(t_ids).replace('|', ',').split(',')
                        sent_tasks.update([tid.strip() for tid in split_ids])
                except: continue
        if 'taskids' in df.columns:
            for ids in df['taskids'].dropna().astype(str):
                split_ids = ids.replace('|', ',').split(',')
                sent_tasks.update([tid.strip() for tid in split_ids])
        return sent_tasks
    except: return set()

def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_gmaps_directions(home, waypoints_tuple):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints_tuple)}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            t_str = f
