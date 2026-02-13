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
    """Extrahiert Stunden und Minuten und rechnet sie in Minuten um."""
    total_minutes = 0
    found = False
    
    # Suche nach '1 Stunde' oder '2 Stunden'
    hr_match = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr_match:
        total_minutes += int(hr_match.group(1)) * 60
        found = True
        
    # Suche nach '30 Minuten'
    min_match = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if min_match:
        total_minutes += int(min_match.group(1))
        found = True
            
    return total_minutes if found else 0

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        
        # Gezielte Suche: Wir nehmen nur den Text unter der Überschrift 'Verkehrsinformation'
        verkehrs_info_text = ""
        # Wir suchen nach dem h2-Tag 'Verkehrsinformation' oder einem Container, der diesen Text enthält
        container = soup_f.find(lambda tag: tag.name == "h2" and "Verkehrsinformation" in tag.text)
        if container:
            # Wir nehmen den Text des übergeordneten Bereichs, um alle Meldungen zu erfassen
            verkehrs_info_text = container.parent.get_text(separator=' ')
        else:
            # Fallback: Falls h2 nicht gefunden wird, suche großflächig nach dem Wort
            text_full = soup_f.get_text(separator=' ')
            if "Verkehrsinformation" in text_full:
                verkehrs_info_text = text_full.split("Verkehrsinformation")[-1].split("zuletzt aktualisiert")[0]

        # Analyse für Realp und Oberwald innerhalb der 'Verkehrsinformation'
        for station in ["Realp", "Oberwald"]:
            match = re.search(f"({station}.{{0,300}})", verkehrs_info_text, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                if "keine wartezeit" in kontext.lower():
                    daten[station] = 0
                else:
                    daten[station] = parse_time_string(kontext)

        # --- LÖTSCHBERG (BLS) ---
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
st.set_page_config(page_title="Autoverlad Monitor", layout="wide", page_icon="🏔️")
aktuelle_werte = fetch_wartezeiten()

# Daten in CSV speichern
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.isfile(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.write("Abfrage der offiziellen Verkehrsinformationen.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- 4. DIAGRAMM ---
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    try:
        df_hist = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
        df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
        df_plot = df_hist[df_hist['Zeit'] > (datetime.now() - timedelta(hours=6))]
        
        if len(df_plot) > 1:
            df_melted = df_plot.melt('Zeit', var_name='Ort', value_name='Wartezeit')
            chart = alt.Chart(df_melted).mark_line(point=True).encode(
                x=alt.X('Zeit:T', title='Uhrzeit', axis=alt.Axis(format='%H:%M')),
                y=alt.Y('Wartezeit:Q', title='Minuten Wartezeit', scale=alt.Scale(domain=[0, 150])),
                color=alt.Color('Ort:N', title='Station')
            ).properties(height=400).interactive()
            st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.error(f"Fehler beim Diagramm: {e}")

st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")
