import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
import os
import sys
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Pfad-Fix für lokale Module
sys.path.append(os.path.dirname(__file__))
from logic import fetch_all_data, init_db, save_to_db, DB_NAME, CH_TZ

# 1. Seiteneinstellungen & Auto-Refresh (alle 5 Min)
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# 2. Daten-Initialisierung & Speicherung
init_db()
data = fetch_all_data()
save_to_db(data)  # Hier greift jetzt die xx:00, xx:05 Logik

st.title("🏔️ Autoverlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(len(data))
for i, (name, d) in enumerate(data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- 2. TREND CHART (Letzte 24h) ---
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    # Zeitfenster für den Chart berechnen
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Daten für Diagramm (24h) und Historie (alles) laden
    df_chart = pd.read_sql_query(f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

if not df_chart.empty:
    df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'])
    
    # Altair Chart mit dickerer Linie und sauberer X-Achse
    chart = alt.Chart(df_chart).mark_line(interpolate='monotone', size=3).encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:00', 
                    title="Uhrzeit (CET)",
                    tickCount={'interval': 'hour', 'step': 1},
                    labelAngle=-45
                )),
        y=alt.Y('minutes:Q', title="Wartezeit (Min)"),
        color=alt.Color('station:N', title="Station"),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Minuten')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle Daten für das 24h-Diagramm... Schau in 5 Minuten wieder rein!")

# --- 3. DEBUG BEREICH (Korrigiert) ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    # Tabs erst definieren, dann befüllen
    tab1, tab2 = st.tabs(["Aktuelle Rohdaten (JSON)", "Datenbank Historie (14 Tage)"])
    
    with tab1:
        st.write("Letzte API-Antwort:")
        st.json(data)
        
    with tab2:
        st.write(f"Gesamtanzahl Einträge: {len(df_history)}")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Raster: 5 Min")
