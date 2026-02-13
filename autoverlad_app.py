import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live-Monitor (ASTRA)", layout="wide", page_icon="🏔️")
# Automatische Aktualisierung alle 10 Minuten
st_autorefresh(interval=600000, key="api_refresh_timer")

DB_FILE = "wartezeiten_historie.csv"
# Dein offizieller API-Token
API_TOKEN = "eyJvcmciOiI2NDA2NTFhNTIyZmEwNTAwMDEyOWJiZTEiLCJpZCI6ImNlNjBiNTczNzRmNDQ3YjZiODUwZDA3ZTA5MmQ4ODk0IiwiaCI6Im11cm11cjEyOCJ9"

def extrahiere_minuten(text):
    """Extrahiert Zahlen für Stunden und Minuten aus dem Text."""
    text = text.lower()
    total = 0
    # Suche nach Stunden (z.B. "1 Stunde")
    stunden_match = re.search(r'(\d+)\s*stunde', text)
    # Suche nach Minuten (z.B. "45 Minuten" oder "45 min")
    minuten_match = re.search(r'(\d+)\s*min', text)
    
    if stunden_match:
        total += int(stunden_match.group(1)) * 60
    if minuten_match:
        total += int(minuten_match.group(1))
    return total

def fetch_astra_data():
    """Ruft Daten über die SOAP-Schnittstelle ab und zählt Treffer pro Ort."""
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    treffer_zaehler = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    
    url = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
    
    # SOAP-Body gemäß opentransportdata.swiss Kochbuch
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
            soup = BeautifulSoup(response.content, "xml")
            # Suche alle situationRecord Tags (beachtet Namespaces)
            records = soup.find_all(lambda tag: "situationRecord" in tag.name)
            
            st.sidebar.success(f"API verbunden: {len(records)} Meldungen")
            
            for record in records:
                # Suche nach Textinhalten (value oder comment Tags)
                desc = record.find(lambda tag: "value" in tag.name or "comment" in tag.name)
                if desc:
                    txt = desc.get_text()
                    low_txt = txt.lower()
                    
                    for loc in daten.keys():
                        if loc.lower() in low_txt:
                            treffer_zaehler[loc] += 1
                            wartezeit = extrahiere_minuten(low_txt)
                            daten[loc] = max(daten[loc], wartezeit)
            
            # Anzeige der Statistik in der Sidebar
            st.sidebar.markdown("### Treffer pro Ort:")
            for loc, count in treffer_zaehler.items():
                if count > 0:
                    st.sidebar.info(f"📍 {loc}: {count} Meldung(en)")
                else:
                    st.sidebar.write(f"⚪ {loc}: 0")
        else:
            st.sidebar.error(f"API Fehler: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
    
    return daten

# --- HAUPTPROGRAMM ---
aktuelle_werte = fetch_astra_data()
zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Daten in CSV speichern
pd.DataFrame([{"Zeit": zeitpunkt, **aktuelle_werte}]).to_csv(
    DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False
)

# --- DASHBOARD UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.markdown("Echtzeit-Verkehrsdaten vom **Bundesamt für Strassen (ASTRA)**")

# Kacheln für aktuelle Werte
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# Historie Graph
st.divider()
if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates()
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    # Filter auf letzte 12 Stunden
    df_display = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))].sort_values('Zeit')
    
    if len(df_display) > 1:
        st.subheader("📈 Wartezeiten-Verlauf (letzte 12h)")
        st.line_chart(df_display.set_index('Zeit'))

# Sidebar Tools
if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} Uhr | Quelle: opentransportdata.swiss")
