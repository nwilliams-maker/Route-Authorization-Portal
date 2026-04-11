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

st.set_page_config(page_title="Tactical Command", layout="wide")

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

    /* NESTED SUB-TABS OVERRIDE (Ready = Green, Sent = Blue, Flagged = Red) */
    div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(1) {{ background-color: {TB_GREEN_FILL} !important; color: #000000 !important; }}
    div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(2) {{ background-color: {TB_BLUE_FILL} !important; color: #000000 !important; }}
    div[data-testid="stTabs"] div[data-testid="stTabs"] [data-baseweb="tab"]:nth-of-type(3) {{ background-color: {TB_RED_FILL} !important; color: #000000 !important; }}

    /* FORCE EXPANDER CARDS PURE WHITE */
    div[data-testid="stExpander"],
    div[data-testid="stExpander"] > details,
    div[data-testid="stExpander"] > details > summary,
    div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
        background-color: #ffffff !important; 
        color: #000000 !important;
    }}
    div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1 !important; border-radius: 15px !important; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; }}
    div[data-testid="stExpander"] details summary p {{ color: #000000 !important; font-weight: 800 !important; }}
    div[data-testid="stExpander"] svg {{ fill: #000000 !important; color: #000000 !important; }}
    
    /* FORCE TEXT AREA AND INPUTS PURE WHITE WITH BLACK TEXT */
    div[data-baseweb="select"] > div, 
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stDateInput"] input,
    div[data-testid="stTextArea"] textarea {{ 
        background-color: #ffffff !important; 
        color: #000000 !important; 
        border: 1.5px solid #cbd5e1 !important; 
        border-radius: 8px !important;
    }}

    /* FORCE LABELS TO BLACK */
    label, div[data-testid="stWidgetLabel"] p {{
        color: #000000 !important;
        font-weight: 600 !important;
    }}
    
    /* Hover Fix for Inputs and Dropdowns */
    div[data-baseweb="select"] > div:hover, 
    div[data-testid="stNumberInput"] input:hover, 
    div[data-testid="stDateInput"] input:hover,
    div[data-testid="stTextArea"] textarea:hover,
    li[role="option"]:hover,
    ul[role="listbox"] li:hover {{
        background-color: {TB_HOVER_GRAY} !important;
        color: #000000 !important;
    }}
    
    /* Terraboost Action Buttons (Purple) */
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #ffffff !important; font-weight: 800 !important; border-radius: 12px !important; width: 100%; border: none !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: all 0.2s ease; }}
    .stButton>button:hover {{ filter: brightness(1.1); transform: translateY(-2px); box-shadow: 0 6px 10px rgba(0,0,0,0.15); color: #ffffff !important; }}
    
    /* Gmail Green Buttons */
    .gmail-btn {{ text-align: center; background-color: {TB_GREEN} !important; color: #ffffff !important; padding: 12px; border-radius: 12px; font-weight: 800; display: block; text-decoration: none; border: none !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: all 0.2s ease; }}
    .gmail-btn:hover {{ filter: brightness(1.05); transform: translateY(-2px); box-shadow: 0 6px 10px rgba(0,0,0,0.15); color: #ffffff !important; }}
    
    div[data-testid="stMetricValue"] > div {{ color: #000000 !important; }}
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

def fetch_sent_records_from_sheet():
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid={SAVED_ROUTES_GID}"
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        sent_dict = {}
        if 'json payload' in df.columns:
            for payload_str in df['json payload'].dropna():
                try:
                    p = json.loads(payload_str)
                    tids = p.get('taskIds', '')
                    contractor_name = p.get('icn', 'Unknown Contractor')
                    if tids:
                        for tid in str(tids).replace('|', ',').split(','):
                            if tid.strip():
                                sent_dict[tid.strip()] = contractor_name
                except: continue
        
        if 'taskids' in df.columns and not sent_dict:
            for idx, row in df.iterrows():
                tids = str(row.get('taskids', '')).replace('|', ',').split(',')
                c_name = row.get('contractor', row.get('icn', 'Unknown Contractor'))
                for tid in tids:
                    if tid.strip() and tid.strip() not in sent_dict:
                        sent_dict[tid.strip()] = c_name
                        
        return sent_dict
    except Exception as e:
        st.error(f"Failed to fetch sent routes. Google Sheets Error: {e}")
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
        all_tasks = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
            progress_bar.progress(min(len(all_tasks)/500, 0.4))

        pool = []
        for t in all_tasks:
            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            
           # ---> CRITICAL FIX: Make the value check flexible for Onfleet decimals/numbers <---
            is_esc = any(
                "escalation" in str(m.get('name', '')).lower() and 
                str(m.get('value', '')).strip().lower() in ["1", "1.0", "true", "yes"] 
                for m in t.get('metadata', [])
            )
            
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0],
                    "escalated": is_esc
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
                "data": group, 
                "center": [anc['lat'], anc['lon']], 
                "stops": len(set(x['full'] for x in group)), 
                "city": anc['city'], "state": anc['state'],
                "status": status,
                "has_ic": has_ic,
                "esc_count": sum(1 for x in group if x.get('escalated'))
            })
            
        st.session_state[f"clusters_{pod_name}"] = clusters
        progress_bar.empty()
    except Exception as e:
        progress_bar.empty()
        st.error(f"Error initializing {pod_name}: {str(e)}")

def render_dispatch(cluster, pod_name, is_sent=False):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"
    
    st.write("### 📍 Route Stops")
    loc_sum = {}
    for c in cluster['data']: loc_sum[c['full']] = loc_sum.get(c['full'], 0) + 1
    for addr, count in loc_sum.items(): st.markdown(f"**{addr}** ({count} Tasks)")
    st.divider()

    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].dropna(subset=['Lat', 'Lng']).copy()
    
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 60].sort_values('d').head(5)

    if v_ics.empty:
        st.error("⚠️ No contractors found within 60 miles. Manual recruiting or assignment required.")
        return

    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    col_a, col_b, col_c = st.columns([2,1,1])
    
    default_idx = 0
    if is_sent and 'contractor_name' in cluster:
        for idx, key in enumerate(ic_opts.keys()):
            if cluster['contractor_name'].lower() in key.lower():
                default_idx = idx
                break

    sel_label = col_a.selectbox("Contractor", list(ic_opts.keys()), index=default_idx, key=f"sel_{cluster_hash}")
    rate = col_b.number_input("Rate/Stop", 16.0, 150.0, 18.0, step=1.0, key=f"rt_{cluster_hash}")
    due = col_c.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}")

    ic = ic_opts[sel_label]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(loc_sum.keys())[:25])
    pay = round(max(cluster['stops'] * rate, hrs * 25.0), 2)
    eff_stop = round(pay / cluster['stops'], 2) if cluster['stops'] > 0 else 0

    m1, m2 = st.columns(2)
    with m1: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Financials</p><p style='margin:0; font-size:24px; font-weight:800; color:{TB_GREEN if eff_stop <= 23.00 else '#ef4444'};'>Total: ${pay:,.2f}</p><p style='margin:0; font-size:13px; color:#000000;'>Effective: ${eff_stop}/stop</p></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px; margin-bottom:10px;'><p style='font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>Logistics</p><p style='margin:0; font-size:24px; font-weight:800; color:#000000;'>{t_str}</p><p style='margin:0; font-size:13px; color:#000000;'>Round Trip: {mi} mi</p></div>", unsafe_allow_html=True)

    # UNIFIED WORK ORDER NUMBER (Name - Date)
    wo_val = f"{ic['Name']} - {datetime.now().strftime('%m%d%Y')}"

    sig = (f"Work Order: {wo_val}\nContractor: {ic['Name']}\nDue Date: {due.strftime('%A, %b %d, %Y')}\n\n"
           f"Metrics:\n- Stops: {cluster['stops']}\n- Mileage: {mi} mi\n- Time: {t_str}\n- Compensation: ${pay:.2f}\n\n"
           f"Authorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true")
    
    # REACTIVE TEXT AREA: Key is dynamically tied to the contractor, pay, and due date so it auto-refreshes
    st.text_area("Email Content Preview", sig, height=180, key=f"tx_{cluster_hash}_{ic['Name']}_{pay}_{due}")

    col1, col2 = st.columns(2)
    with col1:
        if not real_id:
            if st.button("☁️ Push & Generate Link", key=f"btn_s_{cluster_hash}"):
                home = ic['Location']
                payload = {
                    "icn": ic['Name'], "ice": ic['Email'], "wo": wo_val, 
                    "due": str(due), "comp": pay, "lCnt": cluster['stops'], "mi": mi, "time": t_str, "phone": str(ic['Phone']),
                    "locs": " | ".join([home] + list(loc_sum.keys()) + [home]),
                    "taskIds": ",".join(task_ids),
                    "tCnt": len(task_ids),
                    "jobOnly": " | ".join([f"{a} ({c} Tasks)" for a,c in loc_sum.items()])
                }
                res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
                if res.get("success"):
                    st.session_state[sync_key] = res.get("routeId")
                    st.rerun()
        else: st.button("✅ Link Generated", disabled=True, key=f"dis_{cluster_hash}")
    
    with col2:
        if real_id:
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su=Route Request: {ic['Name']}&body={requests.utils.quote(sig)}"
            st.markdown(f'<a href="{gmail_url}" target="_blank" class="gmail-btn">🚀 OPEN IN GMAIL</a>', unsafe_allow_html=True)

def run_pod_tab(pod_name):
    st.markdown(f"<h2 style='text-align:center;'>{pod_name} Dashboard</h2>", unsafe_allow_html=True)
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return
    
    cls = st.session_state[f"clusters_{pod_name}"]
    if not cls:
        st.info(f"No tasks pending in the {pod_name} region.")
        if st.button("🔄 Check Again", key=f"empty_ref_{pod_name}"):
            process_pod(pod_name); st.rerun()
        return
    
    sent_db = st.session_state.get("sent_db", {})
    ready, review, sent = [], [], []
    
    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        matched_contractors = [sent_db[tid] for tid in task_ids if tid in sent_db]
        
        if matched_contractors:
            c['contractor_name'] = matched_contractors[0]
            sent.append(c)
        else:
            if c.get('status') == "Ready": ready.append(c)
            else: review.append(c)
    
    c1, c2, c3, c4 = st.columns([1,1,1, 1.2])
    for col, title, val in zip([c1, c2, c3], ["Ready", "Sent", "Flagged"], [len(ready), len(sent), len(review)]):
        
        if title == "Ready": bg_color = TB_GREEN_FILL
        elif title == "Sent": bg_color = TB_BLUE_FILL
        else: bg_color = TB_RED_FILL
        
        col.markdown(f"""
            <div style='background:{bg_color}; border:1px solid #cbd5e1; border-radius:12px; padding:15px; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <p style='margin:0; font-size:11px; font-weight:800; color:#000000; text-transform:uppercase;'>{title}</p>
                <p style='margin:0; font-size:26px; font-weight:800; color:#000000;'>{val}</p>
            </div>
        """, unsafe_allow_html=True)
    
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Sync Sent Routes", use_container_width=True, key=f"sync_sheet_{pod_name}"):
            bar = st.progress(0, text="🔄 Fetching database records...")
            st.session_state.sent_db = fetch_sent_records_from_sheet()
            bar.progress(100, text="✅ Database Synced!")
            time.sleep(0.5)
            bar.empty()
            st.rerun()

    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=10, color=TB_GREEN, fill=True, opacity=0.8).add_to(m)
    for c in sent: folium.CircleMarker(c['center'], radius=10, color="#3b82f6", fill=True, opacity=0.8).add_to(m)
    for c in review: folium.CircleMarker(c['center'], radius=10, color="#ef4444", fill=True, opacity=0.8).add_to(m)
    st_folium(m, width=1100, height=400, key=f"map_{pod_name}")
    
    t_ready, t_out, t_rev = st.tabs(["Dispatch Ready", "Sent", "Flagged"])
    with t_ready:
        for c in ready:
            esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
            with st.expander(f"📍 {c['city']}, {c['state']} | {c['stops']} Stops{esc_pill}"): render_dispatch(c, pod_name)
    with t_out:
        for c in sent:
            ic_name = c.get('contractor_name', 'Unknown')
            esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
            with st.expander(f"✓ {ic_name} | {c['city']}, {c['state']} | {c['stops']} Stops{esc_pill}"): render_dispatch(c, pod_name, is_sent=True)
    with t_rev:
        for c in review:
            status_emoji = "🔴" if not c.get('has_ic') else "⚠" 
            esc_pill = f"  [ ⭐ {c.get('esc_count', 0)} ]" if c.get('esc_count', 0) > 0 else ""
            with st.expander(f"{status_emoji} {c['city']}, {c['state']} | {c['stops']} Stops{esc_pill}"): render_dispatch(c, pod_name)

# --- START ---
if "ic_df" not in st.session_state:
    try:
        url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0"
        st.session_state.ic_df = pd.read_csv(url)
    except: st.error("Database connection failed.")

st.markdown("<h1>Terraboost Tactical Command</h1>", unsafe_allow_html=True)
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
