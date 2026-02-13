import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. SETUP ---
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # FURKA (MGB)
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        text_f = " ".join(soup_f.get_text(separator=' ').split())
        
        for station in ["Realp", "Oberwald"]:
            match = re.search(f"(.{{0,500}}{station}.{{0,500}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                zahlen = re.findall(r'(\d+)', kontext)
                # Wir nehmen die erste Zahl, die im Kontext der Station auftaucht
                if zahlen:
                    val = int(zahlen[0])
                    # Plausibilitätscheck: Nur Werte zwischen 5 und 240 Min
                    if 5 <= val <= 240: daten[station] = val

        # LÖTSCHBERG (BLS)
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = " ".join(BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ').split())
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"(.{{0,400}}{station}.{{0,400}})", text_l, re.IGNORECASE)
            if match:
                zahlen = re.findall(r'(\d+)', match.group(1))
                if zahlen: daten[station] = int(zahlen[0])
    except:
        pass
    return daten

# --- 2. DATEN-LOGIK ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
aktuelle_werte = fetch_wartezeiten()

# Speichern
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.isfile(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI ---
st.title("🏔️ Autoverlad Live-Monitor")

# Die Kacheln (Metriken)
cols = st.columns(4)
stationen_liste = list(aktuelle_werte.keys())
for i, station in enumerate(stationen_liste):
    cols[i].metric(station, f"{aktuelle_werte[station]} Min")

# --- 4. DIAGRAMM ---
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    try:
        df_hist = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
        df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
        df_plot = df_hist[df_hist['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if len(df_plot) > 1:
            df_melted = df_plot.melt('Zeit', var_name='Station', value_name='Wartezeit')
            chart = alt.Chart(df_melted).mark_line(point=True).encode(
                x=alt.X('Zeit:T', title='Uhrzeit', axis=alt.Axis(format='%H:%M')),
                y=alt.Y('Wartezeit:Q', title='Minuten', scale=alt.Scale(domain=[0, 120])),
                color='Station:N'
            ).properties(height=400).interactive()
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Sammle Daten für das Diagramm...")
    except:
        st.error("Fehler beim Laden der Historie.")

st.caption(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")
