import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="fixed_refresh")
DB_FILE = "wartezeiten_historie.csv"

def uebersetze_text_zu_min(text):
    """Übersetzt exakte Textbausteine direkt in Minuten-Werte."""
    text = text.lower()
    
    # Die Map deckt den Bereich bis 4 Stunden ab
    uebersetzung = {
        "keine wartezeit": 0,
        "15 minuten": 15,
        "30 minuten": 30,
        "45 minuten": 45,
        "1 stunde": 60,
        "1 stunde 15 minuten": 75,
        "1 stunde 30 minuten": 90,
        "1 stunde 45 minuten": 105,
        "2 stunden": 120,
        "2 stunden 15 minuten": 135,
        "2 stunden 30 minuten": 150,
        "2 stunden 45 minuten": 165,
        "3 stunden": 180,
        "3 stunden 15 minuten": 195,
        "3 stunden 30 minuten": 210,
        "3 stunden 45 minuten": 225,
        "4 stunden": 240
    }
    
    for phrase, minuten in uebersetzung.items():
        if phrase in text:
            return minuten
    return 0

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # FURKA (MGB)
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        # Wir isolieren den Bereich zwischen 'Verkehrsinformation' und 'aktualisiert'
        raw = soup.get_text(separator=' ')
        clean_mgb = raw.split("Verkehrsinformation")[-1].split("zuletzt aktualisiert")[0]
        
        for loc in ["Realp", "Oberwald"]:
            if loc.lower() in clean_mgb.lower():
                # Wir schauen uns den Text direkt nach dem Ortsnamen an
                start_idx = clean_mgb.lower().find(loc.lower())
                snippet = clean_mgb[start_idx : start_idx + 150]
                daten[loc] = uebersetze_text_zu_min(snippet)

        # LÖTSCHBERG (BLS)
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        clean_bls = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            if loc.lower() in clean_bls.lower():
                start_idx = clean_bls.lower().find(loc.lower())
                snippet = clean_bls[start_idx : start_idx + 150]
                daten[loc] = uebersetze_text_zu_min(snippet)
    except:
        pass
    return daten

# --- LOGIK ---
werte = fetch_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# CSV Speichern
df_new = pd.DataFrame([{"Zeit": ts, **werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ---
st.title("🏔️ Autoverlad Monitor (Hardcoded)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

# --- CHART ---
st.divider()
if st.sidebar.button("🗑️ Daten löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))].sort_values('Zeit')
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

st.caption(f"Letzte Prüfung: {datetime.now().strftime('%H:%M:%S')} Uhr")
