import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import smtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = "33033b2d35d6428c485758c8a67bb7c0"
GOOGLE_MAPS_KEY = "AIzaSyCDYgNIGcfWPxoux2EILXr60ZK0fZYJPR4"
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"

# 📧 EMAIL CONFIGURATION
DISPATCH_EMAIL = "nwilliams@terraboost.biz"
DISPATCH_APP_PASSWORD = "rhmmahivwllfacqi"

# ☁️ GOOGLE SHEETS CONTRACTOR DATABASE
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

# ⚙️ LOGIC SETTINGS
MAX_DEADHEAD_MILES = 60
HOURLY_FLOOR_RATE = 25.00
MAX_RATE_PER_STOP = 22.00

# 🎨 TERRABOOST COLOR SCHEME
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_LIGHT_BLUE = "#e6f0fa"

# 🗺️ MASTER POD CONFIGURATIONS
POD_CONFIGS = {
    "Blue Pod": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"},
                 "color": "blue"},
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

# 🎯 GEO PRICING FIRMLY DEFINED HERE
GEO_PRICING = {
    "CA": 20.00, "WA": 19.50, "OR": 18.00, "HI": 20.00, "AK": 18.50,
    "NV": 16.00, "AZ": 17.50, "ID": 16.00, "NY": 20.00, "NJ": 19.00,
    "CT": 18.00, "MA": 18.00, "IL": 18.00, "FL": 17.50, "TX": 17.00
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Terraboost Tactical Workspace", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

    .stApp {{
        background-color: #f4f5f7 !important;
        color: #323338 !important;
        font-family: 'Roboto', sans-serif !important;
    }}

    h1, h2, h3 {{
        color: {TB_PURPLE} !important;
        font-weight: 700 !important;
    }}

    #status {{ display: none !important; }}
    [data-testid="stStatusWidget"] {{ display: none !important; }}

    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; border-bottom: 1px solid #d0d4e4; }}
    .stTabs [data-baseweb="tab"] {{
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        padding: 10px 16px;
        font-size: 16px;
        font-weight: 500;
        color: #676879;
        font-family: 'Roboto', sans-serif !important;
    }}
    .stTabs [aria-selected="true"] {{
        border-bottom: 3px solid {TB_GREEN};
        color: {TB_PURPLE} !important;
        font-weight: 700;
    }}

    .metric-box {{
        border-left: 5px solid {TB_PURPLE};
        padding: 10px 15px;
        margin-bottom: 15px;
        background: white;
        border-radius: 0 4px 4px 0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .metric-title {{
        font-size: 11px;
        text-transform: uppercase;
        color: #676879;
        font-weight: 600;
        font-family: 'Roboto', sans-serif !important;
    }}
    .metric-value {{
        font-size: 20px;
        color: {TB_PURPLE};
        font-weight: 700;
        font-family: 'Roboto', sans-serif !important;
    }}

    .stButton>button {{
        background-color: {TB_PURPLE} !important;
        color: white !important;
        border: none !important;
        border-radius: 4px;
        width: 100%;
        font-weight: 600;
        padding: 10px;
        opacity: 1 !important;
        font-family: 'Roboto', sans-serif !important;
    }}
    .stButton>button:hover {{
        background-color: {TB_GREEN} !important;
        opacity: 1 !important;
    }}

    div[data-testid="stIFrame"] {{
        resize: vertical !important;
        overflow: auto !important;
        padding-bottom: 20px;
        background: white;
        border-radius: 8px;
        border: 1px solid #d0d4e4;
    }}
    .route-counter {{
        font-size: 18px;
        font-weight: 600;
        color: {TB_PURPLE};
        padding: 5px 0px;
        font-family: 'Roboto', sans-serif !important;
    }}

    div[data-testid="stExpander"] {{
        background-color: white !important;
        border: 1px solid #d0d4e4 !important;
        border-radius: 8px !important;
        margin-bottom: 12px;
        overflow: hidden;
    }}
    div[data-testid="stExpander"] details summary {{
        background-color: {TB_LIGHT_BLUE} !important;
        padding: 12px !important;
        border-radius: 8px 8px 0 0 !important;
    }}
    div[data-testid="stExpander"] details[open] summary {{
        border-bottom: 1px solid #d0d4e4 !important;
    }}
    div[data-testid="stExpander"] details summary p {{
        color: #323338 !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        font-family: 'Roboto', sans-serif !important;
    }}
    div[data-testid="stExpander"] details summary svg {{
        fill: #323338 !important;
        color: #323338 !important;
    }}

    div[data-testid="stProgress"] > div > div {{
        background-color: {TB_LIGHT_BLUE} !important;
    }}
    div[data-testid="stProgress"] > div > div > div {{
        background-color: {TB_GREEN} !important;
    }}

    .stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {{
        background-color: white !important;
        color: #323338 !important;
        border: 1px solid #d0d4e4 !important;
        font-family: 'Roboto', sans-serif !important;
    }}
    div[data-baseweb="select"] > div {{
        background-color: white !important;
        color: #323338 !important;
        font-family: 'Roboto', sans-serif !important;
    }}
    label p {{
        color: #323338 !important;
        font-weight: 600 !important;
        font-family: 'Roboto', sans-serif !important;
    }}
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
    mi, hrs, t_str = 0, 0, "0h 0m"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except:
        pass
    return mi, hrs, t_str


def get_metrics(home, cluster_nodes, stop_rate):
    unique_addrs = list(set([c['full_addr'] for c in cluster_nodes]))
    mi, hrs, t_str = fetch_gmaps_directions(home, tuple(unique_addrs[:10]))

    stop_count = len(unique_addrs)
    pre_pay = max(stop_count * stop_rate, hrs * HOURLY_FLOOR_RATE)
    max_cap = stop_count * MAX_RATE_PER_STOP

    if pre_pay > max_cap:
        pay, p_type = max_cap, f"Capped at ${MAX_RATE_PER_STOP}/Stop"
    else:
        pay, p_type = pre_pay, "Hourly Minimum" if (hrs * HOURLY_FLOOR_RATE) > (
                    stop_count * stop_rate) else "Per Stop Rate"

    h_rate = (pay / hrs) if hrs > 0 else 0
    return round(mi, 1), t_str, round(pay, 2), round(h_rate, 2), p_type


# 🎯 THE FIX: Grabs the exact R-XXXXX ID from Google's response
def sync_to_sheet(ic, cluster_data, mi, time_str, pay, work_order, location_summary, due_date):
    locs_str = " | ".join([f"{addr} ({count} Tasks)" for addr, count in location_summary.items()])
    payload = {
        "icn": str(ic.get('Name', '')), "ice": str(ic.get('Email', '')), "wo": work_order,
        "due": due_date.strftime('%Y-%m-%d'), "comp": f"{pay:.2f}", "mi": str(mi),
        "time": str(time_str), "locs": locs_str, "lCnt": len(location_summary),
        "tCnt": len(cluster_data), "phone": str(ic.get('Phone', '')),
        "taskIds": ",".join([c['id'] for c in cluster_data])
    }
    try:
        res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}, allow_redirects=True)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                return data.get("routeId")  # Google replies with the real ID here!
        return False
    except Exception as e:
        print(f"Sync Error: {e}")
        return False


@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try:
        return pd.read_csv(f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0")
    except:
        return None


# --- CORE PROCESSING LOGIC ---
def process_pod_data(pod_name):
    config = POD_CONFIGS[pod_name]

    ui_container = st.empty()
    with ui_container.container():
        p_bar = st.progress(0, text=f"📡 Synchronizing {pod_name} Tasks from OnFleet...")

        all_tasks = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}"
        while True:
            res = requests.get(url, headers=headers)
            if res.status_code != 200: break
            data = res.json()
            batch = data.get('tasks', [])
            all_tasks.extend(batch)
            if data.get('lastId') and len(batch) > 0:
                url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}&lastId={data['lastId']}"
            else:
                break

        pool = []
        for t in all_tasks:
            a = t.get('destination', {}).get('address', {})
            stt = normalize_state(a.get('state', ''))
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": a.get('city', 'Unknown'), "state": stt,
                    "full_addr": f"{a.get('number', '')} {a.get('street', '')}, {a.get('city', '')}, {stt}",
                    "lat": t.get('destination', {}).get('location', [0, 0])[1],
                    "lon": t.get('destination', {}).get('location', [0, 0])[0]
                })

        p_bar.progress(0.5, text="📦 Assembling Routes...")

        clusters = []
        total = len(pool)
        while pool:
            anchor = pool.pop(0)
            group, unique_locs, rem = [anchor], {anchor['full_addr']}, []
            for t in pool:
                if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 30.0 and (
                        len(unique_locs) < 20 or t['full_addr'] in unique_locs):
                    group.append(t);
                    unique_locs.add(t['full_addr'])
                else:
                    rem.append(t)

            if rem:
                stragglers, new_rem = [], []
                for t in rem:
                    if haversine(anchor['lat'], anchor['lon'], t['lat'], t['lon']) <= 30.0:
                        stragglers.append(t)
                    else:
                        new_rem.append(t)
                if 0 < (len(set([s['full_addr'] for s in stragglers]) | unique_locs) - len(unique_locs)) <= 4:
                    group.extend(stragglers);
                    rem = new_rem;
                    unique_locs |= set([s['full_addr'] for s in stragglers])

            pool = rem
            clusters.append({"data": group, "center": [anchor['lat'], anchor['lon']], "unique_count": len(unique_locs),
                             "acceptable": len(unique_locs) >= 3})

            prog_val = 0.5 + (0.5 * ((total - len(pool)) / max(total, 1)))
            p_bar.progress(prog_val, text=f"📦 {len(clusters)} Routes Assembled...")

        st.session_state[f"clusters_{pod_name}"] = clusters
        p_bar.progress(1.0, text="✅ Route Assembly Complete")
        time.sleep(0.5)

    ui_container.empty()


