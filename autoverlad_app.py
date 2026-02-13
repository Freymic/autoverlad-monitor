import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- EINSTELLUNGEN ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="freshener")
DB_FILE = "wartezeiten_historie.csv"

def text_zu_minuten(text):
    """
    Übersetzt Textbausteine in echte Zahlen:
    '1 Stunde 30 Minuten' -> 90
    'keine Wartezeit' -> 0
    """
    if not text or "keine wartezeit" in text.lower():
        return 0
    
    gesamt_minuten = 0
    # Suche nach Stunden und multipliziere mit 60
    stunden_match = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if stunden_match:
        gesamt_minuten += int(stunden_match.group(1)) * 60
    
    # Suche nach Minuten und addiere sie
    minuten_match = re.search(r'(\d+)\s*(?:Minute|min)', text, re.IGNORECASE)
    if minuten_match:
        gesamt_minuten += int(minuten_match.group(1))
        
    return gesamt_minuten

def daten_abrufen():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # FURKA (MGB)
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        text_ganz = soup.get_text(separator=' ')
        
        # Wir isolieren den Bereich Verkehrsinformation, um nicht die Uhrzeit (z.B. 14 Min) zu fangen
        if "Verkehrsinformation" in text_ganz:
            info_teil = text_ganz.split("Verkehrsinformation")[-1].split("zuletzt aktualisiert")[0]
            
            for ort in ["Realp", "Oberwald"]:
                match = re.search(f"{ort}.{{0,150}}", info_teil, re.IGNORECASE)
                if match:
                    daten[ort] = text_zu_minuten(match.group(0))

        # LÖTSCHBERG (BLS)
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        bls_text = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for ort in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{ort}.{{0,150}}", bls_text, re.IGNORECASE)
            if match:
                daten[ort] = text_zu_minuten(match.group(0))
    except:
        pass
    return daten

# --- PROGRAMM-ABLAUF ---
aktuelle_werte = daten_abrufen()
jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
df_neu = pd.DataFrame([{"Zeit": jetzt, **aktuelle_werte}])
if not os.path.exists(DB_FILE):
    df_neu.to_csv(DB_FILE, index=False)
else:
    df_neu.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- ANZEIGE ---
st.title("🏔️ Autoverlad Monitor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- GRAFIK ---
st.divider()
if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))].sort_values('Zeit')
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

st.caption(f"Letzte Messung: {datetime.now().strftime('%H:%M:%S')} Uhr")
