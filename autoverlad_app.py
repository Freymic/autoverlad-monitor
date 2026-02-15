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
    # Wir holen die Spalten explizit einzeln ab
    df_chart = pd.read_sql_query(
        f"SELECT timestamp, station, minutes FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", 
        conn
    )
    df_history = pd.read_sql_query("SELECT timestamp, station, minutes, raw_text FROM stats ORDER BY timestamp DESC LIMIT 100", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df_chart.empty:
    df_plot = df_chart.copy()
    
    # 1. SICHERHEIT: Timestamp in echtes Datum umwandeln
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    
    # 2. SICHERHEIT: Minuten strikt in Zahlen umwandeln und ALLES über 480 (8h) kappen
    # Das verhindert, dass Zeitstempel-Zahlen das Diagramm sprengen
    df_plot['minutes'] = pd.to_numeric(df_plot['minutes'], errors='coerce').fillna(0)
    df_plot = df_plot[df_plot['minutes'] < 500] # Sicherheits-Filter gegen Millionen-Werte
    
    # Dynamischer Deckel (Puffer)
    current_max = int(df_plot['minutes'].max()) if not df_plot.empty else 0
    upper_limit = max(60, ((current_max // 30) + 1) * 30 + 30)

    chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', size=3, point=True 
    ).encode(
        x=alt.X('timestamp:T', title="Uhrzeit"),
        y=alt.Y('minutes:Q', 
                title="Wartezeit (Minuten)",
                scale=alt.Scale(domain=[0, upper_limit])),
        color=alt.Color('station:N', title="Station"),
        tooltip=['timestamp:T', 'station:N', 'minutes:Q']
    ).properties(height=400).interactive()
    
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
