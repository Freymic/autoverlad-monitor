import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live-Monitor (ASTRA)", layout="wide", page_icon="🏔️")
# Automatische Aktualisierung alle 10 Minuten
st_autorefresh(interval=600000, key="api_refresh_timer")
DB_FILE = "wartezeiten_historie.csv"

# Dein offizieller API-Token
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
    """Sucht nach definierten Zeitangaben im Text."""
    if not text: return 0
    text = text.lower()
    # Entferne Punkte (z.B. Min. -> Min), um Abkürzungen besser zu finden
    text = text.replace(".", "")
    for phrase, mins in UEBERSETZUNG.items():
        if phrase in text:
            return mins
    return 0

def fetch_astra_data():
    """Ruft Daten über die SOAP-Schnittstelle gemäß Kochbuch ab."""
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    url = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
    
    # Offizieller SOAP-Umschlag laut opentransportdata.swiss Kochbuch
    soap_body = """<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <d2LogicalModel xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2" xmlns="http://datex2.eu/schema/2/2_0">
          <exchange>
            <supplierIdentification>
              <country>ch</country>
              <nationalIdentifier>FEDRO</nationalIdentifier>
            </supplierIdentification>
          </exchange>
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
            # Nutzt lxml Parser (muss in requirements.txt stehen)
            soup = BeautifulSoup(response.content, "xml")
            records = soup.find_all(lambda tag: "situationRecord" in tag.name)
            
            st.sidebar.success(f"API verbunden: {len(records)} Meldungen gefunden.")
            
            for record in records:
                # Suche nach dem Beschreibungsfeld im XML
                desc = record.find(lambda tag: "value" in tag.name or "comment" in tag.name)
                if desc:
                    txt = desc.get_text()
                    val = text_zu_minuten(txt)
                    
                    # Diagnose-Ausgabe für relevante Orte
                    for loc in daten.keys():
                        if loc.lower() in txt.lower():
                            st.sidebar.info(f"Meldung für {loc}: {txt[:100]}...")
                            daten[loc] = max(daten[loc], val)
        else:
            st.sidebar.error(f"API Fehler: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
    return daten

# --- DATENVERARBEITUNG ---
aktuelle_werte = fetch_astra_data()
zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# In CSV loggen
pd.DataFrame([{"Zeit": zeitpunkt, **aktuelle_werte}]).to_csv(
    DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False
)

# --- UI DASHBOARD ---
st.title("🏔️ Autoverlad Live-Monitor (ASTRA)")
st.markdown("Offizielle Live-Daten via **opentransportdata.swiss**")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp (Furka)", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald (Furka)", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg (Lötschberg)", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein (Lötschberg)", f"{aktuelle_werte['Goppenstein']} Min")

# --- HISTORIE ---
st.divider()
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    # Filter auf letzte 12 Stunden
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))]
    
    if len(df) > 1:
        st.subheader("📈 Wartezeiten-Verlauf (letzte 12h)")
        st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")
