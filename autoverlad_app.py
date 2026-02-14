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
# Globaler Refresh alle 5 Minuten
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
    
    # Zeit auf das letzte 5-Minuten-Intervall abrunden (z.B. 14:07 -> 14:05)
    rounded_minute = (now.minute // 5) * 5
    timestamp_rounded = now.replace(minute=rounded_minute, second=0, microsecond=0)
    
    # Prüfen, ob für diesen exakten 5-Min-Slot bereits Daten vorhanden sind
    query = "SELECT 1 FROM stats WHERE timestamp = ? LIMIT 1"
    exists = pd.read_sql_query(query, conn, params=(timestamp_rounded,))
    
    if exists.empty:
        for station, info in data_dict.items():
            conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", 
                         (timestamp_rounded, station, info['min'], info['raw']))
        
        # Cleanup: Alles älter als 14 Tage löschen
        conn.execute("DELETE FROM stats WHERE timestamp < ?", (now - timedelta(days=14),))
        conn.commit()
        st.toast(f"Datenpunkt für {timestamp_rounded.strftime('%H:%M')} gespeichert")
    
    conn.close()

def get_trend(station, current_val):
    """Vergleicht aktuellen Wert mit dem Wert von vor ca. 2 Stunden."""
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
        "Oberwald": {"min": 0, "raw": "Keine Daten"},
        "Realp": {"min": 0, "raw": "Keine Daten"},
        "Kandersteg": {"min": 0, "raw": "Keine Daten"},
        "Goppenstein": {"min": 0, "raw": "Keine Daten"}
    }
    
    # --- FURKA (RSS) ---
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full = f"{title} {desc}"
            raw_xml = ET.tostring(item, encoding='unicode')
            
            std = re.search(r'(\d+)\s*Stunde', full)
            mn = re.search(r'(\d+)\s*Minute', full)
            val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
            
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": raw_xml}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": raw_xml}
    except Exception as e: st.warning(f"Furka RSS Fehler: {e}")

    # --- LÖTSCHBERG (Web Scraping) ---
    try:
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        l_resp.encoding = 'utf-8'
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        full_text = soup.get_text()
        
        for st_name in ["Kandersteg", "Goppenstein"]:
            # Suche nach Stunden und Minuten in der Nähe des Stationsnamens
            # Regex sucht im Umkreis von 100 Zeichen nach dem Stationsnamen
            pattern = rf"{st_name}.{{0,100}}?(\d+)\s*(Stunde|Minute)"
            matches = re.finditer(pattern, full_text, re.IGNORECASE | re.DOTALL)
            
            val = 0
            found_raw = f"Suche für {st_name}..."
            for m in matches:
                num = int(m.group(1))
                unit = m.group(2).lower()
                if "stunde" in unit: val = num * 60
                else: val = num
                found_raw = f"Match: {m.group(0)}"
                break # Ersten Treffer nehmen
                
            results[st_name] = {"min": val, "raw": found_raw}
    except Exception as e: st.warning(f"Lötschberg Fehler: {e}")
    
    return results

# --- 4. UI & FLOW ---
init_db()
all_data = fetch_all_data()
save_stats(all_data)

st.title("🏔️ Alpen-Autoverlad Live-Monitor")

# Darstellung Metriken (4 Spalten)
cols = st.columns(4)
for i, (name, d) in enumerate(all_data.items()):
    diff, arrow = get_trend(name, d['min'])
    delta_str = f"{diff:+} min (2h)" if diff is not None else "Initialisierung..."
    with cols[i]:
        st.metric(label=f"{arrow} {name}", value=f"{d['min']} Min", delta=delta_str, delta_color="inverse")

# --- 5. 24h TREND DIAGRAMM (FIXED X-AXIS) ---
st.subheader("📈 24h Trend (Stündliche Übersicht)")
conn = sqlite3.connect(DB_NAME)
df_24h = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ?", conn, params=(datetime.now() - timedelta(hours=24),))
conn.close()

if not df_24h.empty:
    df_24h['timestamp'] = pd.to_datetime(df_24h['timestamp'])
    
    # Altair Chart mit erzwungener stündlicher Beschriftung
    chart = alt.Chart(df_24h).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', 
                title='Uhrzeit',
                axis=alt.Axis(
                    format='%H:00', 
                    tickCount=24,        # Versucht 24 Ticks (einen pro Stunde) zu setzen
                    labelAngle=-45,
                    grid=True
                )),
        y=alt.Y('minuten:Q', title='Wartezeit (Minuten)', scale=alt.Scale(domainMin=0)),
        color=alt.Color('station:N', title='Station', scale=alt.Scale(scheme='tableau10')),
        tooltip=['timestamp:T', 'station:N', 'minuten:Q']
    ).properties(height=450).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle Daten für den 24h Trend...")

# --- 6. DEBUG ACCORDION ---
with st.expander("🛠️ Debug Informationen (Raw Data & DB History)"):
    tab1, tab2 = st.tabs(["Station Raw Info", "Datenbank Einträge (24h)"])
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Furka - Oberwald (RSS Item):**")
            st.code(all_data["Oberwald"]["raw"], language="xml")
            st.write("**BLS - Kandersteg (Regex Match):**")
            st.code(all_data["Kandersteg"]["raw"])
        with c2:
            st.write("**Furka - Realp (RSS Item):**")
            st.code(all_data["Realp"]["raw"], language="xml")
            st.write("**BLS - Goppenstein (Regex Match):**")
            st.code(all_data["Goppenstein"]["raw"])
            
    with tab2:
        st.write("**Letzte DB-Einträge (24h):**")
        if not df_24h.empty:
            st.dataframe(df_24h.sort_values(by="timestamp", ascending=False), use_container_width=True)

st.caption(f"Update: {datetime.now().strftime('%H:%M:%S')} | Trend-Basis: 2 Stunden | Speicher: 14 Tage")
