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

/* GLOBAL TABS STYLING */
.stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 8px; background: rgba(255,255,255,0.6); padding: 10px; border-radius: 15px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 10px !important; padding: 10px 20px !important; font-weight: 700 !important; }}

/* TOP LEVEL TABS (Pod Colors) */
.stTabs [data-baseweb="tab"]:nth-of-type(1) {{ background-color: #ffffff !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(2) {{ background-color: #dbeafe !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(3) {{ background-color: #dcfce7 !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(4) {{ background-color: #ffedd5 !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(5) {{ background-color: #f3e8ff !important; color: #000000 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(6) {{ background-color: #fee2e2 !important; color: #000000 !important; }}
.stTabs [aria-selected="true"] {{ transform: scale(1.05); border: 2px solid {TB_PURPLE} !important; z-index: 1; }}

/* TARGET THE GMAIL (PRIMARY) BUTTON SPECIFICALLY */
button[kind="primary"] {{
    background-color: #76bc21 !important; /* TB_GREEN */
    color: white !important;
    height: 3.5rem !important;
    font-size: 1.2rem !important;
    font-weight: 800 !important;
    border: none !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    transition: all 0.2s ease !important;
}}

button[kind="primary"]:hover {{
    filter: brightness(1.1) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 10px rgba(0,0,0,0.15) !important;
}}

/* TARGET SECONDARY BUTTONS (Revoke, Initialize, etc.) */
button[kind="secondary"] {{
    background-color: #ffffff !important;
    color: {TB_PURPLE} !important;
    border: 2px solid {TB_PURPLE} !important;
    height: 42px !important;  /* SHRUNK FROM 54px */
    font-size: 0.9rem !important; /* SCALED DOWN SLIGHTLY */
    font-weight: 800 !important;
    border-radius: 8px !important; /* Slimmer corners to match the smaller size */
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    transition: all 0.2s ease !important;
}}

button[kind="secondary"]:hover {{
    background-color: #f3e8ff !important;
    color: {TB_PURPLE} !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    border-color: {TB_PURPLE} !important;
}}

/* CONNECT EXPANDER AND BUTTON SEAMLESSLY */
div[data-testid="stColumn"]:has(.flush-hook) button[kind="secondary"] {{
    margin-left: -1rem !important; /* Pulls the button left to bridge the Streamlit gap */
    width: calc(100% + 1rem) !important; /* Stretches it to fill the gap */
    border-top-left-radius: 0px !important; /* Squares off the button's left side */
    border-bottom-left-radius: 0px !important;
}}

div[data-testid="stColumn"]:has(.expander-hook) div[data-testid="stExpander"] {{
    border-top-right-radius: 0px !important; /* Squares off the expander's right side */
    border-bottom-right-radius: 0px !important;
}}

/* NESTED SUB-TABS OVERRIDE (Clean Uniform Layout) */
div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"] {{
    background-color: #f8fafc !important; 
    color: #475569 !important; 
    border: 1px solid #cbd5e1 !important;
}}
div[data-testid="stTabs"] div[data-testid="stTabs"] [aria-selected="true"] {{
    background-color: #ffffff !important;
    color: #000000 !important;
    border: 2px solid #633094 !important;
}}
/* CARDS & INPUTS */
div[data-testid="stExpander"],
div[data-testid="stExpander"] > details,
div[data-testid="stExpander"] > details > summary,
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    background-color: #ffffff !important; 
    color: #000000 !important;
}}
div[data-testid="stExpander"] {{ 
    border: 1px solid #cbd5e1 !important; 
    border-radius: 10px !important; 
    box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; /* Softer shadow for tighter packing */
    margin-bottom: 8px !important; /* CRITICAL: Shrinks the gap between cards */
    overflow: hidden; 
}}

/* Tightens the padding inside the clickable title bar */
div[data-testid="stExpander"] details summary {{
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
}}

div[data-testid="stExpander"] details summary p {{ 
    color: #000000 !important; 
    font-weight: 800 !important; 
    font-size: 0.95rem !important; /* Slightly smaller text for a sleeker look */
}}

/* Tightens the padding inside the open card */
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    padding: 1rem !important; 
}}

div[data-baseweb="select"] > div, 
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stDateInput"] input,
    div[data-testid="stTextArea"] textarea {{ 
    background-color: #ffffff !important; color: #000000 !important; border: 1.5px solid #cbd5e1 !important; border-radius: 8px !important;
}}

label, div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 600 !important; }}


