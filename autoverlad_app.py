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
save_to_db(data) 

st.title("🏔️ Autoverlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(len(data))
for i, (name, d) in enumerate(data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN (Global definiert, um NameError zu vermeiden) ---
with sqlite3.connect(DB_NAME) as conn:
    # Zeitfenster für den Chart berechnen (letzte 24h)
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Diagramm-Daten (24h)
    df_chart = pd.read_sql_query(f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", conn)
    
    # Historie-Daten (Alles für Debug)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df_chart.empty:
    # 1. DATEN-REINIGUNG (Das "Sicherheitsnetz")
    df_plot = df_chart.copy()
    
    # Sicherstellen, dass timestamp ein echtes Datum ohne Zeitzonen-Konflikt ist
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    
    # Sicherstellen, dass minutes eine echte Zahl ist
    df_plot['minutes'] = pd.to_numeric(df_plot['minutes'], errors='coerce').fillna(0).astype(int)
    
    # 2. CHART DEFINITION
    chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', 
        size=3, 
        point=True  # Zeigt Punkte, falls noch keine Linie möglich ist
    ).encode(
        x=alt.X('timestamp:T', 
                title="Uhrzeit (CET)",
                axis=alt.Axis(
                    format='%H:%M', 
                    tickCount='hour', 
                    labelAngle=-45
                )),
        y=alt.Y('minutes:Q', 
                title="Wartezeit (Minuten)",
                scale=alt.Scale(domainMin=0, nice=True)), # Startet immer bei 0
        color=alt.Color('station:N', title="Station", scale=alt.Scale(scheme='category10')),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Wartezeit (Min)')
        ]
    ).properties(
        height=400
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Daten für die letzten 2

# --- 4. DEBUG BEREICH (NameError Fix) ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["JSON Rohdaten", "Datenbank Historie"])
    
    with tab1:
        st.write("Letzte API-Antwort:")
        st.json(data)
        
    with tab2:
        # df_history ist jetzt sicher definiert
        st.write(f"Gesamtanzahl Einträge in der Datenbank: {len(df_history)}")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Raster: 5 Min")
