import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- 1. CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

# Constants
MAX_DEADHEAD_MILES = 60
HOURLY_FLOOR_RATE = 25.00
REVIEW_PER_STOP_LIMIT = 23.00 

# Branding Colors
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_RED = "#ef4444"
TB_BLUE = "#3b82f6"
TB_LIGHT_BLUE = "#e6f0fa"

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

# --- 2. THE MODERN UI CSS ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    .stApp {{ background-color: #f4f5f7 !important; color: #000000 !important; font-family: 'Roboto', sans-serif !important; }}
    h1, h2, h3 {{ color: {TB_PURPLE} !important; font-weight: 800 !important; }}
    
    /* Modern Expanders */
    div[data-testid="stExpander"] {{ border: 1px solid #d0d4e4 !important; border-radius: 12px !important; margin-bottom: 12px; background-color: white !important; }}
    div[data-testid="stExpander"] details summary {{ background-color: {TB_LIGHT_BLUE} !important; padding: 15px !important; border-radius: 12px 12px 0 0 !important; }}
    div[data-testid="stExpander"] details summary p {{ color: #1e293b !important; font-weight: 700 !important; font-size: 16px !important; }}
    
    /* Input Fields & Labels */
    div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 700 !important; font-size: 14px !important; opacity: 1 !important; }}
    .stTextInput input, .stNumberInput input, .stDateInput input, div[data-baseweb="select"] > div {{ background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #323338 !important; border-radius: 8px !important; }}
    
    /* The Modern High-Contrast Email Area */
    div[data-testid="stTextArea"] textarea {{ color: #000000 !important; background-color: #FFFFFF !important; border: 2px solid {TB_PURPLE} !important; font-weight: 500 !important; font-family: 'Courier New', Courier, monospace !important; }}
    
    /* Buttons */
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #FFFFFF !important; font-weight: 700 !important; border-radius: 8px !important; height: 3em !important; }}
    .stButton>button:hover {{ background-color: {TB_GREEN} !important; border: none !important; }}
    
    .gmail-link {{ display: block; text-align: center; background-color: {TB_GREEN} !important; color: white !important; padding: 14px; border-radius: 8px; text-decoration: none; font-weight: 800; margin-top: 10px; border: 1px solid #5d911a; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT DATA UTILITIES ---
@st.cache_data(ttl=120)
def fetch_database_sent_status():
    """Talks to Google Sheet to see what is already SENT."""
    try:
        res = requests.get(f"{GAS_WEB_APP_URL}?action=getSentRoutes")
        return set(res.json().get("sentIds", []))
    except: return set()

@st.cache_data(ttl=600)
def load_ics(url):
    try:
        export_url = f"{url.split('/edit')[0]}/export?format=csv&gid=0"
        return pd.read_csv(export_url)
    except: return None

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_directions(home, stops):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(stops)}&key={GOOGLE_MAPS_KEY}"
    try:
        r = requests.get(url).json()
        if r['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in r['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in r['routes'][0]['legs']) / 3600
            t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
            return round(mi, 1), hrs, t_str
    except: pass
    return 0, 0, "0h 0m"

# --- 4. CLUSTERING & POD LOGIC ---
def run_pod_processing(pod_name, p_bar=None, step=0.0):
    config = POD_CONFIGS[pod_name]
    if p_bar: p_bar.progress(step, text=f"Scanning Onfleet Network: {pod_name}...")
    
    # Onfleet Fetch (Simplified for logic flow)
    all_tasks = []
    url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}"
    while True:
        res = requests.get(url, headers=headers)
        if res.status_code != 200: break
        data = res.json(); batch = data.get('tasks', [])
        all_tasks.extend(batch)
        if data.get('lastId') and len(batch) > 0:
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}&lastId={data['lastId']}"
        else: break

    pool = []
    for t in all_tasks:
        a = t.get('destination', {}).get('address', {})
        stt = STATE_MAP.get(str(a.get('state', '')).strip().upper(), a.get('state', ''))
        if stt in config['states']:
            pool.append({"id": t['id'], "city": a.get('city', 'Unknown'), "addr": f"{a.get('number', '')} {a.get('street', '')}, {a.get('city', '')}, {stt}",
                        "lat": t.get('destination', {}).get('location', [0, 0])[1], "lon": t.get('destination', {}).get('location', [0, 0])[0]})

    clusters = []
    while pool:
        anchor = pool.pop(0)
        group, unique_locs, rem = [anchor], {anchor['addr']}, []
        for t in pool:
            if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 50.0:
                group.append(t); unique_locs.add(t['addr'])
            else: rem.append(t)
        pool = rem
        c_id = hashlib.md5("".join(sorted([t['id'] for t in group])).encode()).hexdigest()
        clusters.append({"id": c_id, "data": group, "center": [anchor['lat'], anchor['lon']], "unique_count": len(unique_locs), "city": anchor['city']})
    
    st.session_state[f"clusters_{pod_name}"] = clusters

# --- 5. THE MODERN DISPATCH CARD ---
def render_dispatch_card(i, cluster, pod_name):
    sync_key = f"sync_{cluster['id']}"
    gas_id = st.session_state.get(sync_key)
    
    loc_sum = {}
    for c in cluster['data']: loc_sum[c['addr']] = loc_sum.get(c['addr'], 0) + 1
    for addr, count in loc_sum.items(): st.markdown(f"• **{addr}** ({count})")
    st.divider()

    ic_df = st.session_state.ic_df
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
    valid_ics = v_ics[v_ics['d'] <= MAX_DEADHEAD_MILES].sort_values('d').head(5)

    if valid_ics.empty: st.error("No Independent Contractors within 60 miles."); return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}
    c_ic, c_rate, c_due = st.columns([2, 1, 1])
    sel_label = c_ic.selectbox("Select Contractor", list(ic_opts.keys()), key=f"sel_{i}")
    rate = c_rate.number_input("Rate/Stop", 16.0, 200.0, 18.0, 0.5, key=f"rate_{i}")
    due = c_due.date_input("Due Date", datetime.now().date() + timedelta(days=14), key=f"due_{i}")

    sel_ic = ic_opts[sel_label]
    mi, hrs, t_str = fetch_directions(sel_ic['Location'], tuple(list(loc_sum.keys())[:10]))
    pay = max(cluster['unique_count'] * rate, hrs * HOURLY_FLOOR_RATE)
    eff_stop = pay / cluster['unique_count'] if cluster['unique_count'] > 0 else 0
    
    # Financial Visual
    is_critical = eff_stop > REVIEW_PER_STOP_LIMIT
    st.markdown(f"""
        <div style="background-color: {TB_RED if is_critical else '#f8fafc'}; padding: 15px; border-radius: 10px; border: 1px solid #d0d4e4; margin-bottom: 20px;">
            <span style="color: {'white' if is_critical else '#64748b'}; font-weight: 800; font-size: 11px; text-transform: uppercase;">Route Financials</span><br>
            <span style="color: {'white' if is_critical else 'black'}; font-weight: 700; font-size: 18px;">Comp: ${pay:.2f}</span> | 
            <span style="color: {'white' if is_critical else 'black'}; font-weight: 600;">Time: {t_str}</span> | <span style="color: {'white' if is_critical else 'black'}; font-weight: 600;">Efficiency: ${eff_stop:.2f}/stop</span>
        </div>
    """, unsafe_allow_html=True)

    # 🎯 DYNAMIC EMAIL SIGNATURE
    wo_title = f"{sel_ic['Name']} - {datetime.now().strftime('%m%d%Y')}-{i}"
    sig = (f"Work Order: {wo_title}\n"
           f"Due Date: {due.strftime('%m/%d/%Y')}\n"
           f"Stops: {cluster['unique_count']}\n"
           f"Metrics: {mi} mi, {t_str}\n"
           f"Compensation: ${pay:.2f}\n"
           f"Authorize Here: {PORTAL_BASE_URL}?route={gas_id or 'PENDING'}&v2=true")
    
    st.text_area("Final Email Preview", sig, height=220, key=f"sig_{i}_{sel_ic['Name']}_{rate}")

    b1, b2 = st.columns(2)
    with b1:
        if not gas_id:
            if st.button("☁️ Sync Work Order", key=f"sync_btn_{i}"):
                payload = {"icn": sel_ic['Name'], "ice": sel_ic['Email'], "wo": wo_title, "comp": pay, "tCnt": len(cluster['data']), "lCnt": cluster['unique_count'], "mi": mi, "time": t_str, "locs": " | ".join(list(loc_sum.keys()))}
                res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
                if res.get("success"): st.session_state[sync_key] = res.get("routeId"); st.rerun()
        else: st.button("✅ Data Synced", disabled=True)
    with b2:
        if gas_id:
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={sel_ic['Email']}&su=Route Request: {wo_title}&body={requests.utils.quote(sig)}"
            st.markdown(f'<a href="{gmail_url}" target="_blank" class="gmail-link">🚀 OPEN GMAIL NOW</a>', unsafe_allow_html=True)
            if st.button("✔️ Mark Sent Permanently", key=f"mark_sent_{i}"):
                requests.post(GAS_WEB_APP_URL, json={"action": "markSent", "routeId": gas_id})
                st.rerun()

# --- 6. TAB LOGIC ---
def render_pod_tab(pod_name):
    if f"clusters_{pod_name}" not in st.session_state:
        st.info(f"Initialize {pod_name} or run Global Sync.")
        return
    
    clusters = st.session_state[f"clusters_{pod_name}"]
    sent_ids = fetch_database_sent_status()
    ready, review, sent = [], [], []
    
    for c in clusters:
        if c['id'] in sent_ids: sent.append(c); continue
        # Calculation for placement
        _, hrs, _ = fetch_directions("USA", tuple([t['addr'] for t in c['data'][:10]]))
        gate_avg = (hrs * HOURLY_FLOOR_RATE) / c['unique_count'] if c['unique_count'] > 0 else 0
        if gate_avg <= REVIEW_PER_STOP_LIMIT: ready.append(c)
        else: review.append(c)

    st.markdown(f"### {pod_name} Metrics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ready", len(ready))
    c2.metric("In Review", len(review))
    c3.metric("Dispatched", len(sent))
    
    t1, t2, t3 = st.tabs(["🟢 Ready for Dispatch", "📧 Sent / Logged", "🔴 Financial Review"])
    with t1:
        for i, c in enumerate(ready):
            with st.expander(f"📍 {c['city']} | {c['unique_count']} Stops"): render_dispatch_card(i, c, pod_name)
    with t2:
        for c in sent: st.success(f"✅ Dispatched: {c['city']} Network Cluster")
    with t3:
        for i, c in enumerate(review):
            with st.expander(f"🔴 Review Required: {c['city']}"): render_dispatch_card(i+1000, c, pod_name)

# --- 7. MAIN RUNNER ---
if "ic_df" not in st.session_state: st.session_state.ic_df = load_ics(IC_SHEET_URL)
st.markdown("# 🌎 Network Command Center")
tabs = st.tabs(["🌎 Global Sync", "🔵 Blue Pod", "🟢 Green Pod", "🟠 Orange Pod", "🟣 Purple Pod", "🔴 Red Pod"])
with tabs[0]:
    if st.button("🚀 Sync National Onfleet Network"):
        p_bar = st.progress(0)
        pods = list(POD_CONFIGS.keys())
        for idx, pod in enumerate(pods):
            run_pod_processing(pod, p_bar, (idx+1)/len(pods))
        st.success("Global Intelligence Loaded.")
        st.rerun()
for idx, pod in enumerate(POD_CONFIGS.keys()):
    with tabs[idx+1]: render_pod_tab(pod)
