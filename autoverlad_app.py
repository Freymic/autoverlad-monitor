import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st_autorefresh(interval=600000, key="auto_refresh_job")
DB_FILE = "wartezeiten_historie.csv"

def parse_duration(text):
    """Rechnet '1 Stunde 30 Minuten' in 90 Minuten um."""
    total = 0
    # Suche Stunden (Stunde/h/Std)
    hr = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr:
        total += int(hr.group(1)) * 60
    # Suche Minuten (Minute/min/Min)
    mn = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if mn:
        total += int(mn.group(1))
    return total

def get_mgb_data():
    """Spezifischer Abruf für Furka (Realp/Oberwald)."""
    data = {"Realp": 0, "Oberwald": 0}
    try:
        r = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # 1. Wir suchen die Überschrift 'Verkehrsinformation'
        header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "Verkehrsinformation" in tag.text)
        if header:
            # 2. Wir nehmen den gesamten Textbereich danach bis zum Ende der Info-Boxen
            # Wir stoppen vor 'zuletzt aktualisiert', um falsche Uhrzeiten zu vermeiden
            container_text = header.parent.get_text(separator=' ')
            if "zuletzt aktualisiert" in container_text:
                container_text = container_text.split("zuletzt aktualisiert")[0]
            
            for station in ["Realp", "Oberwald"]:
                # Suche Station und die nächsten 300 Zeichen Text
                match = re.search(f"{station}.{{0,300}}", container_text, re.IGNORECASE)
                if match:
                    snippet = match.group(0)
                    if "keine Wartezeit" in snippet:
                        data[station] = 0
                    else:
                        data[station] = parse_duration(snippet)
    except:
        pass
    return data

def get_bls_data():
    """Abruf für Lötschberg (Kandersteg/Goppenstein)."""
    data = {"Kandersteg": 0, "Goppenstein": 0}
    try:
        r = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        text = soup.get_text(separator=' ')
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{station}.{{0,300}}", text, re.IGNORECASE)
            if match:
                data[station] = parse_duration(match.group(0))
    except:
        pass
    return data

# --- HAUPTTEIL ---
# Daten abrufen
furka = get_mgb_data()
loetschberg = get_bls_data()
alle_werte = {**furka, **loetschberg}

# Speichern
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
new_row = pd.DataFrame([{"Zeit": timestamp, **alle_werte}])
if not os.path.exists(DB_FILE):
    new_row.to_csv(DB_FILE, index=False)
else:
    new_row.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.markdown("**Nur offizielle Verkehrsinformationen unter 'Verkehrsinformation' berücksichtigt.**")

# Kacheln anzeigen
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{alle_werte['Realp']} Min")
c2.metric("Oberwald", f"{alle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{alle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{alle_werte['Goppenstein']} Min")

# Verlauf
st.divider()
if st.sidebar.button("🗑️ Verlauf zurücksetzen"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=6))]
    if len(df) > 1:
        st.subheader("📈 Verlauf (letzte 6 Stunden)")
        chart = alt.Chart(df.melt('Zeit')).mark_line(point=True).encode(
            x=alt.X('Zeit:T', title='Uhrzeit'),
            y=alt.Y('value:Q', title='Wartezeit (Min)'),
            color=alt.Color('variable:N', title='Station')
        ).properties(height=400).interactive()
        st.altair_chart(chart, use_container_width=True)

st.caption(f"Letzte Prüfung: {datetime.now().strftime('%H:%M:%S')} Uhr")
