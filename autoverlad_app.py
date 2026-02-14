import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
import os
import sys
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Fix für den ImportError
sys.path.append(os.path.dirname(__file__))

from logic import fetch_all_data, init_db, save_to_db, DB_NAME, CH_TZ

st.set_page_config(page_title="Alpen-Verlad PRO", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Initialisierung und Datenerhebung
init_db()
data = fetch_all_data()
save_to_db(data)

st.title("🏔️ Alpen-Verlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    # Hinweis: Da get_trend_2h noch nicht in logic.py ist, 
    # zeigen wir hier erst mal nur die aktuellen Werte.
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- 2. TREND CHART ---
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    # Wir laden die Daten
    df = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp ASC", conn)

if not df.empty:
    # EXPLIZITE KONVERTIERUNG: Das löst das leere Diagramm-Problem
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Altair Chart Definition
    chart = alt.Chart(df).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:00', 
                    title="Uhrzeit (CET)",
                    # Das erzwingt exakt EINEN Tick pro Stunde
                    tickCount={'interval': 'hour', 'step': 1},
                    labelAngle=-45,
                    grid=True
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
    st.info("Datenbank ist noch leer. Bitte warten, bis die ersten Datenpunkte geloggt wurden.")

# --- 3. DEBUG BEREICH (Wieder eingebaut) ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen (Rohdaten & Datenbank)"):
    tab1, tab2 = st.tabs(["Raw Data", "DB History (24h)"])
    
    with tab1:
        st.write("**Aktuelle Abfrage-Ergebnisse:**")
        st.json(data)
    
    with tab2:
        st.write(f"Aktuelle Zeit (Schweiz): {datetime.now(CH_TZ).strftime('%H:%M:%S')}")
        if not df.empty:
            # Zeigt die neuesten Einträge oben an
            st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)
        else:
            st.info("Noch keine historischen Daten in der Datenbank.")

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Raster: 5 Min")
