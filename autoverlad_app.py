import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Import der Logik-Funktionen
from logic import fetch_all_data, init_db, save_to_db, get_all_timetables, DB_NAME, CH_TZ

# Konfiguration
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# Datenverarbeitung bei jedem Refresh
init_db()
data = fetch_all_data()
save_to_db(data)
timetables = get_all_timetables()

st.title("🏔️ Autoverlad Live-Monitor")

# --- 1. METRIKEN (Wartezeiten) ---
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

# --- 3. TREND CHART (24h) ---
st.markdown("---")
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    cutoff_24h = (datetime.now(CH_TZ) - pd.Timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    df_chart = pd.read_sql_query(f"SELECT * FROM stats WHERE timestamp >= '{cutoff_24h}' ORDER BY timestamp ASC", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC", conn)

if not df_chart.empty:
    df_plot = df_chart.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp']).dt.tz_localize(None)
    df_plot['minutes'] = pd.to_numeric(df_plot['minutes']).fillna(0)
    
    chart = alt.Chart(df_plot).mark_line(interpolate='monotone', size=3, point=True).encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:%M', title="Zeit", labelAngle=-45)),
        y=alt.Y('minutes:Q', title="Wartezeit (Min)", scale=alt.Scale(domainMin=0, domainMax=60)),
        color=alt.Color('station:N', title="Station"),
        tooltip=['timestamp:T', 'station:N', 'minutes:Q']
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle erste Datenpunkte...")

# --- 4. DEBUG ---
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["JSON Rohdaten", "Datenbank Historie"])
    with tab1:
        st.json(data)
    with tab2:
        st.write(f"Einträge in DB: {len(df_history)}")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')}")
