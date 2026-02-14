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
# Automatischer Refresh alle 5 Minuten
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Datenbankname (v2 wegen Zeitzonenumstellung auf CET)
DB_NAME = 'autoverlad_final_v2.db'
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
    # Aktuelle Zeit in Schweizer Lokalzeit
    now_ch = datetime.now(pytz.utc).astimezone(CH_TZ)
    
    # Auf das letzte 5-Minuten-Intervall abrunden (z.B. 21:03 -> 21:00)
    rounded_minute = (now_ch.minute // 5) * 5
    ts_rounded = now_ch.replace(minute=rounded_minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    
    # Prüfen ob Slot bereits existiert
    exists = pd.read_sql_query("SELECT 1 FROM stats WHERE timestamp = ? LIMIT 1", conn, params=(ts_rounded,))
    
    if exists.empty:
        for station, info in data_dict.items():
            conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", 
                         (ts_rounded, station, info['min'], info['raw']))
        
        # Cleanup: Alles älter als 14 Tage löschen
        cleanup_limit = (now_ch - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("DELETE FROM stats WHERE timestamp < ?", (cleanup_limit,))
        conn.commit()
        st.toast(f"💾 Slot {ts_rounded[-8:-3]} (CET) gespeichert")
    conn.close()

def get_trend_2h(station, current_val):
    """Vergleichswert von vor ca. 2 Stunden aus der DB holen."""
    conn = sqlite3.connect(DB_NAME)
    two_h_ago = (datetime.now(CH_TZ) - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    query = "SELECT minuten FROM stats WHERE station = ? AND timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
    df = pd.read_sql_query(query, conn, params=(station, two_h_ago))
    conn.close()
    if df.empty: return None, "➡️"
    diff = current_val - df['minuten'].iloc[0]
    arrow = "⬆️" if diff > 0 else "⬇️" if diff < 0 else "➡️"
    return diff, arrow

# --- 3. DATEN-ABRUF (FURKA & LÖTSCHBERG) ---
def fetch_data():
    results = {s: {"min": 0, "raw": "n/a"} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    
    # --- FURKA RSS ---
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full = f"{title} {desc}"
            
            m = re.search(r'(\d+)\s*Minute', full)
            h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            raw = ET.tostring(item, encoding='unicode')
            
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": raw}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": raw}
    except Exception as e: st.error(f"Furka Fehler: {e}")

    # --- LÖTSCHBERG WEB ---
    try:
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        l_resp.encoding = 'utf-8'
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        full_txt = soup.get_text()
        for s in ["Kandersteg", "Goppenstein"]:
            match = re.search(rf"{s}.{{0,100}}?(\d+)\s*(Minute|Stunde)", full_txt, re.I | re.S)
            if match:
                v = int(match.group(1)) * (60 if "stunde" in match.group(2).lower() else 1)
                results[s] = {"min": v, "raw": f"Gefunden: {match.group(0)}"}
    except Exception as e: st.error(f"Lötschberg Fehler: {e}")
    
    return results

# --- 4. MAIN UI FLOW ---
init_db()
data = fetch_data()
save_stats_quantized(data)

st.title("🏔️ Alpen-Verlad Live-Monitor (CET)")

# Metriken in 4 Spalten
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    diff, arrow = get_trend_2h(name, d['min'])
    delta_label = f"{diff:+} min (2h)" if diff is not None else "Initialisierung..."
    with cols[i]:
        st.metric(label=f"{arrow} {name}", value=f"{d['min']} Min", delta=delta_label, delta_color="inverse")

# --- 5. 24h TREND CHART ---
st.subheader("📈 24h Trend (Stündliche Übersicht)")
conn = sqlite3.connect(DB_NAME)
# Abfrage der letzten 24h in Schweizer Zeit
limit_24h = (datetime.now(CH_TZ) - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
df_24h = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ? ORDER BY timestamp ASC", conn, params=(limit_24
