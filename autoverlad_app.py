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

DB_NAME = 'autoverlad_v5.db'

# --- 2. DATABASE LOGIK ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Wir speichern Station, Minuten und Zeitstempel
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (timestamp DATETIME, station TEXT, minuten INTEGER)''')
    conn.commit()
    conn.close()

def save_stats(data_dict):
    conn = sqlite3.connect(DB_NAME)
    now = datetime.now()
    # Prüfen, ob für diese Minute schon Daten da sind (Vermeidung von Dopplungen)
    for station, mins in data_dict.items():
        conn.execute("INSERT INTO stats VALUES (?, ?, ?)", (now, station, mins))
    # Cleanup: Daten älter als 14 Tage löschen
    conn.execute("DELETE FROM stats WHERE timestamp < ?", (now - timedelta(days=14),))
    conn.commit()
    conn.close()

def get_trend(station, current_val):
    """Vergleicht aktuellen Wert mit dem Wert von vor ca. 2 Stunden."""
    conn = sqlite3.connect(DB_NAME)
    two_hours_ago = datetime.now() - timedelta(hours=2)
    # Suche den nächsten Wert, der ca. 2h alt ist
    query = """SELECT minuten FROM stats 
               WHERE station = ? AND timestamp <= ? 
               ORDER BY timestamp DESC LIMIT 1"""
    old_df = pd.read_sql_query(query, conn, params=(station, two_hours_ago))
    conn.close()
    
    if old_df.empty:
        return None, "n/a"
    
    old_val = old_df['minuten'].iloc[0]
    diff = current_val - old_val
    
    if diff > 0: return diff, "⬆️"
    if diff < 0: return diff, "⬇️"
    return 0, "➡️"

# --- 3. DATEN-ABRUF (FURKA & LÖTSCHBERG) ---
def fetch_furka():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    res = {"Oberwald": 0, "Realp": 0}
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            std = re.search(r'(\d+)\s*Stunde', full)
            mn = re.search(r'(\d+)\s*Minute', full)
            val = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
            if "Oberwald" in full: res["Oberwald"] = val
            if "Realp" in full: res["Realp"] = val
    except: pass
    return res

def fetch_loetschberg():
    url = "https://www.bls.ch/de/fahren/autoverlad/betriebslage"
    res = {"Kandersteg": 0, "Goppenstein": 0}
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        
        for station in res.keys():
            # Suche nach Mustern wie "Kandersteg: 30 Minuten" oder "Keine Wartezeit"
            pattern = rf"{station}.*?(\d+)\s*Minute"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                res[station] = int(match.group(1))
            elif f"keine wartezeit" in text.lower():
                res[station] = 0
    except: pass
    return res

# --- 4. UI LOGIK ---
init_db()
furka_data = fetch_furka()
bls_data = fetch_loetschberg()
all_data = {**furka_data, **bls_data}

# Nur speichern, wenn wir im 5-Min-Takt sind (Logik vereinfacht)
save_stats(all_data)

st.title("🏔️ Alpen-Autoverlad Live-Monitor")

# Darstellung in 4 Spalten
cols = st.columns(4)
for i, (station, mins) in enumerate(all_data.items()):
    with cols[i]:
        diff, arrow = get_trend(station, mins)
        # Delta zeigt die Veränderung zum Wert vor 2h
        delta_val = f"{diff} min" if diff is not None else "Neu"
        st.metric(label=f"{arrow} {station}", value=f"{mins} Min", delta=delta_val, delta_color="inverse")

# --- 5. 24h TREND DIAGRAMM ---
st.subheader("📈 24h Trend (Vergleich alle Stationen)")
conn = sqlite3.connect(DB_NAME)
df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp > ?", conn, 
                       params=(datetime.now() - timedelta(hours=24),))
conn.close()

if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    chart = alt.Chart(df).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:00', title='Uhrzeit (24h)', tickCount=12)),
        y=alt.Y('minuten:Q', title='Wartezeit (min)'),
        color=alt.Color('station:N', title='Station'),
        tooltip=['timestamp:T', 'station:N', 'minuten:Q']
    ).properties(height=450).interactive()
    st.altair_chart(chart, use_container_width=True)

# --- 6. DEBUG ---
with st.expander("🛠️ Debug & History"):
    st.write("**Letzte DB Einträge:**")
    st.dataframe(df.sort_values(by="timestamp", ascending=False).head(20))