div[data-testid="stMetricValue"] > div {{ color: #000000 !important; }}

/* MAP CONTAINER CLEANUP */
    iframe[title="streamlit_folium.st_folium"] {{
        border-radius: 15px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        background-color: transparent !important;
    }}
    
    /* Prevents the 'black box' flicker on refresh */
    .stFolium {{
        background: transparent !important;
    }}
</style>
""", unsafe_allow_html=True)

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

@st.cache_data(ttl=15, show_spinner=False)
def fetch_sent_records_from_sheet():
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets_to_fetch = [
            (DECLINED_ROUTES_GID, "declined"),
            (ACCEPTED_ROUTES_GID, "accepted"),
            (SAVED_ROUTES_GID, "sent")
        ]
        
        sent_dict = {}
        for gid, status_label in sheets_to_fetch:
            try:
                df = pd.read_csv(base_url + gid)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                if 'json payload' in df.columns:
                    for _, row in df.iterrows():
                        try:
                            p = json.loads(row['json payload'])
                            tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                            c_name = str(row.get('contractor', 'Unknown Contractor'))
                            
                            raw_ts = row.get('date created', '')
                            ts_display = ""
                            if pd.notna(raw_ts) and str(raw_ts).strip():
                                try:
                                    ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p')
                                except:
                                    ts_display = str(raw_ts)
                            
                            for tid in tids:
                                tid = tid.strip()
                                if tid:
                                    sent_dict[tid] = {
                                        "name": c_name, 
                                        "status": status_label,
                                        "time": ts_display
                                    }
                        except: continue
            except: continue
        return sent_dict
    except Exception as e:
        st.error(f"Failed to fetch portal records: {e}")
        return {}

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

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try:
        export_url = f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0"
        return pd.read_csv(export_url)
    except: return None

# --- CORE LOGIC ---
def process_pod(pod_name):
    config = POD_CONFIGS[pod_name]
    progress_bar = st.progress(0, text=f"📥 Extracting {pod_name} tasks & evaluating dense routes...")
    try:
        APPROVED_TEAMS = [
            "a - escalation", "b - boosted campaigns", "b - local campaigns", 
            "c - priority nationals", "cvs kiosk removal", "n - national campaigns"
        ]

        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = []
        esc_team_ids = []
        
        if isinstance(teams_res, list):
            for team in teams_res:
                t_name = str(team.get('name', '')).lower().strip()
                if any(appr in t_name for appr in APPROVED_TEAMS):
                    target_team_ids.append(team['id'])
                if 'escalation' in t_name:
                    esc_team_ids.append(team['id'])

        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
            progress_bar.progress(min(len(all_tasks_raw)/500, 0.4))

        unique_tasks_dict = {t['id']: t for t in all_tasks_raw}
        all_tasks = list(unique_tasks_dict.values())

        pool = []
        for t in all_tasks:
            container = t.get('container', {})
            c_type = str(container.get('type', '')).upper()
            
            if c_type == 'TEAM' and container.get('team') not in target_team_ids:
                continue

            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            is_esc = (c_type == 'TEAM' and container.get('team') in esc_team_ids)
            
            if not is_esc:
                for m in (t.get('metadata') or []):
                    if 'escalation' in str(m.get('name', '')).lower() and str(m.get('value', '')).strip() in ['1', '1.0', 'true', 'yes']:
                        is_esc = True
                        break
            
            tt_val = str(t.get('taskType', '')).strip()
            if not tt_val:
                for m in (t.get('metadata') or []):
                    m_name = str(m.get('name', '')).lower().strip()
                    if m_name in ['tasktype', 'task type']:
                        tt_val = str(m.get('value', '')).strip()
                        break
            
            if not tt_val and 'customFields' in t:
                for cf in (t.get('customFields') or []):
                    cf_name = str(cf.get('name', '')).lower().strip()
                    if cf_name in ['tasktype', 'task type']:
                        tt_val = str(cf.get('value', '')).strip()
                        break
                        
            if not tt_val:
                tt_val = str(t.get('taskDetails', '')).strip()
            
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0],
                    "escalated": is_esc, "task_type": tt_val
                })
        
        clusters = []
        total_pool = len(pool)
        
        ic_df = st.session_state.get('ic_df', pd.DataFrame())
        v_ics_base = pd.DataFrame()
        if not ic_df.empty:
            v_ics_base = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()

        while pool:
            prog_val = 0.4 + (0.6 * (1 - (len(pool) / total_pool if total_pool > 0 else 1)))
            progress_bar.progress(min(prog_val, 0.99), text=f"🗺️ Auto-routing {pod_name}... ({len(pool)} tasks remaining)")
            
            anc = pool.pop(0)
            candidates = []
            rem = []
            
            for t in pool:
                d = haversine(anc['lat'], anc['lon'], t['lat'], t['lon'])
                if d <= 50: candidates.append((d, t))
                else: rem.append(t)
            
            candidates.sort(key=lambda x: x[0])
            group = [anc] + [c[1] for c in candidates]
            
            has_ic = False
            closest_ic_loc = f"{anc['lat']},{anc['lon']}" 
            
            if not v_ics_base.empty:
                dists = v_ics_base.apply(lambda x: haversine(anc['lat'], anc['lon'], x['Lat'], x['Lng']), axis=1)
                valid_ics = v_ics_base[dists <= 60].copy()
                if not valid_ics.empty:
                    has_ic = True
                    valid_ics['d'] = dists[dists <= 60]
                    best_ic = valid_ics.sort_values('d').iloc[0]
                    closest_ic_loc = best_ic['Location']

            def check_viability(grp):
                seen = set(); unique_locs = []
                for x in grp:
                    if x['full'] not in seen:
                        seen.add(x['full']); unique_locs.append(x['full'])
                if not unique_locs: return 0, 0
                waypts = unique_locs[:25] 
                
                _, hrs, _ = get_gmaps(closest_ic_loc, waypts)
                pay = round(max(len(unique_locs) * 18.0, hrs * 25.0), 2)
                avg = round(pay / len(unique_locs), 2) if len(unique_locs) > 0 else 0
                return avg, len(unique_locs)
            
            gate_avg, u_count = check_viability(group)
            status = "Ready"
            
            if gate_avg > 23.00 and len(group) > 1:
                removed_stops = []
                passed = False
                for _ in range(min(3, len(group) - 1)):
                    removed_stops.append(group.pop()) 
                    new_avg, _ = check_viability(group)
                    if new_avg <= 23.00:
                        passed = True
                        break
                
                if passed:
                    rem.extend(removed_stops)
                    status = "Ready"
                else:
                    group.extend(removed_stops[::-1])
                    status = "Flagged"
            elif gate_avg > 23.00:
                status = "Flagged"
            
            if not has_ic:
                status = "Flagged"
            
            pool = rem
            clusters.append({
                "data": group, "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in group)), 
                "city": anc['city'], "state": anc['state'],
                "status": status, "has_ic": has_ic,
                "esc_count": sum(1 for x in group if x.get('escalated'))
            })
            
        st.session_state[f"clusters_{pod_name}"] = clusters
        progress_bar.empty()
    except Exception as e:
        progress_bar.empty()
        st.error(f"Error initializing {pod_name}: {str(e)}")

def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"

    # --- 1. STATE KEYS & INITIALIZATION ---
    pay_key = f"pay_val_{cluster_hash}"
    rate_key = f"rate_val_{cluster_hash}"
    sel_key = f"sel_{cluster_hash}"
    last_sel_key = f"last_sel_{cluster_hash}" # Tracks the "previous" selection

    st.write("### 📍 Route Stops")

    # --- NEW: HISTORY LOG ---
    hist = st.session_state.get(f"history_{cluster_hash}", [])
    if hist:
        st.markdown(f"<p style='color: #94a3b8; font-size: 13px; margin-top: -10px; margin-bottom: 15px; font-weight: 600;'>↩️ Previously sent to: {', '.join(hist)}</p>", unsafe_allow_html=True)

    # --- 2. STOP METRICS & PILLS ---
    stop_metrics = {}
    for c in cluster['data']:
        addr = c['full']
        if addr not in stop_metrics:
            stop_metrics[addr] = {'t_count': 0, 'n_ad': 0, 'c_ad': 0, 'd_ad': 0, 'inst': 0, 'remov': 0, 'digi': 0, 'oth': 0}
        stop_metrics[addr]['t_count'] += 1
        tt = str(c.get('task_type', '')).strip().lower()
        if not tt or any(x in tt for x in ["new ad", "digital ad", "art change", "top"]): stop_metrics[addr]['n_ad'] += 1
        elif any(x in tt for x in ["continuity", "photo", "swap"]): stop_metrics[addr]['c_ad'] += 1
        elif any(x in tt for x in ["default", "pull down"]): stop_metrics[addr]['d_ad'] += 1
        elif "install" in tt: stop_metrics[addr]['inst'] += 1
        elif "removal" in tt: stop_metrics[addr]['remov'] += 1
        elif "service" in tt: stop_metrics[addr]['digi'] += 1
        else: stop_metrics[addr]['oth'] += 1

    loc_pills = {} 
    for addr, metrics in stop_metrics.items():
        pill_parts = []
        if metrics['n_ad'] > 0: pill_parts.append(f"🆕 {metrics['n_ad']} New Ad")
        if metrics['c_ad'] > 0: pill_parts.append(f"🔄 {metrics['c_ad']} Continuity")
        if metrics['d_ad'] > 0: pill_parts.append(f"⚪ {metrics['d_ad']} Default")
        if metrics['inst'] > 0: pill_parts.append(f"🛠️ {metrics['inst']} Kiosk Install")
        if metrics['remov'] > 0: pill_parts.append(f"🛑 {metrics['remov']} Kiosk Removal")
        if metrics['digi'] > 0: pill_parts.append(f"📱 {metrics['digi']} Digital Service")
        if metrics['oth'] > 0: pill_parts.append(f"📦 {metrics['oth']} Other")
        pill_str = " | ".join(pill_parts)
        loc_pills[addr] = f"({metrics['t_count']} Tasks) {pill_str}"
        st.markdown(f"**{addr}** &nbsp;<span style='color: #633094; background-color: #f3e8ff; padding: 2px 6px; border-radius: 10px; font-weight: 800; font-size: 11px;'>{metrics['t_count']} Tasks</span>&nbsp; <span style='font-size: 13px; color: #475569;'>— {pill_str}</span>", unsafe_allow_html=True)
        
    st.divider()

    # --- 3. CONTRACTOR FILTERING (100 MILES) ---
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 100].sort_values('d').head(5)

    if v_ics.empty:
        st.error("⚠️ No contractors found within 100 miles.")
        return

    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    
    # --- 3. DYNAMIC PRICING SYNC LOGIC ---
    def sync_on_total():
        # User edited TOTAL COMP
        val = st.session_state[pay_key]
        st.session_state[rate_key] = round(val / cluster['stops'], 2) if cluster['stops'] > 0 else 0

    def sync_on_rate():
        # User edited RATE PER STOP
        val = st.session_state[rate_key]
        st.session_state[pay_key] = round(val * cluster['stops'], 2)

    def update_for_new_contractor():
        # Reset pricing floor when a DIFFERENT contractor is selected
        selected_label = st.session_state[sel_key]
        if selected_label != st.session_state.get(last_sel_key):
            ic_new = ic_opts[selected_label]
            _, h, _ = get_gmaps(ic_new['Location'], list(stop_metrics.keys())[:25])
            new_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
            st.session_state[pay_key] = new_pay
            st.session_state[rate_key] = round(new_pay / cluster['stops'], 2) if cluster['stops'] > 0 else 0
            st.session_state[last_sel_key] = selected_label

    # Initial Setup (First time card is seen)
    if pay_key not in st.session_state:
        first_ic_label = list(ic_opts.keys())[0]
        ic_init = ic_opts[first_ic_label]
        _, h, _ = get_gmaps(ic_init['Location'], list(stop_metrics.keys())[:25])
        initial_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
        st.session_state[pay_key] = initial_pay
        st.session_state[rate_key] = round(initial_pay / cluster['stops'], 2) if cluster['stops'] > 0 else 0
        st.session_state[sel_key] = first_ic_label
        st.session_state[last_sel_key] = first_ic_label

    # --- 5. THE UI ROW ---
    col_a, col_b, col_c, col_d = st.columns([1.5, 1, 1, 1])
    
    with col_a:
        # The callback is attached here to force the background math to run
        st.selectbox("Contractor", list(ic_opts.keys()), key=sel_key, on_change=update_for_new_contractor)
    
    # Get current state values
    ic = ic_opts[st.session_state[sel_key]]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(stop_metrics.keys())[:25])
    
    # LOCK CHECK
    curr_rate = st.session_state[rate_key]
    needs_unlock = (curr_rate >= 25.0) or (ic['d'] > 60) or (cluster['status'] == 'Flagged')
    is_unlocked = True 
    
    if needs_unlock:
        reasons = []
        if curr_rate >= 25.0: reasons.append(f"High Rate (${curr_rate})")
        if ic['d'] > 60: reasons.append(f"Distance ({round(ic['d'],1)}mi)")
        if cluster['status'] == 'Flagged': reasons.append("Flagged Route")
        st.markdown(f"""<div style="background-color:#fef2f2; border:1px solid #ef4444; padding:10px; border-radius:8px; margin-bottom:15px;"><span style="color:#b91c1c; font-weight:800;">🔒 ACTION REQUIRED:</span> <span style="color:#7f1d1d;">{" & ".join(reasons)}</span></div>""", unsafe_allow_html=True)
        is_unlocked = st.checkbox("Authorize Premium Rate / Distance", key=f"lock_{cluster_hash}")

    with col_b:
        st.number_input("Total Comp ($)", min_value=0.0, step=5.0, key=pay_key, on_change=sync_on_total, disabled=not is_unlocked)
    with col_c:
        st.number_input("Rate/Stop ($)", min_value=0.0, step=1.0, key=rate_key, on_change=sync_on_rate, disabled=not is_unlocked)
    with col_d:
        st.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}", disabled=not is_unlocked)

    # --- 6. UPDATED FINANCIALS & PREVIEW ---
    # Fetch final values from session state to ensure they match the UI dynamically
    final_pay = st.session_state[pay_key]
    final_rate = st.session_state[rate_key]

    m1, m2 = st.columns(2)
    with m1: 
        status_color = TB_GREEN if 18.0 <= final_rate <= 23.0 else "#ef4444"
        st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Financials</p><p style='margin:0; font-size:24px; font-weight:800; color:{status_color};'>Total: ${final_pay:,.2f}</p><p style='margin:0; font-size:13px; color:#000000;'>Breakdown: ${final_rate}/stop</p></div>", unsafe_allow_html=True)
    with m2: 
        st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; text-transform:uppercase;'>Logistics</p><p style='margin:0; font-size:24px; font-weight:800; color:#000000;'>{t_str}</p><p style='margin:0; font-size:13px; color:#000000;'>Round Trip: {mi} mi</p></div>", unsafe_allow_html=True)

    # --- DYNAMIC EMAIL PREVIEW ---
    due = st.session_state.get(f"dd_{cluster_hash}", datetime.now().date()+timedelta(14))
    wo_val = f"{ic['Name']} - {datetime.now().strftime('%m%d%Y')}"
    sig_preview = (f"Work Order: {wo_val}\nContractor: {ic['Name']}\nDue Date: {due.strftime('%A, %b %d, %Y')}\n\n"
           f"Metrics:\n- Stops: {cluster['stops']}\n- Mileage: {mi} mi\n- Time: {t_str}\n- Compensation: ${final_pay:.2f}\n\n"
           f"Authorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true")
    
    # This forces Streamlit to wipe the old text and inject the fresh math/dates instantly
    tx_key = f"tx_{cluster_hash}_preview"
    st.session_state[tx_key] = sig_preview 
    
    st.text_area("Email Content Preview", height=180, key=tx_key, disabled=not is_unlocked)

    # --- 7. BUTTON LAYOUT (WITH REVOKE FEATURE) ---
    btn_label = "🚀 GENERATE LINK & OPEN GMAIL" if (not real_id or is_declined) else "🚀 OPEN IN GMAIL (RESEND)"

    # If the route is sitting in the "Sent" tab, split the layout to show the Revoke button
    if is_sent and not is_declined:
        c1, c2 = st.columns([3, 1])
        target_col = c1
        with c2:
            if st.button("↩️ Revoke Route", key=f"rev_{cluster_hash}", use_container_width=True):
                # Log the contractor and time
                hist = st.session_state.get(f"history_{cluster_hash}", [])
                hist.append(f"{cluster.get('contractor_name', 'Unknown')} ({datetime.now().strftime('%m/%d')})")
                st.session_state[f"history_{cluster_hash}"] = hist
                
                # Flag as reverted and destroy the old link
                st.session_state[f"reverted_{cluster_hash}"] = True
                if sync_key in st.session_state:
                    del st.session_state[sync_key]
                st.rerun()
    else:
        target_col = st.container()

    with target_col:
        if st.button(btn_label, type="primary", key=f"gbtn_{cluster_hash}", disabled=not is_unlocked, use_container_width=True):
            final_route_id = real_id
            with st.spinner("Generating secure link..."):
                if not final_route_id or is_declined:
                    home = ic['Location']
                    payload = {
                        "icn": ic['Name'], "ice": ic['Email'], "wo": wo_val, 
                        "due": str(due), "comp": final_pay, "lCnt": cluster['stops'], "mi": mi, "time": t_str, "phone": str(ic['Phone']),
                        "locs": " | ".join([home] + list(stop_metrics.keys()) + [home]),
                        "taskIds": ",".join(task_ids),
                        "tCnt": len(task_ids),
                        "jobOnly": " | ".join([f"{a} {pill}" for a, pill in loc_pills.items()])
                    }
                    res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
                    if res.get("success"):
                        final_route_id = res.get("routeId")
                        st.session_state[sync_key] = final_route_id
                    else:
                        st.error("Failed to generate link."); st.stop()

            # Build final signature with final_route_id
            final_sig = sig_preview.replace("LINK_PENDING", final_route_id)
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su=Route Request: {ic['Name']}&body={requests.utils.quote(final_sig)}"
            
            st.components.v1.html(f"<script>window.open('{gmail_url}', '_blank');</script>", height=0)
            
            # State updates for UI
            now_ts = datetime.now().strftime('%m/%d %I:%M %p')
            st.session_state[f"sent_ts_{cluster_hash}"] = now_ts
            st.session_state[f"contractor_{cluster_hash}"] = ic['Name']
            st.session_state[f"route_state_{cluster_hash}"] = "email_sent"
            st.session_state[f"reverted_{cluster_hash}"] = False # Clear the revert flag since it's sent again
            
            timer_placeholder = st.empty()
            for sec in range(10, 0, -1):
                timer_placeholder.success(f"✅ Link Generated! Moving card in {sec}s...")
                time.sleep(1)
            st.rerun()
            
def run_pod_tab(pod_name):
    # Grab the contractor database from session state
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    
    # ... rest of your header code ...
    
    # Standard Centered Header
    st.markdown(f"<h2 style='text-align:center;'>{pod_name} Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Check if data exists for this pod
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return

    # Load cluster data
    cls = st.session_state[f"clusters_{pod_name}"]

    if not cls:
        st.info(f"No tasks pending in the {pod_name} region.")
        if st.button("🔄 Check Again", key=f"empty_ref_{pod_name}"):
            process_pod(pod_name); st.rerun()
        return

    # --- KEEPING THE CLEAN AUTO-SYNC LOGIC ---
    sent_db = fetch_sent_records_from_sheet()

    ready, review, sent, accepted, declined = [], [], [], [], []

    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        
        sheet_match = sent_db.get(next((tid for tid in task_ids if tid in sent_db), None))
        route_state = st.session_state.get(f"route_state_{cluster_hash}")
        local_ts = st.session_state.get(f"sent_ts_{cluster_hash}", "")
        local_contractor = st.session_state.get(f"contractor_{cluster_hash}", "Unknown")
        
        # Check if the dispatcher manually revoked this route
        is_reverted = st.session_state.get(f"reverted_{cluster_hash}", False)
        
        if sheet_match and not is_reverted:
            c['contractor_name'] = sheet_match.get('name', 'Unknown')
            c['route_ts'] = sheet_match.get('time', '') or local_ts
        else:
            c['contractor_name'] = local_contractor
            c['route_ts'] = local_ts
        
        # If reverted, it completely bypasses the Sent/Accepted/Declined checks
        if route_state == "email_sent" and not is_reverted:
            sent.append(c)
        elif route_state == "link_generated" and not is_reverted:
            orig = st.session_state.get(f"orig_status_{cluster_hash}")
            if orig == "declined":
                declined.append(c)
            else:
                ready.append(c)
        elif sheet_match and not is_reverted:
            raw_status = sheet_match.get('status')
            if raw_status == 'declined':
                declined.append(c)
            elif raw_status == 'accepted':
                accepted.append(c)
            else:
                sent.append(c)
        else:
            # Falls back into standard Dispatching
            if c.get('status') == 'Ready': 
                ready.append(c)
            else: 
                review.append(c)

    total_tasks = sum(len(c['data']) for c in cls)
    total_stops = sum(c['stops'] for c in cls)
    total_routes = len(cls)
    total_dispatched = len(sent) + len(accepted) + len(declined)

    c1, c2, c3 = st.columns([1, 1.5, 1.5])

    with c1:
        st.markdown(f"""
            <div style='background:#f8fafc; border:1px solid #cbd5e1; border-radius:12px; padding:15px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:20px; height: 110px;'>
                <div style='display:flex; justify-content:space-around; text-align:center; height:100%; align-items:center;'>
                    <div>
                        <p style='margin:0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Total Tasks</p>
                        <p style='margin:0; font-size:26px; font-weight:800; color:#000000;'>{total_tasks}</p>
                    </div>
                    <div style='border-left: 2px solid #cbd5e1; height: 40px;'></div>
                    <div>
                        <p style='margin:0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Total Stops</p>
                        <p style='margin:0; font-size:26px; font-weight:800; color:#000000;'>{total_stops}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
            <div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.05); margin-bottom:20px; height: 110px;'>
                <p style='margin:0 0 5px 0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase; text-align:center;'>Total Routes: {total_routes}</p>
                <div style='display:flex; justify-content:space-between; gap:8px;'>
                    <div style='background:{TB_GREEN_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>READY</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(ready)}</p>
                    </div>
                    <div style='background:{TB_BLUE_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>SENT (PENDING)</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(sent)}</p>
                    </div>
                    <div style='background:{TB_RED_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>FLAGGED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(review)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
            <div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:10px; box-shadow:0 2px 4px rgba(0,0,0,0.05); height: 110px;'>
                <p style='margin:0 0 5px 0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase; text-align:center;'>Dispatched Tracking: {total_dispatched}</p>
                <div style='display:flex; justify-content:space-between; gap:8px;'>
                    <div style='background:{TB_GREEN_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>ACCEPTED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(accepted)}</p>
                    </div>
                    <div style='background:{TB_RED_FILL}; flex:1; padding:8px; border-radius:8px; text-align:center;'>
                        <p style='margin:0; font-size:9px; font-weight:800; color:#000000;'>DECLINED</p>
                        <p style='margin:0; font-size:20px; font-weight:800; color:#000000;'>{len(declined)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # --- MAP RENDERING (STAYS RIGHT BELOW) ---
    st.markdown("<br>", unsafe_allow_html=True)
    
    # We use the first cluster as the center point
    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    
    # Draw markers
    for c in ready: folium.CircleMarker(c['center'], radius=8, color=TB_GREEN, fill=True, opacity=0.8).add_to(m)
    for c in sent: folium.CircleMarker(c['center'], radius=8, color="#3b82f6", fill=True, opacity=0.8).add_to(m)
    for c in review: folium.CircleMarker(c['center'], radius=8, color="#ef4444", fill=True, opacity=0.8).add_to(m)
    
    # FIX: Remove width=1100 and use container width for responsiveness
    st_folium(m, height=400, use_container_width=True, key=f"map_{pod_name}")
    
    # --- ICON KEY (LEGEND) ---
    # (Pushed to the far left so Streamlit doesn't turn it into a code block)
    st.markdown("""
<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; background: #ffffff; padding: 12px; border-radius: 12px; border: 1px solid #cbd5e1; margin-top: -10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
    <div style="font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; align-self: center; margin-right: 10px;">Route Key:</div>
    <div style="font-size: 13px; cursor: help;" title="Route is within distance limits (<60mi) and standard rate (<$25/stop).">📍 Ready</div>
    <div style="font-size: 13px; cursor: help;" title="Route is frozen and requires manual authorization before sending.">🔒 Action Required</div>
    <div style="font-size: 13px; cursor: help;" title="The calculated price per stop is $25.00 or higher.">💰 High Rate</div>
    <div style="font-size: 13px; cursor: help;" title="The closest contractor is more than 60 miles away.">📡 Long Distance</div>
    <div style="font-size: 13px; cursor: help;" title="Route was flagged for review (e.g., low density).">🔴 Flagged</div>
    <div style="font-size: 13px; cursor: help;" title="Priority: Contains escalated tasks.">⭐ Escalated</div>
    <div style="font-size: 13px; cursor: help;" title="Route request has been sent to the contractor.">✉️ Sent</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # Create two equal-width columns for side-by-side layout
    col_left, col_right = st.columns(2)

    with col_left:
        # ==========================================
        # SECTION 1: DISPATCH (LEFT SIDE - CENTERED)
        # ==========================================
        st.markdown(f"<div style='font-size: 1.5rem; font-weight: 800; color: {TB_PURPLE}; margin-bottom: 5px; text-align: center;'>🚀 Dispatch</div>", unsafe_allow_html=True)
        t_ready, t_flagged = st.tabs(["📥 Ready", "⚠️ Flagged"])

        with t_ready:
            if not ready: st.info("No tasks ready for dispatch.")
            for i, c in enumerate(ready):
                # --- PRE-CALCULATE BADGES ---
                badges = ""
                if not ic_df.empty:
                    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
                    if not v_ics.empty:
                        v_ics['d'] = v_ics.apply(lambda x: haversine(c['center'][0], c['center'][1], x['Lat'], x['Lng']), axis=1)
                        closest_ic = v_ics.sort_values('d').iloc[0]
                        _, hrs, _ = get_gmaps(closest_ic['Location'], [t['full'] for t in c['data'][:25]])
                        est_pay = max(c['stops'] * 18.0, hrs * 25.0)
                        est_rate = est_pay / c['stops'] if c['stops'] > 0 else 0
                        
                        if est_rate >= 25.0: badges += " 💰"
                        if closest_ic['d'] > 60: badges += " 📡"
                        if est_rate >= 25.0 or closest_ic['d'] > 60: badges = " 🔒" + badges

                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                with st.expander(f"{badges} 📍 {c['city']}, {c['state']} | {c['stops']} Stops{esc_pill}"): 
                    render_dispatch(i, c, pod_name)
                    
        with t_flagged:
            if not review: st.info("No flagged tasks requiring review.")
            for i, c in enumerate(review):
                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                with st.expander(f"🔒 🔴 {c['city']}, {c['state']} | {c['stops']} Stops{esc_pill}"): 
                    render_dispatch(i+1000, c, pod_name)

    with col_right:
        # ==========================================
        # SECTION 2: AWAITING CONFIRMATION (RIGHT SIDE - CENTERED)
        # ==========================================
        st.markdown(f"<div style='font-size: 1.5rem; font-weight: 800; color: {TB_GREEN}; margin-bottom: 5px; text-align: center;'>⏳ Awaiting Confirmation</div>", unsafe_allow_html=True)
        t_sent, t_acc, t_dec = st.tabs(["✉️ Sent (Pending)", "✅ Accepted", "❌ Declined"])

        with t_sent:
            if not sent: st.info("No pending routes sent.")
            for i, c in enumerate(sent):
                ic_name = c.get('contractor_name', 'Unknown')
                ts_label = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
                
                # Re-calculate hash for the quick-revoke button
                task_ids = [str(t['id']).strip() for t in c['data']]
                cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
                
                # 1. Back to [5, 1] for perfect proportions
                exp_col, btn_col = st.columns([5, 1])
                
                with exp_col:
                    # Hidden hook to square off the right side of the expander
                    st.markdown("<div class='expander-hook' style='display:none;'></div>", unsafe_allow_html=True)
                    with st.expander(f"✉️ {ic_name}{ts_label} | {c['city']}, {c['state']}{esc_pill}"): 
                        render_dispatch(i+500, c, pod_name, is_sent=True)
                        
                with btn_col:
                    # Hidden hook to pull the button left and square off its left side
                    st.markdown("<div class='flush-hook' style='display:none;'></div>", unsafe_allow_html=True)
                    if st.button("↩️ Revoke", key=f"quick_rev_{cluster_hash}", help="Pull this route back to Dispatch", use_container_width=True):
                        # Log the previous contractor
                        hist = st.session_state.get(f"history_{cluster_hash}", [])
                        hist.append(f"{ic_name} ({datetime.now().strftime('%m/%d')})")
                        st.session_state[f"history_{cluster_hash}"] = hist
                        
                        # Flag as reverted and destroy the link
                        st.session_state[f"reverted_{cluster_hash}"] = True
                        sync_key = f"sync_{cluster_hash}"
                        if sync_key in st.session_state:
                            del st.session_state[sync_key]
                        st.rerun()
        with t_acc:
            if not accepted: st.info("Waiting for portal acceptances...")
            for i, c in enumerate(accepted):
                ic_name = c.get('contractor_name', 'Unknown')
                ts_label = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                with st.expander(f"✅ {ic_name}{ts_label} | {c['city']}, {c['state']}"):
                    st.success(f"Route accepted. Onfleet assignment should be complete.")
                    render_dispatch(i+2000, c, pod_name, is_sent=True)

        with t_dec:
            if not declined: st.info("No declined routes.")
            for i, c in enumerate(declined):
                ic_name = c.get('contractor_name', 'Unknown')
                ts_label = f" | {c.get('route_ts', '')}" if c.get('route_ts') else ""
                with st.expander(f"❌ {ic_name}{ts_label} | {c['city']}, {c['state']}"):
                    st.error("Route declined. Select a new contractor below to generate a fresh link.")
                    render_dispatch(i+3000, c, pod_name, is_declined=True)
# --- START ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("Database connection failed.")

st.markdown("<h1>Dispatch Command Center</h1>", unsafe_allow_html=True)
tabs = st.tabs(["Global", "Blue", "Green", "Orange", "Purple", "Red"])

with tabs[0]:
    st.markdown("<h2 style='text-align:center;'>Global Control</h2>", unsafe_allow_html=True)
    c_btn = st.columns([1,2,1])[1]
    if c_btn.button("🚀 Initialize All Pods", use_container_width=True):
        st.session_state.sent_db = fetch_sent_records_from_sheet()
        for p in POD_CONFIGS.keys(): process_pod(p)
        st.rerun()

for i, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
    with tabs[i]: run_pod_tab(pod)
