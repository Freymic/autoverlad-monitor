import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="auto_refresh_job")
DB_FILE = "wartezeiten_historie.csv"

def get_minutes(text):
    """Rechnet '1 Stunde 30 Minuten' in 90 Minuten um."""
    total = 0
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr: total += int(hr.group(1)) * 60
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn: total += int(mn.group(1))
    return total

def fetch_mgb():
    """Holt Daten speziell aus dem Bereich Verkehrsinformation."""
    res = {"Realp": 0, "Oberwald": 0}
    try:
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Wir suchen alle Info-Boxen auf der Seite
        info_boxes = soup.find_all(text=re.compile(r'Verladestation|Wartezeit', re.IGNORECASE))
        
        # Wir fügen den Text aller relevanten Boxen zusammen, aber stoppen vor dem Footer
        relevant_text = ""
        for box in info_boxes:
            parent_text = box.parent.get_text()
            if "aktualisiert" not in parent_text: # Footer ignorieren
                relevant_text += " " + parent_text

        for loc in ["Realp", "Oberwald"]:
            # Suche im Umkreis der Station nach Zeitangaben
            match = re.search(f"{loc}.{{0,200}}", relevant_text, re.IGNORECASE)
            if match:
                snippet = match.group(0)
                if "keine" not in snippet.lower():
                    res[loc] = get_minutes(snippet)
    except:
        pass
    return res

def fetch_bls():
    """Holt Daten vom Lötschberg."""
    res = {"Kandersteg": 0, "Goppenstein": 0}
    try:
        r = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text = BeautifulSoup(r.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{loc}.{{0,250}}", text, re.IGNORECASE)
            if match: res[loc] = get_minutes(match.group(0))
    except:
        pass
    return res

# --- LOGIK ---
mgb, bls = fetch_mgb(), fetch_bls()
current = {**mgb, **bls}

# Speichern
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": ts, "Station": k, "Wartezeit": v} for k, v in current.items()])

if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.subheader("Aktuelle Wartezeiten (Verkehrsinformation)")

cols = st.columns(4)
for i, (name, val) in enumerate(current.items()):
    cols[i].metric(name, f"{val} Min")

# --- CHART ---
st.divider()
if st.sidebar.button("🗑️ Verlauf zurücksetzen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    try:
        df = pd.read_csv(DB_FILE)
        df['Zeit'] = pd.to_datetime(df['Zeit'])
        # Nur letzte 6h
        df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if not df.empty:
            st.line_chart(df.pivot(index='Zeit', columns='Station', values='Wartezeit'))
    except:
        st.info("Sammle erste Daten...")

st.caption(f"Letzte Messung: {datetime.now().strftime('%H:%M:%S')} Uhr")
