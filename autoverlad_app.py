import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    debug_info = {}
    
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        # Wir holen den Text und löschen überflüssige Leerzeichen/Umbrüche
        text_f = " ".join(BeautifulSoup(r_f.content, 'html.parser').get_text(separator=' ').split())
        debug_info['Furka_Raw'] = text_f[:1000] # Die ersten 1000 Zeichen für die Sidebar
        
        for station in ["Realp", "Oberwald"]:
            # Suche nach dem Stationsnamen und nimm 300 Zeichen davor und danach
            match = re.search(f"(.{{0,300}}{station}.{{0,300}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                # Wir suchen nach Zahlen, die vor 'Min' oder 'Std' stehen
                zahlen = re.findall(r'(\d+)\s*(?:Min|min|Minuten|h|Std)', kontext)
                if zahlen:
                    daten[station] = int(zahlen[0])
                debug_info[f'Kontext_{station}'] = kontext

        # --- LÖTSCHBERG (BLS) ---
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = " ".join(BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ').split())
        
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"(.{{0,300}}{station}.{{0,300}})", text_l, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                zahlen = re.findall(r'(\d+)\s*(?:Min|min|h|Std)', kontext)
                if zahlen:
                    daten[station] = int(zahlen[0])

    except Exception as e:
        st.error(f"Fehler beim Scraping: {e}")
        
    return daten, debug_info

# --- UI ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
aktuelle_werte, debug_data = fetch_wartezeiten()

# Speichern
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.isfile(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

st.title("🏔️ Autoverlad Live-Monitor")

# Metriken
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# --- DEBUG SIDEBAR ---
with st.sidebar:
    st.header("🔍 Debug-Modus
