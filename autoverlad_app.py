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

# --- 2. DATEN LADEN (Optimiert) ---
with sqlite3.connect(DB_NAME) as conn:
    # Wir laden NUR die letzten 24h und NUR realistische Werte (< 500 Min)
    # Das verhindert, dass 40-Millionen-Leichen das Diagramm bremsen
    query = """
    SELECT timestamp, station, minutes 
    FROM stats 
    WHERE timestamp >= datetime('now', '-24 hours') 
    AND minutes < 500
    ORDER BY timestamp ASC
    """
    df_chart = pd.read_sql_query(query, conn)
    
    # Historie begrenzen auf die letzten 50 Einträge (reicht für Debug)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 50", conn)

# --- 3. TREND CHART (Performant) ---
st.subheader("📈 24h Trend")

if not df_chart.empty:
    df_plot = df_chart.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    
    # Dynamisches Limit ohne komplexe Listenberechnung
    current_max = int(df_plot['minutes'].max())
    upper_limit = max(60, int(current_max * 1.2))

    chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', size=3, point=True 
    ).encode(
        x=alt.X('timestamp:T', title="Uhrzeit"),
        y=alt.Y('minutes:Q', title="Minuten", scale=alt.Scale(domain=[0, upper_limit])),
        color='station:N'
    ).properties(height=400)
    
    st.altair_chart(chart, use_container_width=True)

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
