import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
# Importiere get_furka_status zusätzlich aus deiner logic.py
from logic import fetch_all_data, init_db, save_to_db, save_to_google_sheets, DB_NAME, CH_TZ, get_furka_status
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import datetime # Doppelt hält besser für die Stabilität

# 1. Seiteneinstellungen
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")

# 2. Daten initialisieren & abrufen
init_db()  # Automatischer Restore aus GSheets
data = fetch_all_data()
furka_aktiv = get_furka_status() # NEU: Status aus RSS-Feed prüfen

# Speichern in beide Systeme
save_to_db(data)
gs_success = save_to_google_sheets(data)

if gs_success:
    st.toast("Cloud-Backup aktualisiert!", icon="☁️")

st.title("🏔️ Autoverlad Monitor")

# --- NEU: ZENTRALE STATUS-MELDUNG ---
if not furka_aktiv:
    st.error("🚨 **Hinweis:** Der Verladbetrieb am Furka (Realp/Oberwald) ist aktuell **eingestellt**.")

# --- 1. METRIKEN (Erweitert um Status-Logik) ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    ist_furka = name in ["Realp", "Oberwald"]
    
    if ist_furka and not furka_aktiv:
        # Anzeige wenn geschlossen
        cols[i % 4].metric(
            label=name, 
            value="GESPERRT", 
            delta="Betrieb eingestellt", 
            delta_color="inverse"
        )
    else:
        # Normale Anzeige
        cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN ---
with sqlite3.connect(DB_NAME) as conn:
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp >= datetime('now', '-24 hours')", conn)
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 100", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df.empty:
    df_plot = df.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])
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
    st.info("Noch keine Daten vorhanden.")

# --- 4. DEBUG BEREICH (Erweitert) ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
    st.write(f"Furka-Status (RSS): **{'✅ Aktiv' if furka_aktiv else '❌ Eingestellt'}**")
    
    tab1, tab2 = st.tabs(["JSON Rohdaten", "Datenbank Historie"])
    with tab1:
        st.write("Letzte API-Antwort:")
        st.json(data)
    with tab2:
        st.write("Letzte Einträge aus SQLite:")
        st.dataframe(df_history, use_container_width=True)

# --- 5. STATUS & CLOUD-INFO ---
try:
    current_ws = st.secrets["connections"]["gsheets"]["worksheet"]
    st.success(f"✅ Cloud-Backup aktiv: Tab **'{current_ws}'**.")
except Exception:
    st.info("ℹ️ Cloud-Backup: Standard-Modus aktiv.")

# --- 6. DYNAMISCHER AUTOREFRESH ---
now = datetime.datetime.now(CH_TZ)

seconds_past_interval = (now.minute % 5) * 60 + now.second
seconds_to_wait = (300 - seconds_past_interval) + 10 

if seconds_to_wait < 10:
    seconds_to_wait += 300

st_autorefresh(interval=seconds_to_wait * 1000, key="auto_sync_trigger")

st.caption(f"Letztes Update: {now.strftime('%H:%M:%S')} | Nächstes Update in ~{int(seconds_to_wait)}s")
