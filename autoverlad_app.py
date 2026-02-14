import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from bs4 import BeautifulSoup

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpen-Verlad PRO", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Neue DB-Version für sauberen Start ohne Format-Fehler
DB_NAME = 'autoverlad_final_v1.db'

# --- 2. DATABASE LOGIK (Synchronisiert auf 5min) ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, station TEXT, minuten INTEGER, raw_info TEXT)''')
    conn.commit()
    conn.close()

def save_stats_quantized(data_dict):
    conn = sqlite3.connect(DB_NAME)
    now = datetime.now()
    
    # 5-Minuten-Quantisierung (z.B. 21:03 -> 21:00)
    rounded_minute = (now.minute // 5) * 5
    ts_rounded = now.replace(minute=rounded_minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    # Prüfen ob Slot belegt
    exists = pd.read_sql_query("SELECT 1 FROM stats WHERE timestamp = ? LIMIT 1", conn, params=(ts_rounded,))
    
    if exists.empty:
        for station, info in data_dict.items():
            conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", 
                         (ts_rounded, station, info['min'], info['raw']))
        conn.execute("DELETE FROM stats WHERE timestamp < ?", ((now - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
        st.toast(f"💾 Slot {ts_rounded[-8:-3]} gespeichert")
    conn.close()

# --- 3. DATEN-ABRUF & TREND ---
def get_trend_2h(station, current_val):
    conn = sqlite3.connect(DB_NAME)
    two_h_ago = (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    df = pd.read_sql_query("SELECT minuten FROM stats WHERE station = ? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1", 
                           conn, params=(station, two_h_ago))
    conn.close()
    if df.empty: return None, "➡️"
    diff = current_val - df['minuten'].iloc[0]
    return diff, ("⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️")

def fetch_data():
    res = {s: {"min": 0, "raw": "n/a"} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    try:
        # Furka RSS
        f = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=5)
        root = ET.fromstring(f.content)
        for item in root.findall('.//item'):
            txt = f"{item.find('title').text} {item.find('description').text}"
            m = re.search(r'(\d+)\s*Minute', txt)
            h = re.search(r'(\d+)\s*Stunde', txt)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            raw = ET.tostring(item, encoding='unicode')
            if "Oberwald" in txt: res["Oberwald"] = {"min": val, "raw": raw}
            if "Realp" in txt: res["Realp"] = {"min": val, "raw": raw}
        
        # Lötschberg Web
        l = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(l.text, 'html.parser')
        full_txt = soup.get_text()
        for s in ["Kandersteg", "Goppenstein"]:
            match = re.search(rf"{s}.{{0,100}}?(\d+)\s*(Minute|Stunde)", full_txt, re.I | re.S)
            if match:
                v = int(match.group(1)) * (60 if "stunde" in match.group(2).lower() else 1)
                res[s] = {"min": v, "raw": f"Match: {match.group(0)}"}
    except: pass
    return res

# --- 4. APP FLOW ---
init_db()
data = fetch_data()
save_stats_quantized(data)

st.title("🏔️ Alpen-Verlad Live-Monitor")

# Metriken
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    diff, arrow = get_trend_2h(name, d['min'])
    delta_label = f"{diff:+} min (2h)" if diff is not None else "Initialisierung..."
    cols[i].metric(label=f"{arrow} {name}", value=f"{d['min']} Min", delta=delta_label, delta_color="inverse")

# --- 5. 24h CHART ---
st.subheader("📈 24h Trend (Glatte 5-Min-Intervalle)")
conn = sqlite3.connect(DB_NAME)
df_24h = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ?", conn, 
                           params=((datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),))
conn.close()

if not df_24h.empty:
    # Fehlervermeidung: errors='coerce' entfernt ungültige Daten statt abzustürzen
    df_24h['timestamp'] = pd.to_datetime(df_24h['timestamp'], errors='coerce')
    df_24h = df_24h.dropna(subset=['timestamp'])

    chart = alt.Chart(df_24h).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:00', tickCount=24, title="Uhrzeit")),
        y=alt.Y('minuten:Q', title="Wartezeit (Min)"),
        color='station:N',
        tooltip=['timestamp:T', 'station:N', 'minuten:Q']
    ).properties(height=400).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- 6. DEBUG ---
with st.expander("🛠️ Debug View (Raw & DB)"):
    t1, t2 = st.tabs(["Raw Data", "DB Einträge"])
    with t1:
        c1, c2 = st.columns(2)
        c1.write("**Furka (Oberwald/Realp):**")
        c1.code(data["Oberwald"]["raw"] + "\n" + data["Realp"]["raw"], language="xml")
        c2.write("**Lötschberg (Kandersteg/Goppenstein):**")
        c2.code(data["Kandersteg"]["raw"] + "\n" + data["Goppenstein"]["raw"])
    with t2:
        st.dataframe(df_24h.sort_values("timestamp", ascending=False), use_container_width=True)
