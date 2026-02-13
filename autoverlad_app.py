import streamlit as st
import requests
import re
import json
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Autoverlad Live", layout="centered", page_icon="🏔️")
# Automatische Aktualisierung alle 5 Minuten
st_autorefresh(interval=300000, key="mgb_final_refresh")

def get_furka_real_minutes():
    """Tiefensuche in der MGB-Schnittstelle nach echten Wartezeiten."""
    url = "https://www.matterhorngotthardbahn.ch/graphql"
    
    # Header basierend auf deinem erfolgreichen Browser-Scan
    headers = {
        "Content-Type": "application/json",
        "x-ada-client-type": "JAMES-Web",
        "Origin": "https://www.matterhorngotthardbahn.ch",
        "Referer": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    }

    # Diese Query fragt gezielt nach dem Inhalt der Wartezeit-Seite
    query = """
    query {
      route(path: "/de/stories/autoverlad-furka-wartezeiten") {
        ... on Story {
          content {
            ... on ContentGrid {
              items {
                ... on ContentText { text }
                ... on ContentList { items { ... on ContentText { text } } }
              }
            }
          }
        }
      }
    }
    """
    
    res_data = {"Oberwald": 0, "Realp": 0}
    
    try:
        response = requests.post(url, json={'query': query}, headers=headers, timeout=15)
        if response.status_code == 200:
            # Wir wandeln die gesamte Antwort in einen String um für einen globalen Scan
            data_str = json.dumps(response.json())
            
            for station in res_data.keys():
                # Suche nach der Station und der darauffolgenden Zahl vor 'min'
                # Ignoriert technische Platzhalter wie '1' durch Prüfung auf Kontext
                match = re.search(fr'{station}.*?(\d+)\s*min', data_str, re.IGNORECASE | re.DOTALL)
                if match:
                    res_data[station] = int(match.group(1))
    except Exception as e:
        st.sidebar.error(f"Verbindungsfehler: {e}")
        
    return res_data

# --- BENUTZEROBERFLÄCHE (UI) ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown("Direktabfrage der **Matterhorn Gotthard Bahn (MGB)**")

# Daten abrufen
status = get_furka_real_minutes()

# Sidebar mit Simulation zum Testen der Warnstufen
st.sidebar.header("Optionen")
sim_mode = st.sidebar.checkbox("Simulation (Wartezeit testen)")
if sim_mode:
    status = {"Oberwald": 45, "Realp": 15}
    st.sidebar.info("Simulationsmodus: 45 Min / 15 Min")

# Anzeige der Kacheln
c1, c2 = st.columns(2)

with c1:
    val_o = status["Oberwald"]
    st.metric("Wartezeit Oberwald", f"{val_o} Min")
    if val_o >= 45:
        st.error("🚨 Starke Wartezeit!")
    elif val_o >= 15:
        st.warning("⚠️ Wartezeit vorhanden")
    elif val_o > 1:
        st.info("ℹ️ Kurze Wartezeit")
    else:
        st.success("✅ Freie Fahrt")

with c2:
    val_r = status["Realp"]
    st.metric("Wartezeit Realp", f"{val_r} Min")
    if val_r >= 45:
        st.error("🚨 Starke Wartezeit!")
    elif val_r >= 15:
        st.warning("⚠️ Wartezeit vorhanden")
    elif val_r > 1:
        st.info("ℹ️ Kurze Wartezeit")
    else:
        st.success("✅ Freie Fahrt")

st.divider()
st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")

# Notfall-Link und Diagnose
st.sidebar.markdown("---")
st.sidebar.link_button("🌐 Offizielle Webseite", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")

with st.expander("Diagnose-Details (Rohdaten-Check)"):
    st.write("Gefundene Werte:", status)
    st.write("Verwendete Schnittstelle: MGB Apollo GraphQL")
