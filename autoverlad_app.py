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

# --- 1. CONFIG & REFRESH ---
st.set_page_config(page_title="Alpen-Verlad Monitor DEV", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

DB_NAME = 'autoverlad_v6.db'

# --- 2. DATABASE LOGIK ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, station TEXT, minuten INTEGER, raw_info TEXT)''')
    conn.commit()
    conn.close()

def save_stats(data_dict):
    conn = sqlite3.connect(DB_NAME)
    now = datetime.now()
    # Letzten Zeitstempel prüfen, um 5-Min-Takt zu erzwingen
    last_entry = pd.read_sql_query("SELECT timestamp FROM stats ORDER BY timestamp DESC LIMIT 1", conn)
    if not last_entry.empty:
        last_time = pd.to_datetime(last_entry['timestamp'].iloc[0])
        if now < last_time + timedelta(minutes=4.5):
            conn.close()
            return

    for station, info in data_dict.items():
        conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", 
                     (now, station, info['min'], info['raw']))
    
    conn.execute("DELETE FROM stats WHERE timestamp < ?", (now - timedelta(days=14),))
    conn.commit()
    conn.close()

def get_trend(station, current_val):
    conn = sqlite3.connect(DB_NAME)
    two_hours_ago = datetime.now() - timedelta(hours=2)
    query = "SELECT minuten FROM stats WHERE station = ? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
    old_df = pd.read_sql_query(query, conn, params=(station, two_hours_ago))
    conn.close()
    
    if old_df.empty: return None, "➡️"
    old_val = old_df['minuten'].iloc[0]
    diff = current_val - old_val
    arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
    return diff, arrow

# --- 3. DATEN-ABRUF ---
def fetch_all_data():
    results = {
        "Oberwald": {"min": 0, "raw": ""},
        "Realp": {"min": 0, "raw": ""},
        "Kandersteg": {"min": 0, "raw": ""},
        "Goppenstein": {"min": 0, "raw": ""}
    }
    
    # --- FURKA (RSS) ---
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text
            desc = item.find('description').text
            full = f"{title} {desc}"
            raw_xml = ET.tostring(item, encoding='unicode')
            
            std = re.search(r'(\d+)\s*Stunde', full)
            mn = re.search(r'(\d+)\s*Minute', full)
            val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
            
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": raw_xml}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": raw_xml}
    except Exception as e: st.warning(f"Furka RSS Fehler: {e}")

    # --- LÖTSCHBERG (Web) ---
    try:
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        # Wir speichern einen Teil des HTMLs für das Debugging
        main_content = str(soup.find('main'))[:1000] 
        
        for st_name in ["Kandersteg", "Goppenstein"]:
            # Suche nach Wartezeit im Text
            match = re.search(rf"{st_name}.*?(\d+)\s*Minute", soup.get_text(), re.IGNORECASE)
            val = int(match.group(1)) if match else 0
            results[st_name] = {"min": val, "raw": f"Gefundenes Pattern für {st_name}: {val} Min. | HTML Snippet: {main_content}"}
    except Exception as e: st.warning(f"Lötschberg Fehler: {e}")
    
    return results

# --- 4. UI & FLOW ---
init_db()
all_data = fetch_all_data()
save_stats(all_data)

st.title("🏔️ Alpen-Autoverlad Live-Monitor")

# Darstellung Metriken
cols = st.columns(4)
for i, (name, d) in enumerate(all_data.items()):
    diff, arrow = get_trend(name, d['min'])
    delta_str = f"{diff} min (2h)" if diff is not None else "Initialisierung..."
    with cols[i]:
        st.metric(label=f"{arrow} {name}", value=f"{d['min']} Min", delta=delta_str, delta_color="inverse")

# --- 5. TREND DIAGRAMM ---
st.subheader("📈 24h Trend (Alle Stationen)")
conn = sqlite3.connect(DB_NAME)
df_24h = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ?", conn, params=(datetime.now() - timedelta(hours=24),))
conn.close()

if not df_24h.empty:
    df_24h['timestamp'] = pd.to_datetime(df_24h['timestamp'])
    chart = alt.Chart(df_24h).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:00', title='Uhrzeit', tickCount=12)),
        y=alt.Y('minuten:Q', title='Minuten'),
        color=alt.Color('station:N', title='Station'),
        tooltip=['timestamp:T', 'station:N', 'minuten:Q']
    ).properties(height=400).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- 6. DEBUG ACCORDION ---
with st.expander("🛠️ Debug Informationen (Raw Data & DB History)"):
    tab1, tab2 = st.tabs(["Station Raw Info", "Datenbank Einträge (24h)"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Oberwald Raw:**")
            st.code(all_data["Oberwald"]["raw"], language="xml")
            st.write("**Kandersteg Raw:**")
            st.code(all_data["Kandersteg"]["raw"], language="html")
        with c2:
            st.write("**Realp Raw:**")
            st.code(all_data["Realp"]["raw"], language="xml")
            st.write("**Goppenstein Raw:**")
            st.code(all_data["Goppenstein"]["raw"], language="html")
            
    with tab2:
        st.write("**Letzte DB-Einträge (nach Zeit sortiert):**")
        if not df_24h.empty:
            st.dataframe(df_24h.sort_values(by="timestamp", ascending=False), use_container_width=True)

st.caption(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')} | Trend-Basis: 2 Stunden")
