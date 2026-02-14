import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
import altair as alt
import pytz
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Alpen-Verlad PRO (CET)", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# DB v3 für einen komplett sauberen Start in CET
DB_NAME = 'autoverlad_final_v3.db'
CH_TZ = pytz.timezone('Europe/Zurich')

# --- 2. DATABASE LOGIK ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, station TEXT, minuten INTEGER, raw_info TEXT)''')
    conn.commit()
    conn.close()

def save_stats_quantized(data_dict):
    conn = sqlite3.connect(DB_NAME)
    now_ch = datetime.now(pytz.utc).astimezone(CH_TZ)
    
    # 5-Minuten-Raster (z.B. 21:04 -> 21:00)
    rounded_minute = (now_ch.minute // 5) * 5
    ts_rounded = now_ch.replace(minute=rounded_minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    exists = pd.read_sql_query("SELECT 1 FROM stats WHERE timestamp = ? LIMIT 1", conn, params=(ts_rounded,))
    
    if exists.empty:
        for station, info in data_dict.items():
            conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", 
                         (ts_rounded, station, info['min'], info['raw']))
        
        cleanup_limit = (now_ch - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("DELETE FROM stats WHERE timestamp < ?", (cleanup_limit,))
        conn.commit()
        st.toast(f"💾 Slot {ts_rounded[-8:-3]} gespeichert")
    conn.close()

def get_trend_2h(station, current_val):
    conn = sqlite3.connect(DB_NAME)
    two_h_ago = (datetime.now(CH_TZ) - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    # Korrigierte Query-Syntax
    query = "SELECT minuten FROM stats WHERE station = ? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
    df = pd.read_sql_query(query, conn, params=(station, two_h_ago))
    conn.close()
    if df.empty: return None, "➡️"
    diff = current_val - df['minuten'].iloc[0]
    arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
    return diff, arrow

# --- 3. DATEN-ABRUF ---
def fetch_data():
    results = {s: {"min": 0, "raw": "n/a"} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    try:
        # Furka
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            m = re.search(r'(\d+)\s*Minute', full); h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            raw = ET.tostring(item, encoding='unicode')
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": raw}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": raw}
        
        # Lötschberg
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        l_resp.encoding = 'utf-8'
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        txt = soup.get_text()
        for s in ["Kandersteg", "Goppenstein"]:
            match = re.search(rf"{s}.{{0,100}}?(\d+)\s*(Minute|Stunde)", txt, re.I | re.S)
            if match:
                v = int(match.group(1)) * (60 if "stunde" in match.group(2).lower() else 1)
                results[s] = {"min": v, "raw": f"Gefunden: {match.group(0)}"}
    except: pass
    return results

# --- 4. UI FLOW ---
init_db()
current_data = fetch_data()
save_stats_quantized(current_data)

st.title("🏔️ Alpen-Verlad Monitor (CET)")

cols = st.columns(4)
for i, (name, d) in enumerate(current_data.items()):
    diff, arrow = get_trend_2h(name, d['min'])
    delta_val = f"{diff:+} min (2h)" if diff is not None else "Init..."
    cols[i].metric(label=f"{arrow} {name}", value=f"{d['min']} Min", delta=delta_val, delta_color="inverse")

# --- 5. 24h CHART (FIXED) ---
st.subheader("📈 24h Trend")
conn = sqlite3.connect(DB_NAME)
limit_24h = (datetime.now(CH_TZ) - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

# HIER WAR DER FEHLER (KLAMMER ZU):
df_24h = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ? ORDER BY timestamp ASC", conn, params=(limit_24h,))
conn.close()

if not df_24h.empty:
    # Stabiles Datum-Parsing
    df_24h['timestamp'] = pd.to_datetime(df_24h['timestamp'], errors='coerce')
    df_24h = df_24h.dropna(subset=['timestamp'])

    chart = alt.Chart(df_24h).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:00', tickCount=24, title="Uhrzeit (CET)")),
        y=alt.Y('minuten:Q', title="Wartezeit (min)", scale=alt.Scale(domainMin=0)),
        color='station:N',
        tooltip=['timestamp:T', 'station:N', 'minuten:Q']
    ).properties(height=400).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- 6. DEBUG ---
with st.expander("🛠️ Debug Information"):
    t1, t2 = st.tabs(["Raw Data", "DB History"])
    with t1:
        st.write("**Letzte Funde:**")
        st.json(current_data)
    with t2:
        st.write(f"Schweizer Zeit: {datetime.now(CH_TZ).strftime('%H:%M:%S')}")
        st.dataframe(df_24h.sort_values("timestamp", ascending=False), use_container_width=True)
