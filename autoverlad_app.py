import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
import os
import sys
from streamlit_autorefresh import st_autorefresh

# Fix für den ImportError: Pfad explizit hinzufügen
sys.path.append(os.path.dirname(__file__))

from logic import fetch_all_data, init_db, save_to_db, DB_NAME, CH_TZ

st.set_page_config(page_title="Alpen-Verlad PRO", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

init_db()
data = fetch_all_data()
save_to_db(data)

st.title("🏔️ Alpen-Verlad Live-Monitor")

# Darstellung Metriken
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# Trend Chart
st.subheader("📈 24h Trend")
with sqlite3.connect(DB_NAME) as conn:
    df = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp ASC", conn)

if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    chart = alt.Chart(df).mark_line(interpolate='monotone').encode(
        x=alt.X('timestamp:T', axis=alt.Axis(format='%H:00', title="Uhrzeit")),
        y=alt.Y('minuten:Q', title="Wartezeit (Min)"),
        color='station:N'
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)
