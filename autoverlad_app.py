import streamlit as st
import requests
import re
import json
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Furka Real-Time", layout="centered")
st_autorefresh(interval=300000, key="mgb_update")

def get_mgb_real_minutes():
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res_data = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            html = response.text
            
            # 1. VERSUCH: Suche nach dem JSON-Datenblock (Contenthub)
            # Wir suchen nach dem Muster "waitingTime":XX innerhalb der Bahnhofs-Objekte
            data_blocks = re.findall(r'\{"station":"(Oberwald|Realp)".*?"waitingTime":(\d+)\}', html)
            
            if data_blocks:
                for station, time in data_blocks:
                    res_data[station] = int(time)
            else:
                # 2. VERSUCH: Falls kein JSON gefunden, suche nach Textmustern
                # Wir suchen nach der Zahl, die direkt vor "min" steht, aber NACH dem Bahnhofsnamen
                for station in res_data.keys():
                    # Dieser Regex ist sehr spezifisch, um technische '1'er zu ignorieren
                    match = re.search(fr'{station}.*?(\d+)\s*min', html, re.IGNORECASE | re.DOTALL)
                    if match:
                        res_data[station] = int(match.group(1))
    except:
        pass
    return res_data

# --- DASHBOARD UI ---
st.title("🏔️ Furka Autoverlad: Echtzeit")

status = get_mgb_real_minutes()

# Falls immer noch 1 angezeigt wird, ist es wahrscheinlich ein Platzhalter
c1, c2 = st.columns(2)
with c1:
    st.metric("Oberwald", f"{status['Oberwald']} Min")
    if status['Oberwald'] > 5: st.warning("Wartezeit gemeldet")

with c2:
    st.metric("Realp", f"{status['Realp']} Min")
    if status['Realp'] > 5: st.warning("Wartezeit gemeldet")

st.divider()
st.caption(f"Letzter Daten-Scan: {datetime.now().strftime('%H:%M:%S')} Uhr")

# DEBUGGER: Wenn es nicht klappt, schauen wir uns die Umgebung von "waitingTime" an
if st.sidebar.checkbox("Technischen Datensalat zeigen"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    raw = requests.get(url, headers=headers).text
    # Suche nach dem Begriff 'waitingTime' im Code
    wt_pos = raw.find("waitingTime")
    if wt_pos > -1:
        st.code(raw[wt_pos-50:wt_pos+100], language="json")
    else:
        st.write("Feld 'waitingTime' nicht im Quellcode gefunden.")
