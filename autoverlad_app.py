import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
st_autorefresh(interval=600000, key="global_refresh")
DB_FILE = "wartezeiten_historie.csv"

# Deine Hardcoded-Übersetzungstabelle
UEBERSETZUNG = {
    "4 stunden": 240,
    "3 stunden 45 minuten": 225,
    "3 stunden 30 minuten": 210,
    "3 stunden 15 minuten": 195,
    "3 stunden": 180,
    "2 stunden 45 minuten": 165,
    "2 stunden 30 minuten": 150,
    "2 stunden 15 minuten": 135,
    "2 stunden": 120,
    "1 stunde 45 minuten": 105,
    "1 stunde 30 minuten": 90,
    "1 stunde 15 minuten": 75,
    "1 stunde": 60,
    "45 minuten": 45,
    "30 minuten": 30,
    "15 minuten": 15,
    "keine wartezeit": 0
}

def finde_wartezeit_im_text(text_block):
    """Sucht im gesamten Block nach dem längstmöglichen passenden Baustein."""
    text_block = text_block.lower()
    # Wir sortieren die Liste nach Länge, damit '1 Stunde 30 Minuten' 
    # vor '1 Stunde' gefunden wird.
    for phrase in UEBERSETZUNG.keys():
        if phrase in text_block:
            return UEBERSETZUNG[phrase]
    return 0

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Wir suchen gezielt nach den Containern der Verladestationen
        # Die MGB Seite nutzt oft 'akkordeon' oder 'cards'
        cards = soup.find_all(lambda tag: tag.name == 'div' and ('Realp' in tag.text or 'Oberwald' in tag.text))
        
        for card in cards:
            card_text = card.get_text(separator=' ', strip=True)
            if "Realp" in card_text:
                daten["Realp"] = finde_wartezeit_im_text(card_text)
            if "Oberwald" in card_text:
                daten["Oberwald"] = finde_wartezeit_im_text(card_text)

        # --- LÖTSCHBERG (BLS) ---
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        bls_soup = BeautifulSoup(rl.content, 'html.parser')
        # BLS zeigt Wartezeiten oft in einer Tabelle oder Liste
        bls_text = bls_soup.get_text(separator=' ', strip=True)
        
        for loc in ["Kandersteg", "Goppenstein"]:
            # Suche Station und nimm einen großzügigen Bereich danach
            idx = bls_text.find(loc)
            if idx != -1:
                snippet = bls_text[idx:idx+200]
                daten[loc] = finde_wartezeit_im_text(snippet)
                
    except Exception as e:
        st.error(f"Fehler beim Abruf: {e}")
    return daten

# --- LOGIK & UI ---
werte = fetch_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
pd.DataFrame([{"Zeit": ts, **werte}]).to_csv(DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False)

st.title("🏔️ Autoverlad Live")
cols = st.columns(4)
for i, (name, val) in enumerate(werte.items()):
    cols[i].metric(name, f"{val} Min")

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Daten löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()
