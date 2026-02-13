import streamlit as st
import requests
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Furka Live-Monitor", layout="centered")
st_autorefresh(interval=300000, key="api_refresh")

def get_real_minuten():
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res_data = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            html = response.text
            
            # Strategie: Wir suchen im "JSON-LD" oder in den Scripts, 
            # wo die MGB die echten Werte für die App-Anzeige speichert.
            for station in res_data.keys():
                # Wir suchen spezifisch nach dem Muster: "station":"Oberwald","waitingTime":30
                # oder nach dem Text direkt in der Nähe von "min"
                patterns = [
                    fr'"{station}".*?"waitingTime":\s*(\d+)', # Suche in JSON-Strukturen
                    fr'{station}.*?>\s*(\d+)\s*min',          # Suche in HTML-Tags
                    fr'(\d+)\s*min.*?{station}'               # Alternative Reihenfolge
                ]
                
                for p in patterns:
                    match = re.search(p, html, re.IGNORECASE | re.DOTALL)
                    if match:
                        res_data[station] = int(match.group(1))
                        break # Wenn ein Muster passt, nimm den Wert
    except:
        pass
    return res_data

# --- UI ---
st.title("🏔️ Furka Autoverlad Live")

# Abruf der Daten
status = get_real_minuten()

# Falls wir immer noch 0 oder 1 finden, machen wir eine Debug-Ausgabe
if status["Oberwald"] <= 1:
    st.sidebar.warning("Suche nach echten Minuten läuft...")
    # Zeige uns die Umgebung des Wortes 'Oberwald' im Quellcode
    with st.expander("Technischer Quelltext-Check"):
        headers = {'User-Agent': 'Mozilla/5.0'}
        raw = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", headers=headers).text
        # Finde 'Oberwald' und zeige 500 Zeichen davor/danach
        pos = raw.find("Oberwald")
        if pos > -1:
            st.code(raw[max(0, pos-100):pos+400])
        else:
            st.write("Wort 'Oberwald' im Quellcode nicht gefunden - Seite lädt komplett dynamisch.")

c1, c2 = st.columns(2)
c1.metric("Oberwald", f"{status['Oberwald']} Min")
c2.metric("Realp", f"{status['Realp']} Min")

st.caption(f"Letzter Check: {datetime.now().strftime('%H:%M:%S')} Uhr")
