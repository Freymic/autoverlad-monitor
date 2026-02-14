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

# Konfiguration
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Daten-Initialisierung
init_db()
data = fetch_all_data()
save_to_db(data)

st.title("🏔️ Autoverlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(len(data))
for i, (name, d) in enumerate(data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- 2. TREND CHART ---
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    # WICHTIG: Wir laden alle Daten für das Dataframe (für das Debug-Tab), 
    # filtern aber hier gezielt für das Diagramm.
    
    # 1. Zeitstempel für "vor 24 Stunden" berechnen
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    # 2. Nur die Daten der letzten 24h für den Chart abfragen
    query_chart = f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC"
    df_chart = pd.read_sql_query(query_chart, conn)
    
    # 3. Optional: Alle Daten für das Debug-Tab laden (letzte 2 Wochen)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

if not df_chart.empty:
    df_chart['timestamp'] = pd.to_datetime(df_chart['timestamp'])
    
    # Chart Definition
    chart = alt.Chart(df_chart).mark_line(interpolate='monotone', size=3).encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:00', 
                    title="Uhrzeit (letzte 24h)",
                    tickCount={'interval': 'hour', 'step': 1},
                    labelAngle=-45
                )),
        y=alt.Y('minutes:Q', title="Wartezeit (Min)"),
        color=alt.Color('station:N', title="Station"),
        tooltip=['timestamp:T', 'station:N', 'minutes:Q']
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle Daten für das 24h-Diagramm...")

# Im Debug-Bereich unten kannst du dann df_history statt df_chart anzeigen:
with st.expander("🛠️ Debug Informationen"):
    # ... (Tabs Code) ...
    with tab2:
        st.dataframe(df_history, use_container_width=True)

# --- 3. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["Aktuelle Raw Data", "Datenbank Historie"])
    with tab1:
        st.json(data)
    with tab2:
        st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Raster: 5 Min")
