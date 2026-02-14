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
st.set_page_config(page_title="Alpen-Verlad PRO", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Daten-Initialisierung
init_db()
data = fetch_all_data()
save_to_db(data)

st.title("🏔️ Alpen-Verlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(len(data))
for i, (name, d) in enumerate(data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- 2. TREND CHART ---
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    df = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp ASC", conn)

if not df.empty:
    # Daten für Altair vorbereiten
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Chart Definition mit optimierter X-Achse
    chart = alt.Chart(df).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:00', 
                    title="Uhrzeit (CET)",
                    # Erzwingt exakt jede volle Stunde als Beschriftung
                    tickCount={'interval': 'hour', 'step': 1},
                    labelAngle=-45,
                    grid=True
                )),
        y=alt.Y('minutes:Q', title="Wartezeit (Min)"),
        color=alt.Color('station:N', title="Station"),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Wartezeit')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle erste Datenpunkte für das Diagramm...")

# --- 3. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["Aktuelle Raw Data", "Datenbank Historie"])
    with tab1:
        st.json(data)
    with tab2:
        st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Raster: 5 Min")
