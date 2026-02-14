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
    # Wir laden die Daten und stellen sicher, dass die Spalte 'minutes' vorhanden ist
    df = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp ASC", conn)

if not df.empty:
    # Fehlervermeidung beim Zeitformat
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    
    # Chart-Definition mit Korrektur der Spalten und X-Achse
    chart = alt.Chart(df).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', 
                axis=alt.Axis(
                    format='%H:00', 
                    title="Uhrzeit (CET)",
                    # Erzwingt die Anzeige jeder vollen Stunde
                    tickCount={'interval': 'hour', 'step': 1}
                )),
        y=alt.Y('minutes:Q', title="Wartezeit (Min)"), # Spalte muss 'minutes' sein
        color='station:N',
        tooltip=['timestamp:T', 'station:N', 'minutes:Q']
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Daten für das Diagramm verfügbar.")
    
    

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
