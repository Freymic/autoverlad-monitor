import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. SETUP ---
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

def parse_time_string(text):
    """Rechnet '1 Stunde 30 Minuten' präzise in 90 Minuten um."""
    total_minutes = 0
    found_time = False
    
    # 1. Suche nach Stunden (Stunde/h/Std)
    hr_match = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr_match:
        total_minutes += int(hr_match.group(1)) * 60
        found_time = True
        
    # 2. Suche nach Minuten (Minute/min/Min)
    min_match = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if min_match:
        total_minutes += int(min_match.group(1))
        found_time = True
    
    # 3. Nur wenn absolut keine Zeitwörter gefunden wurden, nimm die erste Zahl
    # Aber ignoriere Zahlen, die Teil eines Datums/Uhrzeit sein könnten (z.B. 2026, 18:07)
    if not found_time:
        all_numbers = re.findall(r'\b(\d{1,3})\b', text)
        for num in all_numbers:
            val = int(num)
            if 5 <= val <= 240: # Nur plausible Wartezeiten
                return val
            
    return total_minutes

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # FURKA (MGB)
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        # Wir entfernen das Datum/Zeit-Element am Ende der Seite, um Fehlinterpretationen zu vermeiden
        for footer in soup_f.find_all(['footer', 'span']):
            if "aktualisiert" in footer.text: footer.decompose()
        
        text_f = " ".join(soup_f.get_text(separator=' ').split())
        
        for station in ["Realp", "Oberwald"]:
            match = re.search(f"({station}.{{0,500}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                if "keine Wartezeit" in kontext.lower():
                    daten[station] = 0
                else:
                    daten[station] = parse_time_string(kontext)

        # LÖTSCHBERG (BLS)
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = " ".join(BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ').split())
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"({station}.{{0,400}})", text_l, re.IGNORECASE)
            if match:
                daten[station] = parse_time_string(match.group(1))
    except:
        pass
    return daten

# --- 2. LOGIK ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
aktuelle_werte = fetch_wartezeiten()

# Speichern
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.isfile(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI ---
st.title("🏔️ Autoverlad Monitor")

cols = st.columns(4)
for i, (name, val) in enumerate(aktuelle_werte.items()):
    cols[i].metric(name, f"{val} Min")

# --- 4. DIAGRAMM ---
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    try:
        df_hist = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
        df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
        df_plot = df_hist[df_hist['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if len(df_plot) > 1:
            df_melted = df_plot.melt('Zeit', var_name='Station', value_name='Wartezeit')
            chart = alt.Chart(df_melted).mark_line(point=True).encode(
                x=alt.X('Zeit:T', title='Uhrzeit', axis=alt.Axis(format='%H:%M')),
                y=alt.Y('Wartezeit:Q', title='Minuten', scale=alt.Scale(domain=[0, 180])),
                color='Station:N'
            ).properties(height=400).interactive()
            st.altair_chart(chart, use_container_width=True)
    except:
        st.error("Fehler beim Laden der Daten.")

st.caption(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")
