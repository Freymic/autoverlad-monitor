import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Furka Live-Check", page_icon="🏔️")
st_autorefresh(interval=300000, key="f_refresh")

def get_mgb_status():
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    results = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            # Wir nutzen BeautifulSoup, um gezielt nach Textbausteinen zu suchen
            soup = BeautifulSoup(response.text, "html.parser")
            all_text = soup.get_text(separator=' | ')
            
            for station in results.keys():
                # Suche nach dem Stationsnamen und der darauffolgenden Zeitangabe
                # Wir suchen nach Mustern wie 'Oberwald | ... | 30 Min'
                regex = rf"{station}.*?(\d+)\s*min"
                match = re.search(regex, all_text, re.IGNORECASE | re.DOTALL)
                
                if match:
                    results[station] = int(match.group(1))
                elif "keine wartezeit" in all_text.lower():
                    results[station] = 0
        return results
    except Exception as e:
        st.error(f"Verbindungsfehler zur MGB: {e}")
        return results

# --- UI DASHBOARD ---
st.title("🏔️ Furka Autoverlad Monitor")
st.markdown("Direktabfrage der MGB-Webseite")

status = get_mgb_status()

col1, col2 = st.columns(2)
with col1:
    st.metric("Abfahrt Oberwald", f"{status['Oberwald']} Min")
    if status['Oberwald'] >= 30:
        st.warning("⚠️ Wartezeit in Oberwald!")

with col2:
    st.metric("Abfahrt Realp", f"{status['Realp']} Min")
    if status['Realp'] >= 30:
        st.error("🚨 Starke Wartezeit in Realp!")

st.divider()
st.caption(f"Letzte Prüfung: {datetime.now().strftime('%H:%M:%S')} Uhr")

# HILFE ZUR FEHLERSUCHE
if status['Oberwald'] == 0 and status['Realp'] == 0:
    st.info("💡 Falls auf der Webseite aktuell Wartezeiten stehen, die App aber 0 anzeigt, werden die Daten vermutlich per JavaScript nachgeladen. In diesem Fall müssten wir einen 'Headless Browser' nutzen.")
