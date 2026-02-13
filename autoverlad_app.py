import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Autoverlad Live (ASTRA)", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="api_refresh")
DB_FILE = "wartezeiten_historie.csv"

# DEIN OFFIZIELLER TOKEN
API_TOKEN = "eyJvcmciOiI2NDA2NTFhNTIyZmEwNTAwMDEyOWJiZTEiLCJpZCI6ImNlNjBiNTczNzRmNDQ3YjZiODUwZDA3ZTA5MmQ4ODk0IiwiaCI6Im11cm11cjEyOCJ9"

# DEINE HARDCODED ÜBERSETZUNG (0 Min bis 4 Stunden)
UEBERSETZUNG = {
    "4 stunden": 240, "3 stunden 45 minuten": 225, "3 stunden 30 minuten": 210,
    "3 stunden 15 minuten": 195, "3 stunden": 180, "2 stunden 45 minuten": 165,
    "2 stunden 30 minuten": 150, "2 stunden 15 minuten": 135, "2 stunden": 120,
    "1 stunde 45 minuten": 105, "1 stunde 30 minuten": 90, "1 stunde 15 minuten": 75,
    "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
    "keine wartezeit": 0
}

def text_zu_min(text):
    if not text: return 0
    text = text.lower()
    for phrase, mins in UEBERSETZUNG.items():
        if phrase in text:
            return mins
    return 0

def fetch_astra_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    # Offizieller OJP Situations Endpoint
    url = "https://api.opentransportdata.swiss/ojp-la-astra/v1/situations"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/xml"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            # Wir suchen alle Meldungen (SituationRecord)
            records = soup.find_all("situationRecord")
            
            for record in records:
                desc = record.find("description")
                if desc:
                    txt = desc.get_text()
                    # Zuweisung basierend auf Textinhalt
                    val = text_zu_min(txt)
                    if "Realp" in txt: daten["Realp"] = val
                    if "Oberwald" in txt: daten["Oberwald"] = val
                    if "Kandersteg" in txt: daten["Kandersteg"] = val
                    if "Goppenstein" in txt: daten["Goppenstein"] = val
        else:
            st.error(f"API Fehler: {response.status_code}")
    except Exception as e:
        st.error(f"Verbindungsfehler: {e}")
    return daten

# --- DATENVERARBEITUNG ---
werte = fetch_astra_data()
jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# In CSV loggen
df_new = pd.DataFrame([{"Zeit": jetzt, **werte}])
if not os.path.exists(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- DASHBOARD ---
st.title("🏔️ Autoverlad Live-Monitor")
st.markdown("Offizielle Live-Daten vom **Bundesamt für Strassen (ASTRA)**")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

# --- HISTORIE ---
st.divider()
if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    # Letzte 12 Stunden für bessere Übersicht
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))].sort_values('Zeit')
    
    if len(df) > 1:
        st.subheader("📈 Wartezeiten-Verlauf")
        # Wir nutzen das native Streamlit Chart (robuster als Altair bei Fehlern)
        st.line_chart(df.set_index('Zeit'))

st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")