# --- UI RENDER FUNCTIONS ---
def render_dispatch_logic(i, cluster, pod_name):
    # 🎯 Identify this unique cluster group
    cluster_hash = hashlib.md5("".join(sorted([t['id'] for t in cluster['data']])).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_gas_id = st.session_state.get(sync_key, None)

    # Text placeholder before sync
    link_id = real_gas_id if real_gas_id else "LINK_GENERATED_UPON_SYNC"

    loc_sum = {}
    for c in cluster['data']:
        addr = c['full_addr']
        loc_sum[addr] = loc_sum.get(addr, 0) + 1
    for addr, count in loc_sum.items():
        st.markdown(f"- **{addr}** ({count} Tasks)")
    st.divider()

    ic_df = st.session_state.ic_df
    v_ics = ic_df[
        ~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(), axis=1)].copy()
    v_ics['Lat'] = pd.to_numeric(v_ics['Lat'], errors='coerce');
    v_ics['Lng'] = pd.to_numeric(v_ics['Lng'], errors='coerce')
    v_ics = v_ics.dropna(subset=['Lat', 'Lng'])

    c_lat, c_lon = cluster['center']
    v_ics['d'] = v_ics.apply(lambda x: haversine(c_lat, c_lon, x['Lat'], x['Lng']), axis=1)

    valid_ics = v_ics[v_ics['d'] <= MAX_DEADHEAD_MILES].sort_values('d').head(5)

    if valid_ics.empty:
        st.error(
            f"⚠️ No contractors available within {MAX_DEADHEAD_MILES} miles. This route must be assigned manually.")
        return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}

    cluster_state = cluster['data'][0].get('state', 'Unknown')
    suggested_rate = float(GEO_PRICING.get(cluster_state, 16.0))
    safe_rate = max(16.0, min(22.0, suggested_rate))

    col_ic, col_rate, col_due = st.columns([2, 1, 1])
    sel_label = col_ic.selectbox("Contractor", options=list(ic_opts.keys()), key=f"sel_{i}_{pod_name}")
    rate = col_rate.number_input("Rate/Stop", 16.0, 22.0, safe_rate, 0.5, key=f"rate_{i}_{pod_name}")
    due = col_due.date_input("Due Date", datetime.now().date() + timedelta(days=14), key=f"due_{i}_{pod_name}")

    sel_ic = ic_opts[sel_label]
    mi, t_str, pay, hr_rate, p_type = get_metrics(sel_ic['Location'], cluster['data'], rate)

    # 💰 COMPENSATION DISPLAY
    st.markdown(f"""
        <div style="background-color: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 15px; font-family: 'Roboto', sans-serif !important;">
            <span style="color: #64748b; font-weight: 800; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;">Route Financials</span><br>
            <span style="color: #0f172a; font-weight: 700; font-size: 16px;">Comp: <span style="color: #16a34a;">${pay:.2f}</span></span>
            <span style="color: #cbd5e1; margin: 0 10px;">|</span>
            <span style="color: #0f172a; font-weight: 600;">Drive: {mi} mi</span>
            <span style="color: #cbd5e1; margin: 0 10px;">|</span>
            <span style="color: #0f172a; font-weight: 600;">Est Time: {t_str}</span>
            <div style="font-size: 10px; color: #94a3b8; margin-top: 4px;">{p_type} • Est. ${hr_rate}/hr</div>
        </div>
    """, unsafe_allow_html=True)

    today_str = datetime.now().strftime("%m%d%Y")
    work_order_title = f"{sel_ic['Name']} - {today_str}-{i}"
    loc_lines = [f"{idx + 1}. {a} ({count} Tasks)" for idx, (a, count) in enumerate(loc_sum.items())]

    # ✉️ EMAIL PREVIEW (Always Visible)
    sig = (
        f"Work Order: {work_order_title}\n"
        f"Contractor: {sel_ic['Name']}\n"
        f"Due Date: {due.strftime('%A, %b %d, %Y')}\n\n"
        f"Metrics:\n"
        f"- Unique Stops: {cluster['unique_count']}\n"
        f"- Mileage: {mi} mi\n"
        f"- Time: {t_str}\n"
        f"- Compensation: ${pay:.2f}\n\n"
        f"STOP LOCATIONS:\n" + "\n".join(loc_lines) +
        f"\n\nAuthorize here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true"
    )

    st.text_area("Email Payload Preview", sig, height=250, key=f"area_{i}_{pod_name}_{link_id}")

    c_btn1, c_btn2 = st.columns(2)

    # --- 🔘 BUTTON 1: SYNC ---
    with c_btn1:
        if not real_gas_id:
            if st.button("☁️ Sync Data to Cloud", key=f"sync_btn_{i}_{pod_name}"):
                with st.spinner("Registering route..."):
                    returned_id = sync_to_sheet(sel_ic, cluster['data'], mi, t_str, pay, work_order_title, loc_sum, due)
                    if returned_id:
                        st.session_state[sync_key] = returned_id
                        st.rerun()
                    else: st.error("Sync failed.")
        else:
            st.button("✅ Route Synced", disabled=True, key=f"sync_done_{i}_{pod_name}")

    # --- 🔘 BUTTON 2: EMAIL ---
    with c_btn2:
        if real_gas_id:
            email_subject = f"Action Required: Route Request | {work_order_title}"
            mailto_link = f"https://mail.google.com/mail/?view=cm&fs=1&to={sel_ic['Email']}&su={requests.utils.quote(email_subject)}&body={requests.utils.quote(sig)}"
            st.markdown(f"""
                <a href="{mailto_link}" target="_blank" style="text-decoration: none;">
                    <div style="background-color: #76bc21; color: white; padding: 10px; text-align: center; border-radius: 4px; font-weight: bold; cursor: pointer; border: 1px solid #5e961a; font-family: 'Roboto', sans-serif !important;">
                        📧 Send Gmail to {sel_ic['Name']}
                    </div>
                </a>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background-color: #e2e8f0; color: #94a3b8; padding: 10px; text-align: center; border-radius: 4px; font-weight: bold; cursor: not-allowed; border: 1px solid #cbd5e1; font-family: 'Roboto', sans-serif !important;">
                    📧 Send Email (Sync First)
                </div>
            """, unsafe_allow_html=True)

    if real_gas_id:
        if st.button("Reset Sync", key=f"reset_{i}_{pod_name}"):
            del st.session_state[sync_key]; st.rerun()

