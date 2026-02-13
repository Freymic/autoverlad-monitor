import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=600000, key="autoverlad_check") # Refresh alle 10 Min
DB_FILE = "wartezeiten_historie.csv"

def parse_time(text):
    """Rechnet Stunden und Minuten in Gesamtaufwand um."""
    total = 0
    found = False
    # Sucht nach '1 Stunde' oder '2 Stunden'
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr:
        total += int(hr.group(1)) * 60
        found = True
    # Sucht nach '30 Minuten'
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn:
        total += int(mn.group(1))
        found = True
    return total if found else 0

def get_data():
    results = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        resp = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        full_text = soup.get_text(separator=' ')
        
        # Wir isolieren den Bereich 'Verkehrsinformation' bis 'zuletzt aktualisiert'
        # Das verhindert, dass Uhrzeit-Zahlen (wie 14 Min) fälschlich gelesen werden
        clean_text = full_text
        if "Verkehrsinformation" in full_text:
            clean_text = full_text.split("Verkehrsinformation")[-1]
        if "zuletzt aktualisiert" in clean_text:
            clean_text = clean_text.split("zuletzt aktualisiert")[0]

        for loc in ["Realp", "Oberwald"]:
            # Suche im Umkreis der Station
            match = re.search(f"{loc}(.{{0,500}})", clean_text, re.IGNORECASE)
            if match:
                snippet = match.group(1)
                if "keine" in snippet.lower():
                    results[loc] = 0
                else:
                    results[loc] = parse_time(snippet)

        # --- LÖTSCHBERG (BLS) ---
        resp_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = BeautifulSoup(resp_l.content, 'html.parser').get_text(separator=' ')
        for loc in ["Kandersteg", "Goppenstein"]:
            m = re.search(f"{loc}(.{{0,400}})", text_l, re.IGNORECASE)
            if m:
                results[loc] = parse_time(m.group(1))
    except:
        pass
    return results

# --- 2. DATEN-VERARBEITUNG ---
aktuelle_werte = get_data()

# In CSV schreiben
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": timestamp, **aktuelle_werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. BENUTZEROBERFLÄCHE ---
st.title("🏔️ Autoverlad Live-Monitor")

# Anzeige der Kacheln
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- 4. GRAFIK ---
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    try:
        df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
        df['Zeit'] = pd.to_datetime(df['Zeit'])
        # Filter auf letzte 6 Stunden
        df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if len(df) > 1:
            df_m = df.melt('Zeit', var_name='Station', value_name='Minuten')
            chart = alt.Chart(df_m).mark_line(point=True).encode(
                x=alt.X('Zeit:T', title='Uhrzeit'),
                y=alt.Y('Minuten:Q', title='Wartezeit (Min)', scale=alt.Scale(domain=[0, 180])),
                color='Station:N'
            ).properties(height=400).interactive()
            st.altair_chart(chart, use_container_width=True)
    except:
        st.write("Warte auf weitere Datenpunkte...")

st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} Uhr")
