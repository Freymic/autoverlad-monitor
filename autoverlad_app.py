import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Autoverlad Live (ASTRA SOAP)", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="api_refresh_timer")
DB_FILE = "wartezeiten_historie.csv"

# Dein Token
API_TOKEN = "eyJvcmciOiI2NDA2NTFhNTIyZmEwNTAwMDEyOWJiZTEiLCJpZCI6ImNlNjBiNTczNzRmNDQ3YjZiODUwZDA3ZTA5MmQ4ODk0IiwiaCI6Im11cm11cjEyOCJ9"

# Deine Hardcoded-Übersetzungstabelle
UEBERSETZUNG = {
    "4 stunden": 240, "3 stunden 45 minuten": 225, "3 stunden 30 minuten": 210,
    "3 stunden 15 minuten": 195, "3 stunden": 180, "2 stunden 45 minuten": 165,
    "2 stunden 30 minuten": 150, "2 stunden 15 minuten": 135, "2 stunden": 120,
    "1 stunde 45 minuten": 105, "1 stunde 30 minuten": 90, "1 stunde 15 minuten": 75,
    "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
    "keine wartezeit": 0
}

def text_zu_minuten(text):
    if not text: return 0
    text = text.lower()
    for phrase, mins in UEBERSETZUNG.items():
        if phrase in text:
            return mins
    return 0

def fetch_astra_soap():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    url = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
    
    # Der SOAP-Umschlag (Envelope), den die API erwartet
    soap_body = """<v2:pullSituationsRequest xmlns:v2="http://datex2.eu/schema/2/2_0"/>"""
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/xml; charset=utf-8",
        "User-Agent": "StreamlitAutoverlad/1.0"
    }
    
    try:
        # Wir senden einen POST-Request statt GET, da es SOAP ist
        response = requests.post(url, data=soap_body, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            records = soup.find_all("situationRecord")
            
            for record in records:
                desc_tag = record.find("description")
                if desc_tag:
                    txt = desc_tag.get_text().lower()
                    val = text_zu_minuten(txt)
                    
                    if "realp" in txt: daten["Realp"] = max(daten["Realp"], val)
                    if "oberwald" in txt: daten["Oberwald"] = max(daten["Oberwald"], val)
                    if "kandersteg" in txt: daten["Kandersteg"] = max(daten["Kandersteg"], val)
                    if "goppenstein" in txt: daten["Goppenstein"] = max(daten["Goppenstein"], val)
        else:
            st.sidebar.error(f"SOAP Fehler: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
    return daten

# --- MAIN ---
aktuelle_werte = fetch_astra_soap()
zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
pd.DataFrame([{"Zeit": zeitpunkt, **aktuelle_werte}]).to_csv(
    DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False
)

st.title("🏔️ Autoverlad Live-Monitor (Pro)")
st.caption("Datenquelle: ASTRA via opentransportdata.swiss (SOAP Pull)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# Verlauf
st.divider()
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))]
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()
