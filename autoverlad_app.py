import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

from logic import fetch_all_data, init_db, save_to_db, get_all_timetables, get_db_status, DB_NAME, CH_TZ

st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

init_db()
data = fetch_all_data()
save_to_db(data)
timetables = get_all_timetables()
db_info = get_db_status()

st.title("🏔️ Autoverlad Live-Monitor")

# --- 1. METRIKEN ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. FAHRPLAN ---
st.markdown("---")
st.subheader("🕒 Nächste Abfahrten")
t_cols = st.columns(4)
for i, (name, departures) in enumerate(timetables.items()):
    with t_cols[i]:
        with st.container(border=True):
            st.markdown(f"**{name}**")
            for dep in departures:
                st.caption(f"🚆 {dep}")

# --- 3. TREND CHART ---
st.markdown("---")
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    df_chart = pd.read_sql_query(f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

if not df_chart.empty:
    df_plot = df_chart.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    chart = alt.Chart(df_plot).mark_line(interpolate='monotone', size=3, point=True).encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:%M', title="Zeit")),
        y=alt.Y('minutes:Q', title="Min", scale=alt.Scale(domainMin=0, domainMax=60)),
        color=alt.Color('station:N', title="Station"),
        tooltip=['timestamp:T', 'station:N', 'minutes:Q']
    ).properties(height=350).interactive()
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Warte auf Datenpunkte...")

# --- 4. ERWEITERTER DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug & System-Status"):
    # Drei Tabs für mehr Übersicht
    tab1, tab2, tab3 = st.tabs(["📊 DB Status", "🌐 API Rohdaten", "📜 Historie"])
    
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Einträge Gesamt", db_info["eintraege"])
        c2.metric("Ältester Datenpunkt", db_info["aeltester"].split(" ")[0] if " " in db_info["aeltester"] else "-")
        c3.metric("DB-Speicherort", DB_NAME)
        st.write("Die Datenbank wird alle 5 Minuten quantisiert und hält Daten für maximal 14 Tage.")
        
    with tab2:
        st.write("Aktuelle Roh-Antworten der Verlad-Dienste:")
        st.json(data)
        
    with tab3:
        st.write("Die letzten Einträge (sortiert nach Zeit):")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Zeitzone: {CH_TZ}")
