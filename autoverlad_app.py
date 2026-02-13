import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide")
st_autorefresh(interval=300000, key="refresh") # Alle 5 Min aktualisieren

def get_bls_wartezeit():
    """Scrapt die BLS-Webseite für Kandersteg und Goppenstein."""
    url = "https://www.bls.ch/de/fahren/autoverlad/fahrplan"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        # Suche nach den Texten in den typischen BLS-Elementen
        text = soup.get_text()
        kandersteg = 30 if "30 Min" in text and "Kandersteg" in text else 0
        goppenstein = 30 if "30 Min" in text and "Goppenstein" in text else 0
        # Hinweis: Das ist eine vereinfachte Logik, die wir verfeinern können
        return {"Kandersteg": kandersteg, "Goppenstein": goppenstein}
    except:
        return {"Kandersteg": "N/A", "Goppenstein": "N/A"}

def get_furka_wartezeit():
    """Scrapt die MGB-Webseite für Realp und Oberwald."""
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()
        realp = 30 if "30 Min" in text and "Realp" in text else 0
        oberwald = 30 if "30 Min" in text and "Oberwald" in text else 0
        return {"Realp": realp, "Oberwald": oberwald}
    except:
        return {"Realp": "N/A", "Oberwald": "N/A"}

# --- UI ---
st.title("🏔️ Autoverlad Realtime Monitor")
st.write("Datenquelle: Direkte Abfrage der Betreiber-Webseiten (BLS & MGB)")

furka = get_furka_wartezeit()
bls = get_bls_wartezeit()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{furka['Realp']} Min")
c2.metric("Oberwald", f"{furka['Oberwald']} Min")
c3.metric("Kandersteg", f"{bls['Kandersteg']} Min")
c4.metric("Goppenstein", f"{bls['Goppenstein']} Min")

st.info("Hinweis: Da keine offizielle API existiert, liest diese App die Informationen direkt von den Webseiten der Bahnbetreiber aus.")
