import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import random
from streamlit_autorefresh import st_autorefresh

# --- 1. REFRESH & SETUP ---
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

# --- 2. DATENABRUF ---
def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # Furka (MGB)
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=10)
        soup_f = BeautifulSoup(r_f.content, 'html.parser').get_text()
        if "Realp" in soup_f:
            if "90 Minuten" in soup_f: daten["Realp"] = 90
            elif "60 Minuten" in soup_f: daten["Realp"] = 60
            elif "30 Minuten" in soup_f: daten["Realp"] = 30
        
        # Lötschberg (BLS)
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text()
        if "Kandersteg" in soup_l and "30 Min" in soup_l: daten["Kandersteg"] = 30
        if "Goppenstein" in soup_l and "30 Min" in soup_l: daten["Goppenstein"] = 30
    except: pass
    return daten

def save_to_csv(neue_daten):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_new = pd.DataFrame([{"Zeit": now, **neue_daten}])
    if not os.path.isfile(DB_FILE):
        df_new.to_csv(DB_FILE, index=False)
    else:
        df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st.title("🏔️ Autoverlad Monitor")

# Sidebar für Aktionen
st.sidebar.header("🛠️ Admin Tools")
if st.sidebar.button("🧪 Testdaten generieren"):
    for i in range(1, 13): # Erzeugt 12 Datenpunkte (3 Stunden)
        test_time = (datetime.now() - timedelta(minutes=15*i)).strftime("%Y-%m-%d %H:%M:%S")
        test_data = {
            "Zeit": test_time,
            "Realp": random.choice([0, 30, 60]),
            "Oberwald": random.choice([0, 30]),
            "Kandersteg": random.choice([0, 30, 60]),
            "Goppenstein": random.choice([0, 30])
        }
        pd.DataFrame([test_data]).to_csv(DB_FILE, mode='a', header=not os.path.isfile(DB_FILE), index=False)
    st.sidebar.success("Testdaten hinzugefügt! Bitte Seite neu laden.")

if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        st.sidebar.warning("Datei gelöscht.")
        st.rerun()

# --- 4. PROGRAMMLOGIK ---
if st.button("🔄 Jetzt Daten abrufen (Refresh)"):
    aktuelle_werte = fetch_wartezeiten()
    save_to_csv(aktuelle_werte)
    st.success("Daten aktualisiert!")
else:
    aktuelle_werte = fetch_wartezeiten()
    save_to_csv(aktuelle_werte)

# --- 5. ANZEIGE ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    df_hist = pd.read_csv(DB_FILE).drop_duplicates()
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    cutoff = datetime.now() - timedelta(hours=6)
    df_plot = df_hist[df_hist['Zeit'] > cutoff].sort_values('Zeit')

    if not df_plot.empty:
        df_melted = df_plot.melt('Zeit', var_name='Station', value_name='Wartezeit')
        chart = alt.Chart(df_melted).mark_line(point=True, interpolate='monotone').encode(
            x=alt.X('Zeit:T', title='Uhrzeit', axis=alt.Axis(format='%H:%M', tickCount={'interval': 'minute', 'step': 30}, labelAngle=0)),
            y=alt.Y('Wartezeit:Q', title='Minuten', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('Station:N', title='Station'),
            tooltip=['Zeit:T', 'Station:N', 'Wartezeit:Q']
        ).properties(height=400).interactive()
        st.altair_chart(chart, use_container_width=True)
else:
    st.info("Noch keine Daten vorhanden.")

st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} Uhr")
