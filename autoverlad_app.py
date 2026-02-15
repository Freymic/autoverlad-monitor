import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime
from logic import fetch_all_data, init_db, save_to_db, save_to_google_sheets, DB_NAME, CH_TZ
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import datetime

# 1. Seiteneinstellungen
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")

# 2. Daten initialisieren & abrufen
init_db()  # Hier wird jetzt auch der automatische Restore aus GSheets gemacht
data = fetch_all_data()

# Speichern in beide Systeme
save_to_db(data)
# Wir fangen den Erfolg des GSheets-Updates ab
gs_success = save_to_google_sheets(data)

if gs_success:
    st.toast("Cloud-Backup aktualisiert!", icon="☁️")

st.title("🏔️ Autoverlad Monitor")

# --- 1. METRIKEN ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN ---
with sqlite3.connect(DB_NAME) as conn:
    # Letzte 24h für das Chart
    df = pd.read_sql_query("SELECT * FROM stats WHERE timestamp >= datetime('now', '-24 hours')", conn)
    # Historie für den Debug-Tab
    df_history = pd.read_sql_query("SELECT * FROM stats ORDER BY timestamp DESC LIMIT 100", conn)

# --- 3. TREND CHART ---
st.subheader("📈 24h Trend")

if not df.empty:
    df_plot = df.copy()
    df_plot['timestamp'] = pd.to_datetime(df_plot['timestamp'])
    
    # Sicherheits-Filter gegen Millionen-Werte
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

# --- 4. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen"):
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

# --- 6. DYNAMISCHER AUTOREFRESH (xx:00, xx:05, ...) ---
now = datetime.now(CH_TZ)
# Berechne Sekunden bis zum nächsten 5-Minuten-Takt
# Beispiel: Es ist 20:03 -> seconds_past = 3*60 = 180s. 
# wait = (300 - 180) + 10s Puffer = 130s.
seconds_past_interval = (now.minute % 5) * 60 + now.second
seconds_to_wait = (300 - seconds_past_interval) + 10 # +10s Puffer für API-Aktualisierung

# Falls wir aus Versehen < 0 landen
if seconds_to_wait < 10:
    seconds_to_wait += 300

# Trigger Refresh in Millisekunden
st_autorefresh(interval=seconds_to_wait * 1000, key="auto_sync_trigger")

st.caption(f"Letztes Update: {now.strftime('%H:%M:%S')} | Nächstes Update in ~{int(seconds_to_wait)}s")
