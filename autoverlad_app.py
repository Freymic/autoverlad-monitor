import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="refresh") # 10 Min
DB_FILE = "wartezeiten_historie.csv"

def extract_minutes(text_snippet):
    """Wandelt '1 Stunde 30 Minuten' sauber in 90 um."""
    mins = 0
    # Suche Stunden
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text_snippet, re.IGNORECASE)
    if hr:
        mins += int(hr.group(1)) * 60
    # Suche Minuten
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text_snippet, re.IGNORECASE)
    if mn:
        mins += int(mn.group(1))
    return mins

def fetch_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        # Wir trennen den Text hart bei den Schlüsselwörtern
        raw_text = r.text
        if "Verkehrsinformation" in raw_text:
            # Alles vor der Info weg
            content = raw_text.split("Verkehrsinformation")[1]
            if "zuletzt aktualisiert" in content:
                # Alles nach der Info (inkl. Uhrzeit) weg
                content = content.split("zuletzt aktualisiert")[0]
            
            # Jetzt säubern wir das HTML-Überbleibsel
            soup = BeautifulSoup(content, 'html.parser')
            clean_info = soup.get_text(separator=' ')

            for station in ["Realp", "Oberwald"]:
                # Suche Station im bereinigten Bereich
                match = re.search(f"{station}.{{0,300}}", clean_info, re.IGNORECASE)
                if match:
                    snippet = match.group(0)
                    if "keine Wartezeit" in snippet:
                        daten[station] = 0
                    else:
                        daten[station] = extract_minutes(snippet)

        # --- LÖTSCHBERG (BLS) ---
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        soup_l = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{station}.{{0,300}}", soup_l, re.IGNORECASE)
            if match:
                daten[station] = extract_minutes(match.group(0))
    except:
        pass
    return daten

# --- LOGIK ---
werte = fetch_data()
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
df_new = pd.DataFrame([{"Zeit": timestamp, **werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.info("Datenquelle: Offizielle Verkehrsinformationen")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

# --- GRAFIK ---
st.divider()
if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))]
    if len(df) > 1:
        chart = alt.Chart(df.melt('Zeit')).mark_line(point=True).encode(
            x=alt.X('Zeit:T', title='Uhrzeit'),
            y=alt.Y('value:Q', title='Wartezeit (Min)'),
            color='variable:N'
        ).properties(height=400).interactive()
        st.altair_chart(chart, use_container_width=True)
