import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Autoverlad Live (Official API)", layout="wide", page_icon="🏔️")
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

def fetch_astra_data():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    url = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"
    
    # Exakter Body aus dem Kochbuch
    soap_body = """<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <d2LogicalModel xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2" xmlns="http://datex2.eu/schema/2/2_0">
          <exchange>
            <supplierIdentification>
              <country>ch</country>
              <nationalIdentifier>FEDRO</nationalIdentifier>
            </supplierIdentification>
            <subscription>
              <operatingMode>operatingMode1</operatingMode>
              <subscriptionStartTime>2024-01-01T00:00:00Z</subscriptionStartTime>
              <subscriptionState>active</subscriptionState>
              <updateMethod>singleElementUpdate</updateMethod>
              <target>
                <address></address>
                <protocol>http</protocol>
              </target>
            </subscription>
          </exchange>
        </d2LogicalModel>
      </soap:Body>
    </soap:Envelope>"""
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "text/xml; charset=utf-8",
        # Exakte SoapAction laut Kochbuch
        "SOAPAction": "http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages"
    }
    
    try:
        response = requests.post(url, data=soap_body.encode('utf-8'), headers=headers, timeout=45)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            # In Datex-II können die Records namespaces haben (z.B. dx223:situationRecord)
            records = soup.find_all(lambda tag: "situationRecord" in tag.name)
            
            for record in records:
                # Suche nach dem Beschreibungsfeld (comment oder value)
                desc = record.find(lambda tag: "value" in tag.name or "comment" in tag.name)
                if desc:
                    txt = desc.get_text().lower()
                    val = text_zu_minuten(txt)
                    
                    if "realp" in txt: daten["Realp"] = max(daten["Realp"], val)
                    if "oberwald" in txt: daten["Oberwald"] = max(daten["Oberwald"], val)
                    if "kandersteg" in txt: daten["Kandersteg"] = max(daten["Kandersteg"], val)
                    if "goppenstein" in txt: daten["Goppenstein"] = max(daten["Goppenstein"], val)
        else:
            st.sidebar.error(f"Fehler: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
    return daten

# --- UI & LOGIK ---
werte = fetch_astra_data()
ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern
pd.DataFrame([{"Zeit": ts, **werte}]).to_csv(
    DB_FILE, mode='a', header=not os.path.exists(DB_FILE), index=False
)

st.title("🏔️ Autoverlad Live-Monitor (Official)")
st.caption("Datenquelle: ASTRA via opentransportdata.swiss (SOAP API)")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{werte['Realp']} Min")
c2.metric("Oberwald", f"{werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{werte['Goppenstein']} Min")

if os.path.exists(DB_FILE):
    df = pd.read_csv(DB_FILE).drop_duplicates().sort_values('Zeit')
    df['Zeit'] = pd.to_datetime(df['Zeit'])
    df = df[df['Zeit'] > (datetime.now() - timedelta(hours=12))]
    if len(df) > 1:
        st.line_chart(df.set_index('Zeit'))

if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()
