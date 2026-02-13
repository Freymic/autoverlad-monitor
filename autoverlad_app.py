import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="api_refresh")
DB_FILE = "wartezeiten_historie.csv"
API_TOKEN = "eyJvcmciOiI2NDA2NTFhNTIyZmEwNTAwMDEyOWJiZTEiLCJpZCI6ImNlNjBiNTczNzRmNDQ3YjZiODUwZDA3ZTA5MmQ4ODk0IiwiaCI6Im11cm11cjEyOCJ9"

def extrahiere_minuten(text):
    """Extrahiert Minuten/Stunden flexibel aus dem Text."""
    text = text.lower()
    # Suche nach Stunden
    stunden_match = re.search(r'(\d+)\s*stunde', text)
    # Suche nach Minuten
    minuten_match = re.search(r'(\d+)\s*min', text)
    
    total = 0
    if stunden_match:
        total += int(stunden_match.group(1)) * 60
    if minuten_match:
        total += int(minuten_match.group(1))
    
    return total if total > 0 else 0

def fetch_astra_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    url = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
    
    soap_body = """<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <d2LogicalModel xmlns="http://datex2.eu/schema/2/2_0">
          <exchange><supplierIdentification><country>ch</country><nationalIdentifier>FEDRO</nationalIdentifier></supplierIdentification></exchange>
        </d2LogicalModel>
      </soap:Body>
    </soap:Envelope>"""
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages"
    }
    
    try:
        response = requests.post(url, data=soap_body.encode('utf-8'), headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            records = soup.find_all(lambda tag: "situationRecord" in tag.name)
            st.sidebar.success(f"Verbunden: {len(records)} Meldungen")
            
            for record in records:
                desc = record.find(lambda tag: "value" in tag.name or "comment" in tag.name)
                if desc:
                    txt = desc.get_text()
                    low_txt = txt.lower()
                    
                    # Orte prüfen
                    for loc in daten.keys():
                        if loc.lower() in low_txt:
                            # Wir haben eine Meldung für den Ort gefunden!
                            wartezeit = extrahiere_minuten(low_txt)
                            daten[loc] = max(daten[loc], wartezeit)
                            # Diagnose-Log
                            st.sidebar.info(f"Gefunden für {loc}: {txt[:60]}...")
    except Exception as e:
        st.sidebar.error(f"Fehler: {e}")
    return daten

# --- UI LOGIK ---
aktuelle_werte = fetch_astra_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
df_row = pd.DataFrame([{"Zeit": ts, **aktuelle_werte}])
df_row.to_csv(DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False)

st.title("🏔️ Autoverlad Live-Monitor")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))].sort_values('Zeit')
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()
