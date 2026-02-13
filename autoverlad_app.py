import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- EINSTELLUNGEN ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
st_autorefresh(interval=600000, key="freshener")
DB_FILE = "wartezeiten_historie.csv"

def get_minutes_from_text(text):
    """Extrahiert Minuten und Stunden aus einem Textabschnitt."""
    total = 0
    # Suche nach Stunden
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr:
        total += int(hr.group(1)) * 60
    # Suche nach Minuten
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn:
        total += int(mn.group(1))
    return total

def fetch_live_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        text_all = soup.get_text(separator=' ')
        
        # Wir isolieren den Bereich 'Verkehrsinformation'
        if "Verkehrsinformation" in text_all:
            # Wir nehmen nur den Teil NACH 'Verkehrsinformation'
            info_part = text_all.split("Verkehrsinformation")[-1]
            # Wir schneiden alles ab 'zuletzt aktualisiert' weg (um die 14 Min zu vermeiden)
            info_part = info_part.split("zuletzt aktualisiert")[0]
            
            for station in ["Realp", "Oberwald"]:
                # Suche Station im bereinigten Text
                match = re.search(f"{station}.{{0,300}}", info_part, re.IGNORECASE)
                if match:
                    daten[station] = get_minutes_from_text(match.group(0))

        # --- LÖTSCHBERG (BLS) ---
        rl = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = BeautifulSoup(rl.content, 'html.parser').get_text(separator=' ')
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{station}.{{0,300}}", text_l, re.IGNORECASE)
            if match:
                daten[station] = get_minutes_from_text(match.group(0))
    except:
        pass
    return daten

# --- HAUPTPROGRAMM ---
aktuelle_werte = fetch_live_data()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern der Daten
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ANZEIGE ---
st.title("🏔️ Autoverlad Live-Monitor")
st.write(f"Abfrage läuft... (Letztes Update: {datetime.now().strftime('%H:%M:%S')})")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- HISTORIE ---
st.divider()
if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df_hist = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    # Nur die letzten 6 Stunden zeigen
    df_hist = df_hist[df_hist['Zeit'] > (datetime.now() - timedelta(hours=6))]
    
    if len(df_hist) > 1:
        df_melt = df_hist.melt('Zeit', var_name='Station', value_name='Minuten')
        chart = alt.Chart(df_melt).mark_line(point=True).encode(
            x=alt.X('Zeit:T', title='Uhrzeit'),
            y=alt.Y('Minuten:Q', title='Wartezeit (Min)'),
            color='Station:N'
        ).properties(height=400).interactive()
        st.altair_chart(chart, use_container_width=True)
