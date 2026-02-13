import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="auto_refresh_job")
DB_FILE = "wartezeiten_historie.csv"

def parse_time(text):
    """Rechnet '1 Stunde 30 Minuten' in 90 Minuten um."""
    mins = 0
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr: mins += int(hr.group(1)) * 60
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn: mins += int(mn.group(1))
    return mins

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        text = soup.get_text(separator=' ')
        
        # Wir isolieren den Bereich 'Verkehrsinformation' bis 'aktualisiert'
        if "Verkehrsinformation" in text:
            text = text.split("Verkehrsinformation")[-1]
        if "aktualisiert" in text:
            text = text.split("aktualisiert")[0]

        for loc in ["Realp", "Oberwald"]:
            match = re.search(f"{loc}.{{0,200}}", text, re.IGNORECASE)
            if match:
                snippet = match.group(0)
                if "keine" not in snippet.lower():
                    daten[loc] = parse_time(snippet)

        # --- LÖTSCHBERG (BLS) ---
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{loc}.{{0,250}}", text_l, re.IGNORECASE)
            if match: daten[loc] = parse_time(match.group(0))
    except:
        pass
    return daten

# --- HAUPTLOGIK ---
aktuelle_werte = fetch_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern für das Diagramm
df_new = pd.DataFrame([{"Zeit": ts, **aktuelle_werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ANZEIGE ---
st.title("🏔️ Autoverlad Live-Monitor")
cols = st.columns(4)
for i, (name, val) in enumerate(aktuelle_werte.items()):
    cols[i].metric(name, f"{val} Min")

# --- DIAGRAMM ---
st.divider()
if st.sidebar.button("🗑️ Verlauf zurücksetzen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    try:
        df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
        df['Zeit'] = pd.to_datetime(df['Zeit'])
        # Nur letzte 6h anzeigen
        df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if len(df) > 1:
            st.subheader("📈 Verlauf (letzte 6 Stunden)")
            df_plot = df.melt('Zeit', var_name='Station', value_name='Minuten')
            st.line_chart(df.set_index('Zeit'))
    except:
        st.info("Sammle erste Datenpunkte...")

st.caption(f"Letzte Messung: {datetime.now().strftime('%H:%M:%S')} Uhr")
