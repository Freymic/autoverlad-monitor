import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & REFRESH ---
st.set_page_config(page_title="Furka DEV - 24h Trend", layout="wide")

# Autorefresh alle 5 Minuten
st_autorefresh(interval=5 * 60 * 1000, key="furka_dev_refresh")

# --- 2. DATABASE LOGIK (2 Wochen Speicher) ---
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
    # Speichern
    c.execute("INSERT INTO stats VALUES (?, ?, ?, ?, ?)", 
              (datetime.now(), ow_min, re_min, ow_raw, re_raw))
    # Cleanup: Alles älter als 14 Tage löschen
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

# --- 3. RSS LOGIK ---
def fetch_furka_rss():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    res = {
        "Oberwald": {"min": 0, "raw": "Keine Daten"},
        "Realp": {"min": 0, "raw": "Keine Daten"}
    }
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                title = item.find('title').text
                desc = item.find('description').text
                full = f"{title} {desc}"
                
                # XML Schnipsel für Debug speichern
                raw_xml_snippet = ET.tostring(item, encoding='unicode')
                
                direction = "Oberwald" if "Oberwald" in full else "Realp" if "Realp" in full else None
                if direction:
                    std = re.search(r'(\d+)\s*Stunde', full)
                    mn  = re.search(r'(\d+)\s*Minute', full)
                    val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
                    res[direction]["min"] = val
                    res[direction]["raw"] = raw_xml_snippet
            return res
    except Exception as e:
        st.error(f"Fehler beim Abruf: {e}")
    return res

# --- 4. APP FLOW ---
init_db()
data = fetch_furka_rss()

# Speichern der neuen Daten
save_to_db(data["Oberwald"]["min"], data["Realp"]["min"], 
           data["Oberwald"]["raw"], data["Realp"]["raw"])

st.title("🏔️ Furka Monitor (Development Branch)")

# Metriken
c1, c2 = st.columns(2)
c1.metric("Oberwald", f"{data['Oberwald']['min']} Min")
c2.metric("Realp", f"{data['Realp']['min']} Min")

# --- 5. 24h TREND DIAGRAMM ---
df_24h = load_data(hours=24)

if not df_24h.empty:
    st.subheader("📈 Trend letzte 24 Stunden")
    
    # Daten für Altair vorbereiten (von Breit- in Langformat umwandeln)
    chart_df = df_24h.rename(columns={
        "timestamp": "Zeit", 
        "oberwald_min": "Oberwald", 
        "realp_min": "Realp"
    })
    
    # Umwandlung für Altair (Tidy Data)
    chart_data = chart_df.melt('Zeit', value_vars=['Oberwald', 'Realp'], 
                               var_name='Station', value_name='Wartezeit (min)')

    # Erstellung des Altair Charts
    chart = alt.Chart(chart_data).mark_line(interpolate='monotone').encode(
        x=alt.X('Zeit:T', 
                title='Uhrzeit',
                axis=alt.Axis(
                    format='%H:00',        # Zeigt nur Stunde:00
                    tickCount='hour',      # Setzt Ticks auf jede Stunde
                    labelOverlap='hide',   # Versteckt überlappende Labels
                    grid=True
                )),
        y=alt.Y('Wartezeit (min):Q', title='Minuten'),
        color=alt.Color('Station:N', scale=alt.Scale(range=['#FF4B4B', '#1C83E1'])), # Rot für OW, Blau für RE
        tooltip=['Zeit:T', 'Station:N', 'Wartezeit (min):Q']
    ).properties(height=400).interactive()

    st.altair_chart(chart, use_container_width=True)

# --- 6. DEBUG ACCORDION ---
with st.expander("🛠️ Debug Informationen (RSS & Datenbank)"):
    tab1, tab2 = st.tabs(["Raw RSS Updates", "Datenbank (letzte 24h)"])
    
    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Letztes RSS Oberwald:**")
            st.code(data["Oberwald"]["raw"], language="xml")
        with col_b:
            st.write("**Letztes RSS Realp:**")
            st.code(data["Realp"]["raw"], language="xml")
            
    with tab2:
        st.write("**Einträge der letzten 24h (Rohdaten):**")
        st.dataframe(df_24h.sort_values(by="timestamp", ascending=False), use_container_width=True)

st.caption(f"Letzter Check: {datetime.now().strftime('%H:%M:%S')} | Speicher: 14 Tage")
