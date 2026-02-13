import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="refresh")
DB_FILE = "wartezeiten_historie.csv"

def uebersetze_wartezeit(text):
    """
    Wandelt Text in Minuten um:
    - 'keine Wartezeit' -> 0
    - '1 Stunde 30 Minuten' -> 90
    - '40 Minuten' -> 40
    """
    text = text.lower()
    if "keine wartezeit" in text:
        return 0
    
    minuten_total = 0
    # Suche Stunden (Stunde, Std, h)
    stunden_match = re.search(r'(\d+)\s*(?:stunde|std|h)', text)
    if stunden_match:
        minuten_total += int(stunden_match.group(1)) * 60
    
    # Suche Minuten (Minute, Min, m)
    minuten_match = re.search(r'(\d+)\s*(?:minute|min)', text)
    if minuten_match:
        minuten_total += int(minuten_match.group(1))
        
    return minuten_total

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        # Wir greifen nur den Text im Bereich 'Verkehrsinformation' ab
        seite_text = soup.get_text(separator=' ')
        
        # Sicherstellen, dass wir nicht im Footer landen (verhindert die "14 Min" aus der Uhrzeit)
        info_block = seite_text.split("Verkehrsinformation")[-1].split("zuletzt aktualisiert")[0]

        for station in ["Realp", "Oberwald"]:
            # Suche den Textabschnitt nach dem Stationsnamen
            match = re.search(f"{station}.{{0,150}}", info_block, re.IGNORECASE)
            if match:
                daten[station] = uebersetze_wartezeit(match.group(0))

        # --- LÖTSCHBERG (BLS) ---
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        bls_text = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{station}.{{0,150}}", bls_text, re.IGNORECASE)
            if match:
                daten[station] = uebersetze_wartezeit(match.group(0))
    except:
        pass
    return daten

# --- DATEN-LOGIK ---
werte = fetch_data()
zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
df_new = pd.DataFrame([{"Zeit": zeitpunkt, **werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- ANZEIGE ---
st.title("🏔️ Autoverlad Live-Monitor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

# --- HISTORIE ---
st.divider()
if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    # Nur letzte 6 Stunden für bessere Übersicht
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))].sort_values('Zeit')
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")
