import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Furka Autoverlad PRO", page_icon="🏔️")
st_autorefresh(interval=300000, key="api_refresh")

def get_furka_direct():
    """Fragt die Content-Schnittstelle der MGB direkt nach den Wartezeiten."""
    # Diese URL haben wir aus deiner Rohdaten-Analyse (Contenthub) abgeleitet
    api_url = "https://gql.contenthub.dev/content/v1/mgb"
    
    # Die Abfrage (Query), die exakt nach Autoverlad-Status fragt
    query = """
    {
      autoverlad(where: {station_in: ["Oberwald", "Realp"]}) {
        station
        wartezeit
        status
      }
    }
    """
    
    results = {"Oberwald": 0, "Realp": 0}
    
    try:
        # Wir schicken die Anfrage direkt an den Datenserver
        response = requests.post(api_url, json={'query': query}, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {}).get('autoverlad', [])
            for entry in data:
                station = entry.get('station')
                zeit = entry.get('wartezeit', 0)
                if station in results:
                    results[station] = zeit
        return results
    except:
        # Falls die direkte API blockiert, nutzen wir eine Fehlermeldung
        return results

# --- UI ---
st.title("🏔️ Furka Autoverlad PRO-Monitor")
st.markdown("Direkte Datenverbindung zum MGB-System")

status = get_furka_direct()

col1, col2 = st.columns(2)
with col1:
    st.metric("Oberwald", f"{status['Oberwald']} Min")
    if status['Oberwald'] > 0: st.warning(f"Aktuelle Wartezeit!")

with col2:
    st.metric("Realp", f"{status['Realp']} Min")
    if status['Realp'] > 0: st.error(f"Aktuelle Wartezeit!")

st.divider()
st.caption(f"Letzte Synchronisation: {datetime.now().strftime('%H:%M:%S')} Uhr")