def run_pod_tab(pod_name):
    # Apply typography update to the section header
    st.markdown(f"""
        <h2 style="font-family: 'Roboto', sans-serif !important;">{pod_name} Command Center</h2>
    """, unsafe_allow_html=True)

    if f"clusters_{pod_name}" not in st.session_state:
        st.info(f"Data for {pod_name} is currently resting to save bandwidth.")
        if st.button(f"📥 Load {pod_name} Data", key=f"load_{pod_name}"):
            process_pod_data(pod_name)
            st.rerun()
        return

    clusters = st.session_state[f"clusters_{pod_name}"]
    if not clusters:
        st.warning(f"No tasks found for {pod_name}.")
        if st.button("🔄 Refresh Data", key=f"ref_emp_{pod_name}"):
            process_pod_data(pod_name)
            st.rerun()
        return

    ic_df = st.session_state.ic_df
    if ic_df is not None:
        v_ics = ic_df[~ic_df.astype(str).apply(lambda x: x.str.contains('Field Agent', case=False, na=False).any(),
                                               axis=1)].copy()
        v_ics['Lat'] = pd.to_numeric(v_ics['Lat'], errors='coerce')
        v_ics['Lng'] = pd.to_numeric(v_ics['Lng'], errors='coerce')
        v_ics = v_ics.dropna(subset=['Lat', 'Lng'])
    else:
        v_ics = pd.DataFrame()

    acc = []
    unacc = []

    for c in clusters:
        has_ic = False
        if not v_ics.empty:
            c_lat, c_lon = c['center']
            dists = v_ics.apply(lambda x: haversine(c_lat, c_lon, x['Lat'], x['Lng']), axis=1)
            has_ic = (dists <= MAX_DEADHEAD_MILES).any()

        if c['acceptable'] and has_ic:
            acc.append(c)
        else:
            unacc.append(c)

    # Apply typography updates to metric labels
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.markdown(
        f"<div class='metric-box'><div class='metric-title' style='font-family: 'Roboto', sans-serif !important;'>Total Routes</div><div class='metric-value' style='font-family: 'Roboto', sans-serif !important;'>{len(clusters)}</div></div>",
        unsafe_allow_html=True)
    c2.markdown(
        f"<div class='metric-box'><div class='metric-title' style='color:{TB_GREEN}; font-family: 'Roboto', sans-serif !important;'>Ready to Dispatch</div><div class='metric-value' style='font-family: 'Roboto', sans-serif !important;'>{len(acc)}</div></div>",
        unsafe_allow_html=True)
    c3.markdown(
        f"<div class='metric-box'><div class='metric-title' style='color:#f44336; font-family: 'Roboto', sans-serif !important;'>Manual Review</div><div class='metric-value' style='font-family: 'Roboto', sans-serif !important;'>{len(unacc)}</div></div>",
        unsafe_allow_html=True)
    with c4:
        if st.button("🔄 Refresh Data", key=f"refresh_{pod_name}"):
            process_pod_data(pod_name)
            st.rerun()

    m = folium.Map(location=clusters[0]['center'], zoom_start=6, tiles="cartodbpositron")
    if st.session_state.ic_df is not None:
        v_ics = st.session_state.ic_df.dropna(subset=['Lat', 'Lng']).copy()
        for _, ic in v_ics.iterrows():
            if str(ic.get('Pod Color', '')) == pod_name.split(' ')[0] or normalize_state(ic.get('State', '')) in \
                    POD_CONFIGS[pod_name]['states']:
                folium.Marker([ic['Lat'], ic['Lng']],
                              icon=folium.Icon(color="lightgray" if "Field Agent" in str(ic.values) else 'cadetblue',
                                               icon="user", prefix="fa"), opacity=0.35).add_to(m)

    for idx, c in enumerate(clusters):
        folium.CircleMarker(c['center'], radius=12, color=TB_GREEN if c['acceptable'] and has_ic else "#f44336",
                            fill=True, fill_opacity=0.8, tooltip=f"Route {idx + 1}").add_to(m)
    st_folium(m, use_container_width=True, height=600, key=f"map_{pod_name}")

    t1, t2 = st.tabs(["🟢 Ready", "🔴 Review"])
    with t1:
        for i, cluster in enumerate(acc):
            with st.expander(
                    f"📍 {cluster['data'][0]['city']}, {cluster['data'][0]['state']} | {cluster['unique_count']} Unique Stops"):
                render_dispatch_logic(i, cluster, pod_name)
    with t2:
        for i, cluster in enumerate(unacc):
            with st.expander(
                    f"🔴 Review Required | {cluster['data'][0]['city']}, {cluster['data'][0]['state']} | {cluster['unique_count']} Unique Stops"):
                render_dispatch_logic(i + 1000, cluster, pod_name)


