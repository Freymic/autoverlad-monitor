import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
from logic import fetch_all_data, init_db, save_to_db, DB_NAME, CH_TZ

# 1. Seiteneinstellungen
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")

# 2. Daten initialisieren & abrufen
init_db()
data = fetch_all_data()
save_to_db(data) 

st.title("🏔️ Autoverlad Monitor")

# --- 1. METRIKEN ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN ---
with sqlite3.connect(DB_NAME) as conn:
    # Nur Daten der letzten 24h laden
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp >= datetime('now', '-24 hours')", conn)
    # Volle Historie für den Debug-Tab
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 100", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df.empty:
    df_plot = df.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])
    
    # Sicherheits-Filter gegen Millionen-Werte/Zeitstempel-Fehler
    df_plot = df_plot[df_plot['minutes'] < 500]
    
   chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', 
        size=3, 
        point=True  # Wichtig: Zeigt Punkte auch wenn die Linie flach bei 0 liegt
    ).encode(
        x=alt.X('timestamp:T', 
                title="Uhrzeit (CET)",
                axis=alt.Axis(format='%H:%M', tickCount='hour', labelAngle=-45)),
        y=alt.Y('minutes:Q', 
                title="Wartezeit (Minuten)",
                scale=alt.Scale(domainMin=0, domainMax=180)), # Skala bis 60, damit 0-Linie sichtbar ist
        color=alt.Color('station:N', title="Station"),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Wartezeit (Min)')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Daten vorhanden.")

# --- 4. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    tab1, tab2 = st.tabs(["JSON Rohdaten", "Datenbank Historie"])
    
    with tab1:
        st.write("Letzte API-Antwort:")
        st.json(data)
        
    with tab2:
        st.write(f"Die letzten {len(df_history)} Einträge aus der Datenbank:")
        st.dataframe(df_history, use_container_width=True)

st.caption(f"Letztes Update: {datetime.now(CH_TZ).strftime('%H:%M:%S')} | Intervall: 5 Min")
