import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
st.set_page_config(page_title="Autoverlad Live (ASTRA API)", layout="wide", page_icon="🏔️")
st_autorefresh(interval=600000, key="api_refresh_timer")
DB_FILE = "wartezeiten_historie.csv"

# Dein offizieller API-Token von opentransportdata.swiss
API_TOKEN = "eyJvcmciOiI2NDA2NTFhNTIyZmEwNTAwMDEyOWJiZTEiLCJpZCI6ImNlNjBiNTczNzRmNDQ3YjZiODUwZDA3ZTA5MmQ4ODk0IiwiaCI6Im11cm11cjEyOCJ9"

# Deine Hardcoded-Übersetzungstabelle (0 Min bis 4 Stunden)
UEBERSETZUNG = {
    "4 stunden": 240, "3 stunden 45 minuten": 225, "3 stunden 30 minuten": 210,
    "3 stunden 15 minuten": 195, "3 stunden": 180, "2 stunden 45 minuten": 165,
    "2 stunden 30 minuten": 150, "2 stunden 15 minuten": 135, "2 stunden": 120,
    "1 stunde 45 minuten": 105, "1 stunde 30 minuten": 90, "1 stunde 15 minuten": 75,
    "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
    "keine wartezeit": 0
}

def text_zu_minuten(text):
    """Sucht nach den definierten Textbausteinen im API-Text."""
    if not text: return 0
    text = text.lower()
    for phrase, mins in UEBERSETZUNG.items():
        if phrase in text:
            return mins
    return 0

def fetch_astra_data():
    """Ruft die offiziellen Datex-II Verkehrsdaten vom ASTRA ab."""
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    
    # Korrekte URL für den Datex-II Pull (Traffic Situations)
    url = "https://api.opentransportdata.swiss/ojp-la-astra/v1/datex2/v2/situations"
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/xml"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "xml")
            # Suche alle Meldungen im Feed
            records = soup.find_all("situationRecord")
            
            for record in records:
                desc_tag = record.find("description")
                if desc_tag:
                    txt = desc_tag.get_text()
                    val = text_zu_minuten(txt)
                    
                    # Orte im Text identifizieren und höchsten Wert pro Ort speichern
                    if "Realp" in txt: daten["Realp"] = max(daten["Realp"], val)
                    if "Oberwald" in txt: daten["Oberwald"] = max(daten["Oberwald"], val)
                    if "Kandersteg" in txt: daten["Kandersteg"] = max(daten["Kandersteg"], val)
                    if "Goppenstein" in txt: daten["Goppenstein"] = max(daten["Goppenstein"], val)
        else:
            st.sidebar.error(f"API Fehler: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
    return daten

# --- DATEN-LOGIK ---
aktuelle_werte = fetch_astra_data()
zeitpunkt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Speichern der Daten in der CSV-Historie
df_neu = pd.DataFrame([{"Zeit": zeitpunkt, **aktuelle_werte}])
if not os.path.exists(DB_FILE):
    df_neu.to_csv(DB_FILE, index=False)
else:
    # Nur speichern, wenn sich Werte geändert haben oder nach Zeitablauf (optional)
    df_neu.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- DASHBOARD UI ---
st.title("🏔️ Autoverlad Live-Monitor")
st.markdown("Echtzeit-Daten vom **Bundesamt für Strassen (ASTRA)**")

# Anzeige der aktuellen Wartezeiten in 4 Spalten
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- HISTORIE GRAPH ---
st.divider()
st.subheader("📈 Wartezeiten-Verlauf (letzte 12 Stunden)")

if st.sidebar.button("🗑️ Verlauf löschen"):
    if os.path.exists(DB_FILE): 
        os.remove(DB_FILE)
    st.rerun()

if os.path.exists(DB_FILE):
    try:
        df = pd.read_csv(DB_FILE)
        df['Zeit'] = pd.to_datetime(df['Zeit'])
        # Dubletten entfernen und nach Zeit sortieren
        df = df.drop_duplicates().sort_values('Zeit')
        
        # Filter auf die letzten 12 Stunden
        limit = datetime.now() - timedelta(hours=12)
        df_display = df[df['Zeit'] > limit]
        
        if not df_display.empty:
            # Diagramm anzeigen
            st.line_chart(df_display.set_index('Zeit'))
        else:
            st.info("Noch keine Daten für den gewählten Zeitraum vorhanden.")
    except Exception as e:
        st.error(f"Fehler beim Laden der Grafik: {e}")

st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} Uhr | Datenquelle: opentransportdata.swiss")
