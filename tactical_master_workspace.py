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
ACCEPTED_ROUTES_GID = "934075207" 
DECLINED_ROUTES_GID = "600909788"

# Terraboost Media Brand Palette
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_APP_BG = "#f1f5f9"    
TB_HOVER_GRAY = "#e2e8f0" 

# Status Fills
TB_GREEN_FILL = "#dcfce7" # Ready
TB_BLUE_FILL = "#dbeafe"  # Sent
TB_RED_FILL = "#ffcccc"   # Flagged

POD_CONFIGS = {
    "Blue": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}},
    "Green": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}},
    "Orange": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}},
    "Purple": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}},
    "Red": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}}
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

st.set_page_config(page_title="Dispatch Command Center", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
    .main .block-container {{ max-width: 1100px !important; padding-top: 2rem; }}
    h1, h2, h3, h4, h5, h6 {{ color: #000000 !important; font-weight: 800 !important; }}
    .stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: rgba(255,255,255,0.6); padding: 10px; border-radius: 15px; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 10px !important; padding: 10px 20px !important; font-weight: 700 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(1) {{ background-color: #ffffff !important; color: #000000 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(2) {{ background-color: #dbeafe !important; color: #000000 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(3) {{ background-color: #dcfce7 !important; color: #000000 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(4) {{ background-color: #ffedd5 !important; color: #000000 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(5) {{ background-color: #f3e8ff !important; color: #000000 !important; }}
    .stTabs [data-baseweb="tab"]:nth-of-type(6) {{ background-color: #fee2e2 !important; color: #000000 !important; }}
    .stTabs [aria-selected="true"] {{ transform: scale(1.05); border: 2px solid {TB_PURPLE} !important; z-index: 1; }}
    div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1 !important; border-radius: 15px !important; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; background-color: #ffffff !important; }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #ffffff !important; font-weight: 800 !important; border-radius: 12px !important; width: 100%; border: none !important; }}
    .gmail-btn {{ text-align: center; background-color: {TB_GREEN} !important; color: #ffffff !important; padding: 12px; border-radius: 12px; font-weight: 800; display: block; text-decoration: none; }}
    </style>
""" ,unsafe_allow_html=True)

# --- UTILITIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

def fetch_sent_records_from_sheet():
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets_to_fetch = [(SAVED_ROUTES_GID, "sent"), (ACCEPTED_ROUTES_GID, "accepted"), (DECLINED_ROUTES_GID, "declined")]
        sent_dict = {}
        for gid, status_label in sheets_to_fetch:
            df = pd.read_csv(base_url + gid)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if 'json payload' in df.columns:
                for _, row in df.iterrows():
                    try:
                        p = json.loads(row['json payload'])
                        tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                        raw_date = row.get('date created', '')
                        formatted_date = pd.to_datetime(raw_date).strftime('%m/%d %I:%M %p') if raw_date else ""
                        for tid in tids:
                            tid = tid.strip()
                            if tid:
                                sent_dict[tid] = {
                                    "name": row.get('contractor', 'Unknown'),
                                    "status": status_label,
                                    "time": formatted_date
                                }
                    except: continue
        return sent_dict
    except: return {}

@st.cache_data(show_spinner=False)
def get_gmaps(home, waypoints):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints)}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return 0, 0, "0h 0m"

# --- CORE LOGIC ---
def process_pod(pod_name):
    config = POD_CONFIGS[pod_name]
    progress_bar = st.progress(0, text=f"📥 Extracting {pod_name} tasks...")
    try:
        APPROVED_TEAMS = ["a - escalation", "b - boosted campaigns", "b - local campaigns", "c - priority nationals", "cvs kiosk removal", "n - national campaigns"]
        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = [t['id'] for t in teams_res if any(appr in str(t.get('name','')).lower() for appr in APPROVED_TEAMS)]
        esc_team_ids = [t['id'] for t in teams_res if 'escalation' in str(t.get('name','')).lower()]

        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
        
        unique_tasks = {t['id']: t for t in all_tasks_raw}
        pool = []
        for t in unique_tasks.values():
            container = t.get('container', {})
            if container.get('type') == 'TEAM' and container.get('team') not in target_team_ids: continue
            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            if stt in config['states']:
                pool.append({"id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt, "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}", "lat": t['destination']['location'][1], "lon": t['destination']['location'][0], "escalated": (container.get('team') in esc_team_ids)})

        clusters = []
        while pool:
            anc = pool.pop(0)
            group = [anc]
            rem = []
            for t in pool:
                if haversine(anc['lat'], anc['lon'], t['lat'], t['lon']) <= 50: group.append(t)
                else: rem.append(t)
            pool = rem
            clusters.append({"data": group, "center": [anc['lat'], anc['lon']], "stops": len(set(x['full'] for x in group)), "city": anc['city'], "state": anc['state'], "esc_count": sum(1 for x in group if x.get('escalated'))})
        st.session_state[f"clusters_{pod_name}"] = clusters
    except Exception as e: st.error(f"Error initializing {pod_name}: {e}")

def render_dispatch(i, cluster, pod_name, is_sent=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"
    
    st.write("### 📍 Route Stops")
    stop_metrics = {}
    for c in cluster['data']:
        addr = c['full']
        if addr not in stop_metrics: stop_metrics[addr] = {'t_count': 0}
        stop_metrics[addr]['t_count'] += 1
        st.markdown(f"**{addr}** — <span style='color: #633094;'>{stop_metrics[addr]['t_count']} Tasks</span>", unsafe_allow_html=True)
    
    st.divider()
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df.dropna(subset=['Lat', 'Lng']).copy()
    v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
    v_ics = v_ics[v_ics['d'] <= 60].sort_values('d').head(5)

    if v_ics.empty: return st.error("No contractors found.")
    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    col_a, col_b, col_c = st.columns([2,1,1])
    sel_label = col_a.selectbox("Contractor", list(ic_opts.keys()), key=f"sel_{cluster_hash}")
    rate = col_b.number_input("Rate/Stop", 16.0, 150.0, 18.0, key=f"rt_{cluster_hash}")
    due = col_c.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}")

    ic = ic_opts[sel_label]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(stop_metrics.keys())[:25])
    pay = round(max(cluster['stops'] * rate, hrs * 25.0), 2)
    sig = f"Work Order: {ic['Name']} - {datetime.now().strftime('%m%d%Y')}\nStops: {cluster['stops']}\nCompensation: ${pay}\nLink: {PORTAL_BASE_URL}?route={link_id}"

    col1, col2 = st.columns(2)
    with col1:
        if not real_id and st.button("☁️ Push & Generate Link", key=f"btn_{cluster_hash}"):
            payload = {"icn": ic['Name'], "ice": ic['Email'], "wo": f"WO-{cluster_hash[:5]}", "due": str(due), "comp": pay, "taskIds": ",".join(task_ids)}
            res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
            if res.get("success"):
                st.session_state[sync_key] = res.get("routeId")
                st.rerun()
    with col2:
        if real_id:
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su=Route Request&body={requests.utils.quote(sig)}"
            if st.button("🚀 OPEN IN GMAIL", key=f"gbtn_{cluster_hash}"):
                now_ts = datetime.now().strftime('%m/%d %I:%M %p')
                st.session_state[f"contractor_{cluster_hash}"] = ic['Name']
                st.session_state[f"sent_ts_{cluster_hash}"] = now_ts
                st.components.v1.html(f"<script>window.open('{gmail_url}', '_blank');</script>", height=0)
                time.sleep(0.5)
                st.rerun()

def run_pod_tab(pod_name):
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name}", key=f"init_{pod_name}"): process_pod(pod_name); st.rerun()
        return
    
    cls = st.session_state[f"clusters_{pod_name}"]
    sent_db = st.session_state.get("sent_db", {})
    ready, review, sent, accepted, declined = [], [], [], [], []
    
    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        sheet_match = next((sent_db[tid] for tid in task_ids if tid in sent_db), None)
        local_sent_name = st.session_state.get(f"contractor_{cluster_hash}")
        local_ts = st.session_state.get(f"sent_ts_{cluster_hash}", "")
        
        if sheet_match or local_sent_name:
            c['contractor_name'] = sheet_match['name'] if sheet_match else local_sent_name
            c['route_ts'] = sheet_match['time'] if (sheet_match and sheet_match['time']) else local_ts
            status = sheet_match['status'] if sheet_match else "sent"
            if status == "accepted": accepted.append(c)
            elif status == "declined": declined.append(c)
            else: sent.append(c)
        else: ready.append(c)

    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    st_folium(m, width=1100, height=400, key=f"map_{pod_name}")
    st.markdown("---")
    t1, t2, t3, gap, t4, t5, end = st.tabs(["Ready", "Sent", "Flagged", " ", "Accepted", "Declined", " "])
    
    with t2:
        for i, c in enumerate(sent):
            ts_label = f" | {c.get('route_ts','')}"
            with st.expander(f"✉️ Sent: {c['contractor_name']}{ts_label}"): render_dispatch(i+500, c, pod_name, True)
    with t4:
        for i, c in enumerate(accepted):
            ts_label = f" | {c.get('route_ts','')}"
            with st.expander(f"✅ {c['contractor_name']}{ts_label}"): render_dispatch(i+2000, c, pod_name, True)
    with t5:
        for i, c in enumerate(declined):
            ts_label = f" | {c.get('route_ts','')}"
            with st.expander(f"❌ {c['contractor_name']}{ts_label}"): render_dispatch(i+3000, c, pod_name)
    with t1:
        for i, c in enumerate(ready):
            with st.expander(f"📍 {c['city']} | {c['stops']} Stops"): render_dispatch(i, c, pod_name)

# Start
if "ic_df" not in st.session_state:
    try: st.session_state.ic_df = pd.read_csv(f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0")
    except: st.error("DB Error")

st.markdown("<h1>Dispatch Command Center</h1>", unsafe_allow_html=True)
pod_tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])
for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with pod_tabs[i]: run_pod_tab(pod)