def run_global_tab():
    # Apply typography update to the main header
    st.markdown(f"""
        <h1 style="font-family: 'Roboto', sans-serif !important;">Dispatch Command Center</h1>
    """, unsafe_allow_html=True)
    
    if "global_data" not in st.session_state:
        if st.button("🌍 Sync Global Overview Map", key="load_global"):
            ui_container = st.empty()
            with ui_container.container():
                p = st.progress(0, text="Synchronizing Global Intelligence...")
                all_tasks = []
                url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}"
                while True:
                    res = requests.get(url, headers=headers)
                    if res.status_code != 200: break
                    data = res.json();
                    batch = data.get('tasks', [])
                    all_tasks.extend(batch)
                    p.progress(min(len(all_tasks) / 2000, 0.95), text=f"📥 {len(all_tasks)} Global Points Downloaded...")
                    if data.get('lastId') and len(batch) > 0:
                        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time() * 1000) - (80 * 24 * 3600 * 1000)}&lastId={data['lastId']}"
                    else:
                        break

                processed = [{"state": normalize_state(t.get('destination', {}).get('address', {}).get('state', '')),
                              "lat": t.get('destination', {}).get('location', [0, 0])[1],
                              "lon": t.get('destination', {}).get('location', [0, 0])[0]} for t in all_tasks]
                st.session_state.global_data = processed
                ui_container.empty()
                st.rerun()
        return

    all_glob = st.session_state.global_data

    # Apply typography updates to metric labels
    m_cols = st.columns(5)
    for idx, (name, cfg) in enumerate(POD_CONFIGS.items()):
        cnt = len([t for t in all_glob if t['state'] in cfg['states']])
        m_cols[idx].markdown(
            f"<div class='metric-box'><div class='metric-title' style='font-family: 'Roboto', sans-serif !important;'>{name}</div><div class='metric-value' style='font-family: 'Roboto', sans-serif !important;'>{cnt} Tasks</div></div>",
            unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.button("🔄 Refresh Global Map", on_click=lambda: st.session_state.pop("global_data", None))

    m_all = folium.Map(location=[39.82, -98.57], zoom_start=4, tiles="cartodbpositron")
    if st.session_state.ic_df is not None:
        for _, ic in st.session_state.ic_df.dropna(subset=['Lat', 'Lng']).iterrows():
            folium.CircleMarker([ic['Lat'], ic['Lng']], radius=2, color=TB_PURPLE, fill=True, opacity=0.4,
                                tooltip=ic.get('Name')).add_to(m_all)
    for t in all_glob:
        folium.CircleMarker([t['lat'], t['lon']], radius=2, color=TB_GREEN, fill=True, opacity=0.3).add_to(m_all)
    st_folium(m_all, use_container_width=True, height=600, key="master_map")


# --- MAIN APP LAYOUT ---
if "ic_df" not in st.session_state:
    st.session_state.ic_df = load_ic_database(IC_SHEET_URL)

tab_global, tab_blue, tab_green, tab_orange, tab_purple, tab_red = st.tabs(
    ["🌎 Global Overview", "🔵 Blue Pod", "🟢 Green Pod", "🟠 Orange Pod", "🟣 Purple Pod", "🔴 Red Pod"])

with tab_global: run_global_tab()
with tab_blue: run_pod_tab("Blue Pod")
with tab_green: run_pod_tab("Green Pod")
with tab_orange: run_pod_tab("Orange Pod")
with tab_purple: run_pod_tab("Purple Pod")
with tab_red: run_pod_tab("Red Pod")
