import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & REFRESH ---
st.set_page_config(page_title="Furka DEV - Final", layout="wide")

# Aktualisiert die App alle 5 Minuten automatisch
st_autorefresh(interval=5 * 60 * 1000, key="furka_dev_refresh")

# --- 2. DATABASE LOGIK (Speicher: 14 Tage) ---
DB_NAME = 'furka_dev_v4.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, oberwald_min INTEGER, realp_min INTEGER, 
                  raw_ow TEXT, raw_re TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(ow_min, re_min, ow_raw, re_raw):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO stats VALUES (?, ?, ?, ?, ?)", 
              (datetime.now(), ow_min, re_min, ow_raw, re_raw))
    # Alte Daten löschen (älter als 14 Tage)
    c.execute("DELETE FROM stats WHERE timestamp < ?", 
              (datetime.now() - timedelta(days=14),))
    conn.commit()
    conn.close()

def load_data(hours=24):
    conn = sqlite3.connect(DB_NAME)
    cutoff = datetime.now() - timedelta(hours=hours)
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ? ORDER BY timestamp ASC", 
                           conn, params=(cutoff,))
    conn.close()
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# --- 3. RSS LOGIK (Stabil via MGB) ---
def fetch_furka_rss():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    res = {
        "Oberwald": {"min": 0, "raw": "Keine aktuellen Daten"},
        "Realp": {"min": 0, "raw": "Keine aktuellen Daten"},
        "full_xml": ""
    }
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        res["full_xml"] = resp.text
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                title = item.find('title').text or ""
                desc = item.find('description').text or ""
                full = f"{title} {desc}"
                raw_snippet = ET.tostring(item, encoding='unicode')
                
                direction = "Oberwald" if "Oberwald" in full else "Realp" if "Realp" in full else None
                if direction:
                    std = re.search(r'(\d+)\s*Stunde', full)
                    mn  = re.search(r'(\d+)\s*Minute', full)
                    val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
                    res[direction]["min"] = val
                    res[direction]["raw"] = raw_snippet
    except Exception as e:
        st.error(f"RSS Fehler: {e}")
    return res

# --- 4. APP EXECUTION ---
init_db()
data = fetch_furka_rss()

# Nur speichern, wenn der Abruf erfolgreich war (Status 200)
if "full_xml" in data and data["full_xml"]:
    save_to_db(data["Oberwald"]["min"], data["Realp"]["min"], 
               data["Oberwald"]["raw"], data["Realp"]["raw"])

st.title("🏔️ Furka Monitor (Development Branch)")

# Metriken für die aktuelle Situation
col1, col2 = st.columns(2)
with col1:
    st.metric("Oberwald (VS)", f"{data['Oberwald']['min']} Min")
with col2:
    st.metric("Realp (UR)", f"{data['Realp']['min']} Min")

# --- 5. 24h TREND (ALTAIR FIX) ---
df_24h = load_data(hours=24)

if not df_24h.empty:
    st.subheader("📈 Trend letzte 24 Stunden")
    
    # Daten für Altair transformieren
    chart_df = df_24h.rename(columns={"timestamp": "Zeit", "oberwald_min": "Oberwald", "realp_min": "Realp"})
    chart_data = chart_df.melt('Zeit', value_vars=['Oberwald', 'Realp'], 
                               var_name='Station', value_name='Minuten')

    # Chart Definition mit robusten Achsen
    line_chart = alt.Chart(chart_data).mark_line(interpolate='monotone').encode(
        x=alt.X('Zeit:T', 
                title='Uhrzeit (volle Stunden)',
                axis=alt.Axis(format='%H:00', tickCount=12, labelAngle=-45)),
        y=alt.Y('Minuten:Q', title='Wartezeit (min)', scale=alt.Scale(domainMin=0)),
        color=alt.Color('Station:N', scale=alt.Scale(range=['#FF4B4B', '#1C83E1'])),
        tooltip=['Zeit:T', 'Station:N', 'Minuten:Q']
    ).properties(height=400).interactive()

    st.altair_chart(line_chart, use_container_width=True)
else:
    st.info("Sammle erste Daten für den 24h-Trend...")

# --- 6. DEBUG ACCORDION ---
with st.expander("🛠️ Debug Informationen (RSS & Datenbank)"):
    t1, t2 = st.tabs(["Raw RSS", "DB History (24h)"])
    with t1:
        ca, cb = st.columns(2)
        ca.write("**RSS Oberwald:**")
        ca.code(data["Oberwald"]["raw"], language="xml")
        cb.write("**RSS Realp:**")
        cb.code(data["Realp"]["raw"], language="xml")
    with t2:
        st.dataframe(df_24h.sort_values(by="timestamp", ascending=False), use_container_width=True)

st.caption(f"Letzter Abgleich: {datetime.now().strftime('%H:%M:%S')} | Speicherzeitraum: 14 Tage")
