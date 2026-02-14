import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- 1. KONFIGURATION & AUTO-REFRESH ---
st.set_page_config(page_title="Furka Live-Check Pro", layout="wide")

# Aktualisiert die gesamte App alle 5 Minuten automatisch
st_autorefresh(interval=5 * 60 * 1000, key="furka_auto_update")

# --- 2. DATENBANK LOGIK (Persistenz für Trend) ---
def init_db():
    conn = sqlite3.connect('furka_v3.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, oberwald INTEGER, realp INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def update_database(ow_min, re_min, raw_msg):
    conn = sqlite3.connect('furka_v3.db')
    c = conn.cursor()
    c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", (datetime.now(), ow_min, re_min, raw_msg))
    # Daten älter als 24h löschen, um DB klein zu halten
    c.execute("DELETE FROM stats WHERE timestamp < ?", (datetime.now() - timedelta(hours=24),))
    conn.commit()
    conn.close()

def get_history_df(hours=6):
    conn = sqlite3.connect('furka_v3.db')
    cutoff = datetime.now() - timedelta(hours=hours)
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ? ORDER BY timestamp ASC", 
                           conn, params=(cutoff,))
    conn.close()
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# --- 3. DATENABFRAGE (RSS statt Scraping) ---
def fetch_mgb_rss():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    try:
        # User-Agent imitieren, um Blockaden vorzubeugen
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            items = root.findall('.//item')
            res = {"Oberwald": 0, "Realp": 0, "msg": "Keine besonderen Vorkommnisse"}
            
            for item in items:
                title = item.find('title').text
                desc = item.find('description').text
                full = f"{title} {desc}"
                
                # Richtung bestimmen
                direction = "Oberwald" if "Oberwald" in full else "Realp" if "Realp" in full else None
                if direction:
                    # Zeit extrahieren (Stunden oder Minuten)
                    std = re.search(r'(\d+)\s*Stunde', full)
                    mn  = re.search(r'(\d+)\s*Minute', full)
                    val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
                    res[direction] = val
                    res["msg"] = title
            return res, resp.text
    except Exception as e:
        st.error(f"RSS Fehler: {e}")
    return None, ""

# --- 4. HAUPT-APP ---
init_db()
st.title("🏔️ Furka Autoverlad: Live-Status & Trend")

# Daten abrufen
current_data, raw_xml = fetch_mgb_rss()

if current_data:
    # In DB speichern für den Trend
    update_database(current_data["Oberwald"], current_data["Realp"], current_data["msg"])
    
    # Metriken anzeigen
    c1, c2 = st.columns(2)
    with c1:
        st.metric("📍 Oberwald", f"{current_data['Oberwald']} min", 
                  delta="Normalbetrieb" if current_data['Oberwald'] == 0 else "Stau")
    with c2:
        st.metric("📍 Realp", f"{current_data['Realp']} min", 
                  delta="Normalbetrieb" if current_data['Realp'] == 0 else "Stau", delta_color="inverse")

# --- 5. TREND-VISUALISIERUNG (6h) ---
df_hist = get_history_df(6)
if not df_hist.empty:
    st.subheader("📈 Wartezeit-Trend (letzte 6 Stunden)")
    # Chart-Daten aufbereiten
    chart_df = df_hist.copy()
    chart_df = chart_df.rename(columns={"timestamp": "Zeit", "oberwald": "Oberwald", "realp": "Realp"})
    st.line_chart(chart_df.set_index("Zeit")[["Oberwald", "Realp"]])

# --- 6. DEBUG & INFO ---
with st.expander("🛠️ Debug-Informationen (RSS & DB)"):
    st.write(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")
    if current_data:
        st.write("**Aktuelle Meldung:**", current_data["msg"])
    if raw_xml:
        st.code(raw_xml, language="xml")
    st.dataframe(df_hist.tail(10))

st.caption("Datenquelle: MGB RSS Incident Manager. Automatisches Update alle 5 Min.")
