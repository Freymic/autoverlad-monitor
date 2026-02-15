import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
from logic import fetch_all_data, init_db, save_to_db, DB_NAME, CH_TZ

st.set_page_config(page_title="Autoverlad Live", layout="wide")

# Daten holen
init_db()
data = fetch_all_data()
save_to_db(data) 

st.title("🏔️ Autoverlad Monitor (Stabiler Modus)")

# Metriken
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# Chart
with sqlite3.connect(DB_NAME) as conn:
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp >= datetime('now', '-24 hours')", conn)

if not df.empty:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('timestamp:T', title="Zeit"),
        y=alt.Y('minutes:Q', title="Minuten", scale=alt.Scale(domain=[0, 180])), # Fest auf 180 Min eingestellt
        color='station:N'
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)
