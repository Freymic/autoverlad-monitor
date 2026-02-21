import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
import datetime
from logic import (
    fetch_all_data, 
    init_db, 
    DB_NAME, 
    CH_TZ, 
    get_furka_status,
    get_loetschberg_status,
    get_gemini_situation_report
)
from streamlit_autorefresh import st_autorefresh

# 1. Seiteneinstellungen
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")

# 2. Daten initialisieren & abrufen
init_db()  

data = fetch_all_data()

furka_aktiv = get_furka_status() 
loetschberg_aktiv = get_loetschberg_status()

st.title("🏔️ Autoverlad Monitor")

# --- NEU: PLATZHALTER FÜR DEN LAGEBERICHT ---
# st.empty() reserviert den Platz oben. Wir füllen ihn ganz am Schluss.
report_placeholder = st.empty()

# --- ZENTRALE STATUS-MELDUNGEN ---
if not furka_aktiv or not loetschberg_aktiv:
    if not furka_aktiv:
        st.error("🚨 **Hinweis:** Der Verladbetrieb am **Furka** (Realp/Oberwald) ist aktuell **eingestellt**.")
    if not loetschberg_aktiv:
        st.error("🚨 **Hinweis:** Der Verladbetrieb am **Lötschberg** (Kandersteg/Goppenstein) ist aktuell **eingestellt**.")

# --- 1. METRIKEN ---
cols = st.columns(4)
for i, (name, d) in enumerate(data.items()):
    ist_furka = name in ["Realp", "Oberwald"]
    ist_loetsch = name in ["Kandersteg", "Goppenstein"]
    
    gesperrt = (ist_furka and not furka_aktiv) or (ist_loetsch and not loetschberg_aktiv)
    
    if gesperrt:
        cols[i % 4].metric(
            label=name, 
            value="GESPERRT", 
            delta="Betrieb eingestellt", 
            delta_color="inverse"
        )
    else:
        cols[i % 4].metric(label=name, value=f"{d['min']} Min")

# --- 2. DATEN LADEN (Historie für Chart) ---
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

# --- 4. DEBUG BEREICH ---
st.markdown("---")
with st.expander("🛠️ Debug Informationen & Experten-Diagnose"):
    col_stat1, col_stat2 = st.columns(2)
    col_stat1.write(f"Furka-Status (RSS): **{'✅ Aktiv' if furka_aktiv else '❌ Eingestellt'}**")
    col_stat2.write(f"Lötschberg-Status (API): **{'✅ Aktiv' if loetschberg_aktiv else '❌ Eingestellt'}**")
    
    tab1, tab2, tab3 = st.tabs(["JSON Rohdaten", "Datenbank Historie", "Experten-Diagnose (Live)"])
    
    with tab1:
        st.write("Aktuelle Wartezeit-Daten:")
        st.json(data)
    
    with tab2:
        st.write("Letzte 100 Einträge aus der SQLite DB:")
        st.dataframe(df_history, use_container_width=True)
        
    with tab3:
        st.write("### Live-Abfrage der Verkehrs-Feeds")
        diag_col1, diag_col2 = st.columns(2)
        import requests
        with diag_col1:
            st.markdown("**Furka (MGB RSS)**")
            try:
                f_res = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=5)
                st.text_area("Roh-Text Furka (Auszug):", f_res.text[:500], height=150)
            except Exception as e:
                st.error(f"Fehler Furka-Feed: {e}")

        with diag_col2:
            st.markdown("**Lötschberg (BLS API)**")
            try:
                l_res = requests.get("https://www.bls.ch/api/TrafficInformation/GetNewNotifications?sc_lang=de&sc_site=internet-bls", 
                                     headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                st.json(l_res.json().get("trafficInformations", []))
            except Exception as e:
                st.error(f"Fehler BLS-API: {e}")

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

# =====================================================================
# --- 7. GEMINI LAGEBERICHT GANZ ZUM SCHLUSS LADEN ---
# Hier greifen wir auf den Platzhalter von ganz oben zu.
# =====================================================================
with report_placeholder.container():
    # Während Gemini rechnet, zeigen wir einen schicken Lade-Spinner
    with st.spinner("🤖 KI analysiert die Verkehrslage..."):
        with sqlite3.connect(DB_NAME) as conn:
            df_trend = pd.read_sql_query(
                "SELECT timestamp, station, minutes FROM stats ORDER BY timestamp DESC LIMIT 40", 
                conn
            )
        
        report = get_gemini_situation_report(data, df_trend)
        
        # Sobald fertig, wird der Spinner durch die hübsche Info-Box ersetzt
        st.subheader("🤖 KI-Lagebericht")
        st.info(report)
