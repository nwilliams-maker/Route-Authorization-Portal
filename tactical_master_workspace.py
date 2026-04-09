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

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

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

st.set_page_config(page_title="Terraboost Tactical Workspace", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    .stApp {{ background-color: #f4f5f7 !important; color: #000000 !important; font-family: 'Roboto', sans-serif !important; }}
    h1, h2, h3 {{ color: {TB_PURPLE} !important; font-weight: 800 !important; }}
    div[data-testid="stExpander"] {{ border: 1px solid #d0d4e4 !important; border-radius: 8px !important; margin-bottom: 12px; }}
    div[data-testid="stExpander"] details summary {{ background-color: {TB_LIGHT_BLUE} !important; padding: 12px !important; border-radius: 8px 8px 0 0 !important; }}
    div[data-testid="stExpander"] details summary p {{ color: #1e293b !important; font-weight: 700 !important; font-size: 16px !important; }}
    div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 700 !important; font-size: 14px !important; opacity: 1 !important; }}
    .stTextInput input, .stNumberInput input, .stDateInput input, div[data-baseweb="select"] > div {{ background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #323338 !important; opacity: 1 !important; }}
    div[data-testid="stTextArea"] textarea {{ color: #000000 !important; background-color: #FFFFFF !important; border: 1px solid #323338 !important; font-weight: 600 !important; opacity: 1 !important; }}
    div[data-testid="stTextArea"] label p {{ color: #000000 !important; font-weight: 800 !important; }}
    .metric-box {{ border-left: 5px solid {TB_PURPLE}; padding: 12px 15px; margin-bottom: 15px; background: white; border-radius: 0 4px 4px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .metric-title {{ font-size: 11px; text-transform: uppercase; color: #444444 !important; font-weight: 800; }}
    .metric-value {{ font-size: 20px; color: {TB_PURPLE} !important; font-weight: 800; }}
    .stTabs [data-baseweb="tab"] {{ color: #444444 !important; font-weight: 600 !important; }}
    .stTabs [aria-selected="true"] {{ color: {TB_PURPLE} !important; border-bottom: 3px solid {TB_GREEN} !important; }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #FFFFFF !important; font-weight: 700 !important; border-radius: 6px !important; width: 100%; }}
    .stButton>button:hover {{ background-color: {TB_GREEN} !important; }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
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
            t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
            return round(mi, 1), hrs, t_str
    except: pass
    return 0, 0, "0h 0m"

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try:
        export_url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0"
        return pd.read_csv(export_url)
    except: return None

# --- PROCESSING ---
def process_pod_data(pod_name):
    config = POD_CONFIGS[pod_name]
    ui_container = st.empty()
    with ui_container.container():
        p_bar = st.progress(0, text=f"📡 Syncing {pod_name}...")
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
            stt = normalize_state(a.get('state', ''))
            if stt in config['states']:
                pool.append({"id": t['id'], "city": a.get('city', 'Unknown'), "state": stt,
                    "full_addr": f"{a.get('number', '')} {a.get('street', '')}, {a.get('city', '')}, {stt}",
                    "lat": t.get('destination', {}).get('location', [0, 0])[1],
                    "lon": t.get('destination', {}).get('location', [0, 0])[0]})
        clusters = []
        while pool:
            anchor = pool.pop(0)
            group, unique_locs, rem = [anchor], {anchor['full_addr']}, []
            for t in pool:
                if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 50.0:
                    group.append(t); unique_locs.add(t['full_addr'])
                else: rem.append(t)
            pool = rem
            clusters.append({"data": group, "center": [anchor['lat'], anchor['lon']], "unique_count": len(unique_locs), "city": anchor['city'], "state": anchor['state']})
        st.session_state[f"clusters_{pod_name}"] = clusters
    ui_container.empty()

# --- DISPATCH RENDER ---
def render_dispatch_logic(i, cluster, pod_name, is_sent=False):
    cluster_hash = hashlib.md5("".join(sorted([t['id'] for t in cluster['data']])).encode()).hexdigest()
    sync_key, sent_key = f"sync_{cluster_hash}", f"sent_log_{cluster_hash}"
    real_gas_id = st.session_state.get(sync_key, None)
    link_id = real_gas_id if real_gas_id else "LINK_GENERATED_UPON_SYNC"

    loc_sum = {}
    for c in cluster['data']:
        addr = c['full_addr']; loc_sum[addr] = loc_sum.get(addr, 0) + 1
    for addr, count in loc_sum.items(): st.markdown(f"• **{addr}** ({count} Tasks)")
    st.divider()

    if is_sent and sent_key in st.session_state:
        log = st.session_state[sent_key]
        st.info(f"📧 **Sent to:** {log['contractor']} | **Timestamp:** {log['time']}")

    ic_df = st.session_state.ic_df
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].copy()
    v_ics = v_ics.dropna(subset=['Lat', 'Lng'])
    c_lat, c_lon = cluster['center']
    v_ics['d'] = v_ics.apply(lambda x: haversine(c_lat, c_lon, x['Lat'], x['Lng']), axis=1)
    valid_ics = v_ics[v_ics['d'] <= MAX_DEADHEAD_MILES].sort_values('d').head(5)

    if valid_ics.empty:
        st.error("⚠️ No Independent Contractors nearby."); return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}
    c_ic, c_rate, c_due = st.columns([2, 1, 1])
    sel_label = c_ic.selectbox("Contractor", list(ic_opts.keys()), key=f"s_{i}_{pod_name}")
    rate = c_rate.number_input("Rate/Stop", 16.0, 150.0, 18.0, 0.5, key=f"r_{i}_{pod_name}")
    due = c_due.date_input("Due Date", datetime.now().date() + timedelta(days=14), key=f"d_{i}_{pod_name}")
    
    sel_ic = ic_opts[sel_label]
    mi, hrs, t_str = fetch_gmaps_directions(sel_ic['Location'], tuple(list(loc_sum.keys())[:10]))
    
    # Calculation Logic
    stop_count = cluster['unique_count']
    pay = max(stop_count * rate, hrs * HOURLY_FLOOR_RATE)
    eff_stop = pay / stop_count if stop_count > 0 else 0
    is_critical = eff_stop > REVIEW_PER_STOP_LIMIT

    st.markdown(f"""
        <div style="background-color: {TB_RED if is_critical else '#f8fafc'}; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 15px;">
            <span style="color: {'white' if is_critical else '#444444'}; font-weight: 800; font-size: 10px; text-transform: uppercase;">Financials</span><br>
            <span style="color: {'white' if is_critical else 'black'}; font-weight: 700; font-size: 16px;">Comp: <span style="color: {TB_GREEN if not is_critical else '#ffcccc'};">${pay:.2f}</span></span> | 
            <span style="color: {'white' if is_critical else 'black'}; font-weight: 600;">Time: {t_str}</span> | <span style="color: {'white' if is_critical else 'black'}; font-weight: 600;">Avg: ${eff_stop:.2f}/stop</span>
        </div>
    """, unsafe_allow_html=True)

    wo_title = f"{sel_ic['Name']} - {datetime.now().strftime('%m%d%Y')}-{i}"
    loc_lines = [f"{idx + 1}. {a} ({count} Tasks)" for idx, (a, count) in enumerate(loc_sum.items())]
    sig = (f"Work Order: {wo_title}\nContractor: {sel_ic['Name']}\nDue Date: {due.strftime('%A, %b %d, %Y')}\n\n"
           f"Metrics:\n- Unique Stops: {stop_count}\n- Mileage: {mi} mi\n- Time: {t_str}\n- Compensation: ${pay:.2f}\n\n"
           f"STOP LOCATIONS:\n" + "\n".join(loc_lines) + f"\n\nAuthorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true")
    
    # 🎯 FIX: tied key to sel_ic['Name'] to ensure refresh on change
    st.text_area("Email Payload Preview", sig, height=250, key=f"area_{i}_{pod_name}_{sel_ic['Name']}")

def run_pod_tab(pod_name):
    st.markdown(f"<h2>{pod_name} Command Center</h2>", unsafe_allow_html=True)
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"📥 Initialize {pod_name}", key=f"init_{pod_name}"): process_pod_data(pod_name); st.rerun()
        return
    clusters = st.session_state[f"clusters_{pod_name}"]
    ic_df = st.session_state.ic_df
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']) if ic_df is not None else pd.DataFrame()
    ready, review, sent = [], [], []
    for c in clusters:
        c_h = hashlib.md5("".join(sorted([t['id'] for t in c['data']])).encode()).hexdigest()
        if f"sent_log_{c_h}" in st.session_state: sent.append(c); continue
        has_ic = v_ics.apply(lambda x: haversine(c['center'][0], c['center'][1], x['Lat'], x['Lng']), axis=1).le(MAX_DEADHEAD_MILES).any() if not v_ics.empty else False
        _, hrs, _ = fetch_gmaps_directions(f"{c['center'][0]},{c['center'][1]}", tuple([d['full_addr'] for d in c['data'][:10]]))
        gate_avg = (hrs * HOURLY_FLOOR_RATE) / c['unique_count'] if c['unique_count'] > 0 else 0
        if has_ic and gate_avg <= REVIEW_PER_STOP_LIMIT: ready.append(c)
        else: review.append(c)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"<div class='metric-box'><div class='metric-title'>Total</div><div class='metric-value'>{len(clusters)}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-box'><div class='metric-title' style='color:{TB_GREEN}'>Ready</div><div class='metric-value'>{len(ready)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-box'><div class='metric-title' style='color:{TB_BLUE}'>Sent</div><div class='metric-value'>{len(sent)}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-box'><div class='metric-title' style='color:#f44336'>Review</div><div class='metric-value'>{len(review)}</div></div>", unsafe_allow_html=True)
    if c5.button("🔄 Refresh", key=f"ref_{pod_name}"): process_pod_data(pod_name); st.rerun()

    m = folium.Map(location=clusters[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=10, color=TB_GREEN, fill=True, opacity=0.7).add_to(m)
    for c in sent: folium.CircleMarker(c['center'], radius=10, color=TB_BLUE, fill=True, opacity=0.7).add_to(m)
    for c in review: folium.CircleMarker(c['center'], radius=10, color="#f44336", fill=True, opacity=0.7).add_to(m)
    st_folium(m, use_container_width=True, height=450, key=f"map_{pod_name}")
    
    t1, t2, t3 = st.tabs(["🟢 Ready", "📧 Sent", "🔴 Review"])
    with t1:
        for i, c in enumerate(ready):
            with st.expander(f"📍 {c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i, c, pod_name)
    with t2:
        for i, c in enumerate(sent):
            with st.expander(f"✅ Sent | {c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i+500, c, pod_name, is_sent=True)
    with t3:
        for i, c in enumerate(review):
            with st.expander(f"🔴 Review Required | {c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i+1000, c, pod_name)

# --- GLOBAL TAB ---
def run_global_tab():
    st.markdown("## 🌎 Global Network Overview")
    if st.button("🚀 Sync Global Network"):
        p_bar = st.progress(0, text="Initializing Network Sweep...")
        pods = list(POD_CONFIGS.keys())
        for idx, pod in enumerate(pods):
            progress_step = (idx + 1) / len(pods)
            process_pod_data(pod)
            p_bar.progress(progress_step, text=f"Synced {pod}...")
        st.success("Global Sync Complete!")
        st.rerun()

# --- MAIN ---
if "ic_df" not in st.session_state: st.session_state.ic_df = load_ic_database(IC_SHEET_URL)
st.markdown("<h1>Network Command Center</h1>", unsafe_allow_html=True)
tabs = st.tabs(["🌎 Global", "🔵 Blue Pod", "🟢 Green Pod", "🟠 Orange Pod", "🟣 Purple Pod", "🔴 Red Pod"])
with tabs[0]: run_global_tab()
with tabs[1]: run_pod_tab("Blue Pod")
with tabs[2]: run_pod_tab("Green Pod")
with tabs[3]: run_pod_tab("Orange Pod")
with tabs[4]: run_pod_tab("Purple Pod")
with tabs[5]: run_pod_tab("Red Pod")
