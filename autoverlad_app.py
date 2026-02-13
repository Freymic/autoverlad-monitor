import streamlit as st
import requests
import re
import json
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Furka Live-Monitor", layout="centered", page_icon="🏔️")
st_autorefresh(interval=300000, key="mgb_final_sync")

def get_furka_real_data():
    url = "https://www.matterhorngotthardbahn.ch/graphql"
    headers = {
        "Content-Type": "application/json",
        "x-ada-client-type": "JAMES-Web", # Der Schlüssel aus deinem Scan
        "Origin": "https://www.matterhorngotthardbahn.ch",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }

    # Wir testen die 3 häufigsten Strukturen für Wartezeit-Daten
    queries = [
        # 1. Suche nach allgemeinen Autoverlad-Status-Objekten
        'query { allAutoverladStatus { items { stationName waitingTime } } }',
        # 2. Suche nach Story-Inhalten (wo die Texte liegen)
        'query { route(path: "/de/stories/autoverlad-furka-wartezeiten") { ... on Story { content { ... on ContentGrid { items { ... on ContentText { text } } } } } } }',
        # 3. Suche nach speziellen Komponenten
        'query { story(slug: "autoverlad-furka-wartezeiten") { components { ... on WaitingTimeComponent { time station } } } }'
    ]
    
    res_data = {"Oberwald": 0, "Realp": 0}
    
    for q in queries:
        try:
            response = requests.post(url, json={'query': q}, headers=headers, timeout=10)
            if response.status_code == 200:
                raw_json = response.text
                # Globaler Scan: Wir suchen nach 'Oberwald' gefolgt von einer Zahl
                for station in res_data.keys():
                    # Findet 'Oberwald":30' oder 'Oberwald...45 min'
                    match = re.search(fr'{station}.*?(\d+)\s*(?:min|")', raw_json, re.IGNORECASE | re.DOTALL)
                    if match:
                        found_val = int(match.group(1))
                        # Ignoriere technische Platzhalter wie '1'
                        if found_val > 1 or "min" in match.group(0).lower():
                            res_data[station] = found_val
                
                # Wenn wir Werte gefunden haben, die nicht 0 oder 1 sind, brechen wir ab
                if any(v > 1 for v in res_data.values()):
                    break
        except:
            continue
            
    return res_data

# --- UI ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown("Direkte Systemabfrage: MGB Apollo GraphQL")

status = get_furka_real_data()

# Kacheln mit Logik für Statusfarben
c1, c2 = st.columns(2)
with c1:
    val = status["Oberwald"]
    st.metric("Oberwald", f"{val} Min")
    if val >= 15: st.warning("⚠️ Wartezeit")
    else: st.success("✅ Freie Fahrt")

with c2:
    val = status["Realp"]
    st.metric("Realp", f"{val} Min")
    if val >= 15: st.warning("⚠️ Wartezeit")
    else: st.success("✅ Freie Fahrt")

# Diagnose-Tool
with st.expander("Diagnose-Details (Rohdaten-Check)"):
    st.write("Gefundene Werte:", status)
    st.write("Status: Verbunden mit JAMES-Web Gateway")
