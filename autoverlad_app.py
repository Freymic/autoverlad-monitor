import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
import datetime
from streamlit_autorefresh import st_autorefresh

# Importiere die neuen, konsolidierten Funktionen aus der logic.py
from logic import (
    fetch_all_data, 
    init_db, 
    save_to_db, 
    save_to_google_sheets, 
    DB_NAME, 
    CH_TZ
)

# 1. Seiteneinstellungen
st.set_page_config(page_title="Autoverlad Monitor", layout="wide", page_icon="🏔️")

# 2. Daten-Initialisierung & zentraler Abruf
init_db()

# Hier holen wir ALLES mit einem einzigen Aufruf (inkl. KI-Status & Wartezeiten)
full_payload = fetch_all_data()

# Daten entpacken für einfachere Nutzung
data = full_payload["wait_times"]
active_status = full_payload["active_status"]
furka_aktiv = active_status["furka"]
loetschberg_aktiv = active_status["loetschberg"]

# Speichern (Lokal & Cloud)
save_to_db(full_payload)
gs_success = save_to_google_sheets(full_payload)

if gs_success:
    st.toast("Cloud-Backup aktualisiert!", icon="☁️")

# --- UI HEADER ---
st.title("🏔️ Autoverlad Monitor")

# --- ZENTRALE STATUS-WARNUNGEN ---
if not furka_aktiv or not loetschberg_aktiv:
    if not furka_aktiv:
        st.error("🚨 **Hinweis:** Der Verladbetrieb am **Furka** (Realp/Oberwald) ist aktuell **eingestellt**.")
    if not loetschberg_aktiv:
        st.error("🚨 **Hinweis:** Der Verladbetrieb am **Lötschberg** (Kandersteg/Goppenstein) ist aktuell **eingestellt**.")

# --- 1. METRIKEN ---
# Mapping, welche Station zu welchem Verbund gehört
station_to_provider = {
    "Realp": "furka",
    "Oberwald": "furka",
    "Kandersteg": "loetschberg",
    "Goppenstein": "loetschberg"
}

cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    provider = station_to_provider.get(name)
    ist_aktiv = active_status.get(provider, True)
    
    with cols[i % 4]:
        if not ist_aktiv:
            st.metric(
                label=name, 
                value="GESPERRT", 
                delta="Betrieb eingestellt", 
                delta_color="inverse"
            )
        else:
            st.metric(
                label=name, 
                value=f"{d['min']} Min",
                delta="Normalbetrieb" if d['min'] == 0 else "Wartezeit"
            )

# --- 2. TREND CHART ---
with sqlite3.connect(DB_NAME) as conn:
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp >= datetime('now', '-24 hours')", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 100", conn)

st.subheader("📈 24h Trend")
if not df.empty:
    df_plot = df.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])
    # Filter für Ausreißer (9999er Werte oder Nachtpausen)
    df_plot = df_plot[df_plot['minutes'] < 500]
    
    chart = alt.Chart(df_plot).mark_line(
        interpolate='monotone', 
        size=3, 
        point=True
    ).encode(
        x=alt.X('timestamp:T', title="Uhrzeit (CET)", axis=alt.Axis(format='%H:%M')),
        y=alt.Y('minutes:Q', title="Wartezeit (Minuten)", scale=alt.Scale(domain=[0, 180])),
        color=alt.Color('station:N', title="Station"),
        tooltip=[
            alt.Tooltip('timestamp:T', format='%H:%M', title='Zeit'),
            alt.Tooltip('station:N', title='Station'),
            alt.Tooltip('minutes:Q', title='Wartezeit (Min)')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Trend-Daten für die letzten 24h vorhanden.")

# --- 3. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen & Experten-Diagnose"):
    tab1, tab2, tab3 = st.tabs(["JSON Rohdaten", "Datenbank Historie", "KI-Status Analyse"])
    
    with tab1:
        st.write("Aktuelle Payload aus `fetch_all_data`:")
        st.json(full_payload)
    
    with tab2:
        st.write("Letzte 100 Einträge in SQLite:")
        st.dataframe(df_history, use_container_width=True)
        
    with tab3:
        st.write("### KI-Entscheidungs-Matrix")
        c1, c2 = st.columns(2)
        c1.info(f"**Lötschberg Status:** {'✅ OFFEN' if loetschberg_aktiv else '❌ GESPERRT'}")
        c2.info(f"**Furka Status:** {'✅ OFFEN' if furka_aktiv else '❌ GESPERRT'}")
        st.caption("Diese Status werden durch Gemini basierend auf den Live-Texten der BLS und MGB ermittelt.")

# --- 4. STATUS & REFRESH ---
now = datetime.datetime.now(CH_TZ)
# Zeit bis zum nächsten vollen 5-Minuten-Intervall berechnen
seconds_past_interval = (now.minute % 5) * 60 + now.second
seconds_to_wait = (300 - seconds_past_interval) + 10 # 10s Puffer

st_autorefresh(interval=seconds_to_wait * 1000, key="auto_sync_trigger")

st.markdown("---")
col_info1, col_info2 = st.columns(2)
with col_info1:
    st.caption(f"Letztes Update: {now.strftime('%H:%M:%S')} | Nächstes Update in ~{int(seconds_to_wait)}s")
with col_info2:
    try:
        ws = st.secrets["connections"]["gsheets"]["worksheet"]
        st.caption(f"☁️ Cloud-Sync: Aktiv (Tab: {ws})")
    except:
        st.caption("☁️ Cloud-Sync: Lokaler Modus")
