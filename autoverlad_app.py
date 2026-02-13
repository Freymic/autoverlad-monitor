import streamlit as st
import requests
import re
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Autoverlad Live", layout="centered", page_icon="🏔️")
# Automatische Aktualisierung alle 5 Minuten (300.000 ms)
st_autorefresh(interval=300000, key="furka_refresh")

def get_furka_minuten():
    """Holt die exakte Minutenzahl direkt aus dem MGB-Datenstrom."""
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'}
    res_data = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.post(url, headers=headers, timeout=10) # Post/Get je nach Server-Akzeptanz
        if response.status_code == 200:
            # Säubere den Quelltext von unnötigen Leerzeichen/Tags für stabilere Suche
            clean_text = " ".join(response.text.split())
            
            for station in res_data.keys():
                # Suche nach 'Station' gefolgt von Zahlen und 'min'
                match = re.search(fr'{station}.*?(\d+)\s*min', clean_text, re.IGNORECASE)
                if match:
                    res_data[station] = int(match.group(1))
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
        
    return res_data

# --- BENUTZEROBERFLÄCHE (UI) ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown("Echtzeit-Abfrage der **Matterhorn Gotthard Bahn (MGB)**")

# Daten abrufen
status = get_furka_minuten()

# Simulations-Modus in der Sidebar
st.sidebar.title("Einstellungen")
if st.sidebar.checkbox("Simulation (Wartezeit testen)"):
    status = {"Oberwald": 45, "Realp": 15}
    st.sidebar.info("Simulationsmodus aktiv")

# Anzeige der Metriken
c1, c2 = st.columns(2)

with c1:
    val_o = status["Oberwald"]
    st.metric("Wartezeit Oberwald", f"{val_o} Min")
    if val_o >= 45:
        st.error("🚨 Starke Wartezeit (über 45 Min)")
    elif val_o >= 15:
        st.warning("⚠️ Wartezeit vorhanden")
    else:
        st.success("✅ Freie Fahrt")

with c2:
    val_r = status["Realp"]
    st.metric("Wartezeit Realp", f"{val_r} Min")
    if val_r >= 45:
        st.error("🚨 Starke Wartezeit (über 45 Min)")
    elif val_r >= 15:
        st.warning("⚠️ Wartezeit vorhanden")
    else:
        st.success("✅ Freie Fahrt")

# Zeitstempel und Info
st.divider()
st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")

# Link zur offiziellen Quelle
st.sidebar.markdown("---")
st.sidebar.link_button("🌐 Offizielle MGB Webseite", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")

# Debug-Info (nur sichtbar wenn aufgeklappt)
with st.expander("Technisches Protokoll"):
    st.write("Aktuelle Rohdaten-Werte:", status)
    st.write("Gefundene Informationen basieren auf der Metadaten-Analyse.")
