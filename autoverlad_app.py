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
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN ---
with sqlite3.connect(DB_NAME) as conn:
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    df_chart = pd.read_sql_query(f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df_chart.empty:
    # Daten-Vorbereitung für Altair
    df_plot = df_chart.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    df_plot['minutes'] = pd.to_numeric(df_plot['minutes'], errors='coerce').fillna(0).astype(int)
    
    chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', 
        size=3, 
        point=True  # Wichtig: Zeigt Punkte auch wenn die Linie flach bei 0 liegt
    ).encode(
        x=alt.X('timestamp:T', 
                title="Uhrzeit (CET)",
                axis=alt.Axis(format='%H:%M', tickCount='hour', labelAngle=-45)),
        y=alt.Y('minutes:Q', 
                title="Wartezeit (Minuten)",
                scale=alt.Scale(domainMin=0, domainMax=60)), # Skala bis 60, damit 0-Linie sichtbar ist
        color=alt.Color('station:N', title="Station"),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Wartezeit (Min)')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Daten für die letzten 24h vorhanden. Die ersten Punkte erscheinen im nächsten 5-Minuten-Raster.")

# --- 4. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["JSON Rohdaten", "Datenbank Historie"])
    
    with tab1:
        st.write("Letzte API-Antwort:")
        st.json(data)
        
    with tab2:
        # Sicherstellen, dass df_history existiert (behebt NameError)
        st.write(f"Einträge in der Datenbank: {len(df_history)}")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Intervall: 5 Min")
