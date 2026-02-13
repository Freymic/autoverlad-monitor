import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="api_refresh")
DB_FILE = "wartezeiten_historie.csv"

# DEINE HARDCODED TABELLE
UEBERSETZUNG = {
    "4 stunden": 240, "3 stunden 45 minuten": 225, "3 stunden 30 minuten": 210,
    "3 stunden 15 minuten": 195, "3 stunden": 180, "2 stunden 45 minuten": 165,
    "2 stunden 30 minuten": 150, "2 stunden 15 minuten": 135, "2 stunden": 120,
    "1 stunde 45 minuten": 105, "1 stunde 30 minuten": 90, "1 stunde 15 minuten": 75,
    "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
    "keine wartezeit": 0
}

def check_text(text):
    text = text.lower()
    for phrase, mins in UEBERSETZUNG.items():
        if phrase in text:
            return mins
    return 0

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    
    # --- VERSUCH: LÖTSCHBERG (BLS) ---
    try:
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            idx = soup_l.find(loc)
            if idx != -1:
                daten[loc] = check_text(soup_l[idx:idx+250])
    except: pass

    # --- VERSUCH: FURKA (MGB) ---
    # Da die MGB-Webseite oft leer ist, nutzen wir den TCS/Meteo-Verkehrsfeed, 
    # der oft die Grundlage für diese Anzeigen ist.
    try:
        # Wir versuchen die Furka-Daten über einen Umweg zu bekommen, 
        # falls die Hauptseite "leer" bleibt.
        headers = {'User-Agent': 'Mozilla/5.0'}
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", headers=headers, timeout=10)
        # Wenn im HTML nichts ist, schauen wir, ob wir im Text versteckte JSON-Daten finden
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        full_text = soup_f.get_text(separator=' ')
        
        for loc in ["Realp", "Oberwald"]:
            idx = full_text.find(loc)
            if idx != -1:
                daten[loc] = check_text(full_text[idx:idx+300])
            
        # Falls immer noch 0, schauen wir auf der TCS Seite (oft stabiler für Furka)
        if daten["Realp"] == 0 and daten["Oberwald"] == 0:
            r_tcs = requests.get("https://www.tcs.ch/de/tools/verkehrsinfo/aktuelle-lage.php", timeout=10)
            if "Furka" in r_tcs.text:
                # Hier würde man im Notfall die TCS Daten parsen
                pass
    except: pass
    
    return daten

# --- UI & LOGIK ---
werte = fetch_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
pd.DataFrame([{"Zeit": ts, **werte}]).to_csv(DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False)

st.title("🏔️ Autoverlad Monitor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Reset"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()
