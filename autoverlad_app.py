import streamlit as st
import requests
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Furka Live-Monitor", layout="centered", page_icon="🏔️")
st_autorefresh(interval=300000, key="api_refresh")

def get_furka_status():
    """Holt die Wartezeiten direkt von der MGB-Statusseite."""
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'}
    
    res_data = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            text = response.text
            # Wir suchen im Quellcode nach dem JSON-Datenblock, den Contenthub dort ablegt
            # Diese Suche ist robuster als das Scrapen von sichtbarem Text
            for station in res_data.keys():
                # Suche nach "Oberwald" gefolgt von einer Zahl und "min" im gesamten Quelltext
                match = re.search(fr'{station}.*?(\d+)\s*min', text, re.IGNORECASE | re.DOTALL)
                if match:
                    res_data[station] = int(match.group(1))
    except:
        pass
    return res_data

# --- UI ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown("Direkte Abfrage der Matterhorn Gotthard Bahn")

# Echte Daten abrufen
status = get_furka_status()

# Simulation für den Test (falls aktuell 0 steht)
if st.sidebar.checkbox("Simulation (Wartezeit testen)"):
    status = {"Oberwald": 45, "Realp": 15}

c1, c2 = st.columns(2)

with c1:
    val = status["Oberwald"]
    st.metric("Wartezeit Oberwald", f"{val} Min")
    if val > 30:
        st.error("🚨 Starke Wartezeit!")
    elif val > 0:
        st.warning("⚠️ Wartezeit vorhanden")

with c2:
    val = status["Realp"]
    st.metric("Wartezeit Realp", f"{val} Min")
    if val > 30:
        st.error("🚨 Starke Wartezeit!")
    elif val > 0:
        st.warning("⚠️ Wartezeit vorhanden")

st.divider()
st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")

# Notfall-Link
st.sidebar.markdown("---")
st.sidebar.link_button("🌐 Offizielle MGB Webseite öffnen", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
