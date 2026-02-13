import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="refresh_check")
DB_FILE = "wartezeiten_historie.csv"

def get_minutes(text):
    """Rechnet '1 Stunde 30 Minuten' in 90 Minuten um."""
    total = 0
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr: total += int(hr.group(1)) * 60
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn: total += int(mn.group(1))
    return total

def fetch_all():
    res = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # FURKA (MGB)
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        text = soup.get_text(separator=' ')
        
        # WICHTIG: Wir schneiden alles ab 'zuletzt aktualisiert' weg (verhindert die 14 Min!)
        if "Verkehrsinformation" in text:
            text = text.split("Verkehrsinformation")[-1]
        if "zuletzt aktualisiert" in text:
            text = text.split("zuletzt aktualisiert")[0]

        for loc in ["Realp", "Oberwald"]:
            match = re.search(f"{loc}.{{0,200}}", text, re.IGNORECASE)
            if match:
                s = match.group(0)
                if "keine" not in s.lower(): res[loc] = get_minutes(s)

        # LÖTSCHBERG (BLS)
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        t_l = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            m = re.search(f"{loc}.{{0,250}}", t_l, re.IGNORECASE)
            if m: res[loc] = get_minutes(m.group(0))
    except:
        pass
    return res

# --- LOGIK ---
werte = fetch_all()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
df_new = pd.DataFrame([{"Zeit": ts, **werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ---
st.title("🏔️ Autoverlad Live-Monitor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

# --- CHART ---
st.divider()
if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    try:
        df = pd.read_csv(DB_FILE).drop_duplicates()
        df['Zeit'] = pd.to_datetime(df['Zeit'])
        # Filter: Nur letzte 6h
        df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))].sort_values('Zeit')
        if len(df) > 1:
            st.subheader("📈 Verlauf")
            st.line_chart(df.set_index('Zeit'))
    except:
        st.write("Sammle Daten...")

st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} Uhr")
