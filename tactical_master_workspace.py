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

# Terraboost Media Brand Colors
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_GRAY_BG = "#cbd5e1"
TB_OFF_WHITE = "#f8fafc"
TB_LIGHT_BLUE = "#f0f7ff"

# Pod Configuration
POD_CONFIGS = {
    "Blue": {
        "states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"},
        "bg": "#dbeafe", "text": "#1e3a8a"
    },
    "Green": {
        "states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"},
        "bg": "#dcfce7", "text": "#064e3b"
    },
    "Orange": {
        "states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"},
        "bg": "#ffedd5", "text": "#7c2d12"
    },
    "Purple": {
        "states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"},
        "bg": "#f3e8ff", "text": "#581c87"
    },
    "Red": {
        "states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"},
        "bg": "#fee2e2", "text": "#7f1d1d"
    }
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Terraboost Tactical Workspace", layout="wide")

# --- UI STYLING (Color-Coded Tabs Fix) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    .stApp {{ background-color: {TB_GRAY_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
    h1, h2, h3 {{ color: {TB_PURPLE} !important; font-weight: 800 !important; }}

    /* TAB DYNAMICS */
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 20px !important;
        font-weight: 700 !important;
        border: 1px solid #94a3b8 !important;
    }}

    /* Specific Tab Fills */
    .stTabs [data-baseweb="tab"]:nth-of-type(1) {{ background-color: #f1f5f9 !important; color: #475569 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(2) {{ background-color: #dbeafe !important; color: #1e3a8a !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(3) {{ background-color: #dcfce7 !important; color: #064e3b !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(4) {{ background-color: #ffedd5 !important; color: #7c2d12 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(5) {{ background-color: #f3e8ff !important; color: #581c87 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(6) {{ background-color: #fee2e2 !important; color: #7f1d1d !important; }}

    .stTabs [aria-selected="true"] {{
        border-bottom: 4px solid {TB_PURPLE} !important;
        transform: translateY(-2px);
    }}

    /* Expander Styling */
    div[data-testid="stExpander"] {{ 
        border: 1.5px solid #94a3b8 !important; 
        border-radius: 12px !important; 
        background-color: #FFFFFF !important;
        margin-bottom: 12px; 
    }}
    
    div[data-testid="stExpander"] details summary p {{ color: #000000 !important; font-weight: 800 !important; }}

    /* Inputs */
    div[data-baseweb="select"] > div, 
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stDateInput"] input {{
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1.5px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }}

    .stButton>button {{ 
        background-color: {TB_PURPLE} !important; 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        border-radius: 10px !important; 
    }}
    
    .gmail-btn {{
        text-align: center; background-color: {TB_GREEN} !important; color: white !important; 
        padding: 12px; border-radius: 12px; font-weight: 800; text-decoration: none; display: block;
    }}
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
                        sent_tasks.update([tid.strip() for tid in str(t_ids).replace('|', ',').split(',')])
                except: continue
        return sent_tasks
    except: return set()

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
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
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
        st.write(f"📡 Processing {pod_name} Pod...")
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
            stt = (a.get('state', '') or '').strip().upper()
            if stt in config['states']:
                pool.append({"id": t['id'], "city": a.get('city', 'Unknown'), "state": stt,
                    "full_addr": f"{a.get('number', '')} {a.get('street', '')}, {a.get('city', '')}, {stt}",
                    "lat": t.get('destination', {}).get('location', [0, 0])[1],
                    "lon": t.get('destination', {}).get('location', [0, 0])[0]})
        clusters = []
        while pool:
            anchor = pool.pop(0); group, unique_locs, rem = [anchor], {anchor['full_addr']}, []
            for t in pool:
                if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 50.0:
                    group.append(t); unique_locs.add(t['full_addr'])
                else: rem.append(t)
            pool = rem
            clusters.append({"data": group, "center": [anchor['lat'], anchor['lon']], "unique_count": len(unique_locs), "city": anchor['city'], "state": anchor['state']})
        st.session_state[f"clusters_{pod_name}"] = clusters
    ui_container.empty()

def render_dispatch_logic(i, cluster, pod_name, is_sent=False):
    cluster_task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(cluster_task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_gas_id = st.session_state.get(sync_key, None)
    link_id = real_gas_id if real_gas_id else "LINK_PENDING"

    loc_sum = {c['full_addr']: 0 for c in cluster['data']}
    for c in cluster['data']: loc_sum[c['full_addr']] += 1
    
    for addr, count in loc_sum.items(): st.markdown(f"**{addr}** ({count} Tasks)")
    st.divider()

    ic_df = st.session_state.ic_df
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng'])
    v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
    valid_ics = v_ics[v_ics['d'] <= 60].sort_values('d').head(5)

    if valid_ics.empty:
        st.error("⚠️ No contractors found within 60 miles."); return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}
    c_ic, c_rate, c_due = st.columns([2, 1, 1])
    sel_label = c_ic.selectbox("Contractor", list(ic_opts.keys()), key=f"s_{i}_{pod_name}")
    rate = c_rate.number_input("Rate/Stop", 16.0, 150.0, 18.0, 0.5, key=f"r_{i}_{pod_name}")
    due = c_due.date_input("Deadline", datetime.now().date() + timedelta(days=14), key=f"d_{i}_{pod_name}")
    
    sel_ic = ic_opts[sel_label]
    mi, hrs, t_str = fetch_gmaps_directions(sel_ic['Location'], tuple(list(loc_sum.keys())[:10]))
    pay = round(max(cluster['unique_count'] * rate, hrs * 25.00), 2)
    eff_stop = round(pay / cluster['unique_count'], 2) if cluster['unique_count'] > 0 else 0

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(f"<div style='background:{TB_OFF_WHITE}; border:1px solid #e2e8f0; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; color:#64748b; text-transform:uppercase;'>Financials</p><p style='margin:0; font-size:24px; font-weight:800; color:{TB_GREEN if eff_stop <= 23.00 else '#ef4444'};'>Total: ${pay:,.2f}</p><p style='margin:0; font-size:13px;'>Effective: ${eff_stop}/stop</p></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div style='background:{TB_OFF_WHITE}; border:1px solid #e2e8f0; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; color:#64748b; text-transform:uppercase;'>Logistics</p><p style='margin:0; font-size:24px; font-weight:800;'>{t_str}</p><p style='margin:0; font-size:13px;'>Round Trip: {mi} mi</p></div>", unsafe_allow_html=True)

    wo_title = f"{sel_ic['Name']} - {datetime.now().strftime('%m%d%Y')}-{i}"
    sig = (f"Work Order: {wo_title}\nContractor: {sel_ic['Name']}\nDue Date: {due.strftime('%A, %b %d, %Y')}\n\n"
           f"Metrics:\n- Stops: {cluster['unique_count']}\n- Mileage: {mi} mi\n- Time: {t_str}\n- Compensation: ${pay:.2f}\n\n"
           f"LOCATIONS:\n" + "\n".join([f"• {a} ({c} Tasks)" for a,c in loc_sum.items()]) + f"\n\nAuthorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true")
    st.text_area("Email Content", sig, height=200, key=f"area_{i}_{pod_name}_{sel_ic['Name']}")

    col1, col2 = st.columns(2)
    with col1:
        if not real_gas_id:
            if st.button("☁️ Sync Work Order", key=f"sync_btn_{i}_{pod_name}"):
                home = sel_ic['Location']
                payload = {"icn": sel_ic['Name'], "ice": sel_ic['Email'], "wo": wo_title, "due": due.strftime('%Y-%m-%d'), "comp": pay, "lCnt": cluster['unique_count'], "tCnt": len(cluster['data']), "mi": mi, "time": t_str, "locs": " | ".join([home] + list(loc_sum.keys()) + [home]), "taskIds": ",".join(cluster_task_ids), "phone": str(sel_ic['Phone']), "jobOnly": " | ".join([f"{a} ({c} Tasks)" for a,c in loc_sum.items()])}
                res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
                if res.get("success"): st.session_state[sync_key] = res.get("routeId"); st.rerun()
        else: st.button("✅ Data Synced", disabled=True, key=f"synced_{i}_{pod_name}")
    with col2:
        if real_gas_id:
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={sel_ic['Email']}&su=Route Request: {wo_title}&body={requests.utils.quote(sig)}"
            st.markdown(f'<a href="{gmail_url}" target="_blank" class="gmail-btn">🚀 SEND GMAIL NOW</a>', unsafe_allow_html=True)
            if st.button("✔️ Mark Sent", key=f"mksent_{i}_{pod_name}"):
                requests.post(GAS_WEB_APP_URL, json={"action": "markSent", "routeId": real_gas_id}); st.rerun()

def run_pod_tab(pod_name):
    st.markdown(f"## {pod_name} Pod")
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"📥 Initialize {pod_name}", key=f"init_{pod_name}"): process_pod_data(pod_name); st.rerun()
        return
    
    clusters = st.session_state[f"clusters_{pod_name}"]
    if not clusters:
        st.info("No tasks found for this pod area."); return

    sent_db = st.session_state.get("sent_db", set())
    ready, review, sent = [], [], []
    for c in clusters:
        cluster_task_ids = [str(t['id']).strip() for t in c['data']]
        if any(tid in sent_db for tid in cluster_task_ids): sent.append(c); continue
        hrs = fetch_gmaps_directions(f"{c['center'][0]},{c['center'][1]}", tuple([d['full_addr'] for d in c['data'][:10]]))[1]
        gate_avg = (hrs * 25.00) / c['unique_count'] if c['unique_count'] > 0 else 0
        if gate_avg <= 23.00: ready.append(c)
        else: review.append(c)

    c1, c2, c3, c4, c5 = st.columns(5)
    cfg = POD_CONFIGS[pod_name]
    for col, title, val in zip([c1, c2, c3, c4], ["Volume", "Ready", "Active", "Flagged"], [len(clusters), len(ready), len(sent), len(review)]):
        col.markdown(f"<div style='background:{cfg['bg']}; border:1px solid {cfg['text']}44; border-radius:12px; padding:15px; margin-bottom:15px;'><p style='margin:0; font-size:10px; font-weight:800; color:{cfg['text']}; text-transform:uppercase;'>{title}</p><p style='margin:0; font-size:24px; font-weight:800; color:{cfg['text']};'>{val}</p></div>", unsafe_allow_html=True)
    if c5.button("🔄 Sync", key=f"ref_{pod_name}"): st.session_state.sent_db = load_sent_records_from_sheet(IC_SHEET_URL); process_pod_data(pod_name); st.rerun()

    m = folium.Map(location=clusters[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=10, color=TB_GREEN, fill=True, opacity=0.8).add_to(m)
    for c in sent: folium.CircleMarker(c['center'], radius=10, color="#3b82f6", fill=True, opacity=0.8).add_to(m)
    for c in review: folium.CircleMarker(c['center'], radius=10, color="#ef4444", fill=True, opacity=0.8).add_to(m)
    st_folium(m, use_container_width=True, height=400, key=f"map_{pod_name}")
    
    t1, t2, t3 = st.tabs(["Dispatch Ready", "Active Outbox", "Under Review"])
    with t1:
        for i, c in enumerate(ready):
            with st.expander(f"{c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i, c, pod_name)
    with t2:
        for i, c in enumerate(sent):
            with st.expander(f"✓ {c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i+500, c, pod_name, is_sent=True)
    with t3:
        for i, c in enumerate(review):
            with st.expander(f"⚠ {c['city']}, {c['state']} | {c['unique_count']} Stops"): render_dispatch_logic(i+1000, c, pod_name)

if "ic_df" not in st.session_state: st.session_state.ic_df = load_ic_database(IC_SHEET_URL)
if "sent_db" not in st.session_state: st.session_state.sent_db = load_sent_records_from_sheet(IC_SHEET_URL)

st.markdown("<h1>Terraboost Media Command</h1>", unsafe_allow_html=True)
tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])
with tabs[0]: 
    st.markdown("## Global Overview")
    if st.button("🚀 Sync All Pods"): 
        st.session_state.sent_db = load_sent_records_from_sheet(IC_SHEET_URL)
        for pod in POD_CONFIGS.keys(): process_pod_data(pod)
        st.rerun()
for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)
