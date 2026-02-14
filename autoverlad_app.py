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
    # Datentypen für Altair fixen
    df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'])
    df_chart['minutes'] = pd.to_numeric(df_chart['minutes'])
    
    chart = alt.Chart(df_chart).mark_line(interpolate='monotone', size=3, point=True).encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:%M', 
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
    st.info("Sammle Daten für das 24h-Diagramm... (Punkte erscheinen alle 5 Minuten)")

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
