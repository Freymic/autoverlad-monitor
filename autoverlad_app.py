import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Autoverlad Live", page_icon="🏔️")
st_autorefresh(interval=300000, key="furka_refresh") # Alle 5 Min

def extract_minutes(text):
    """Sucht nach Mustern wie '30 Min', '1 Std', 'keine Wartezeit'."""
    text = text.lower()
    if "keine wartezeit" in text or "0 min" in text:
        return 0
    
    # Suche nach 'X Std' und 'Y Min'
    hours = re.search(r'(\d+)\s*std', text)
    mins = re.search(r'(\d+)\s*min', text)
    
    total = 0
    if hours: total += int(hours.group(1)) * 60
    if mins: total += int(mins.group(1))
    return total

def get_furka_data():
    """Liest die offizielle MGB-Webseite für Furka-Wartezeiten aus."""
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    results = {"Oberwald": "Unbekannt", "Realp": "Unbekannt"}
    
    try:
        # User-Agent simulieren, um nicht blockiert zu werden
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Wir suchen nach den spezifischen Textblöcken auf der Seite
            # Die MGB nutzt oft Listen oder Tabellen für die Bahnhöfe
            page_content = soup.get_text(separator=' ')
            
            # Suche nach Abschnitten, die den Bahnhofnamen enthalten
            for station in results.keys():
                # Wir suchen den Textbereich um den Stationsnamen herum (ca. 200 Zeichen danach)
                pattern = f"{station}.*?(\d+\s*min|\d+\s*std|keine wartezeit)"
                match = re.search(pattern, page_content, re.IGNORECASE | re.DOTALL)
                
                if match:
                    results[station] = extract_minutes(match.group(0))
                else:
                    results[station] = 0 # Standardmäßig 0, wenn nichts gefunden
        return results
    except Exception as e:
        return {"Oberwald": f"Fehler: {e}", "Realp": "Fehler"}

# --- UI ---
st.title("🏔️ Autoverlad Furka: Live-Status")
st.subheader("Echtzeit-Abfrage der Matterhorn Gotthard Bahn")

data = get_furka_data()

col1, col2 = st.columns(2)

with col1:
    st.metric("Oberwald", f"{data['Oberwald']} Min")
    if isinstance(data['Oberwald'], int) and data['Oberwald'] > 30:
        st.warning("Erhöhtes Verkehrsaufkommen in Oberwald!")

with col2:
    st.metric("Realp", f"{data['Realp']} Min")
    if isinstance(data['Realp'], int) and data['Realp'] > 30:
        st.warning("Erhöhtes Verkehrsaufkommen in Realp!")

st.divider()
st.write(f"Zuletzt geprüft: {datetime.now().strftime('%H:%M:%S')} Uhr")
st.caption("Diese App liest die Daten direkt von der Webseite der MGB aus, da keine öffentliche API für Wartezeiten existiert.")

# DIAGNOSE-MODUS (Optional zum Testen)
with st.expander("Rohdaten-Analyse (Webseite Text)"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    test_res = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", headers=headers)
    st.text(test_res.text[:1000]) # Zeige den Anfang des HTML-Codes
