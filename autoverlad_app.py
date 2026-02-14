import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re

# --- Funktionen ---

def get_furka_rss_data():
    """Liest den RSS-Feed aus und gibt Rohdaten sowie die extrahierte Zeit zurück."""
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    
    debug_info = {
        "status_code": None,
        "raw_xml": "",
        "found_items": 0,
        "error": None
    }
    
    try:
        response = requests.get(url, timeout=10)
        debug_info["status_code"] = response.status_code
        debug_info["raw_xml"] = response.text
        
        if response.status_code == 200:
            # XML parsen
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            debug_info["found_items"] = len(items)
            
            if items:
                # Wir nehmen die Beschreibung des aktuellsten Eintrags
                description = items[0].find('description').text
                
                # Suche nach der Wartezeit (Zahl vor 'Minuten')
                match = re.search(r'(\d+)\s*Minuten', description)
                if match:
                    return f"{match.group(1)} Min.", debug_info
                
                # Fallback: Wenn 'offen' im Text steht, aber keine Zahl
                if "offen" in description.lower():
                    return "0 Min.", debug_info
                    
            return "0 Min. (Keine Meldung)", debug_info
            
    except Exception as e:
        debug_info["error"] = str(e)
        return "Fehler", debug_info
    
    return "Keine Daten", debug_info

# --- Streamlit UI ---

st.set_page_config(page_title="Furka RSS Debugger", page_icon="🏔️")

st.title("🏔️ Furka Autoverlad Monitor")
st.markdown("Abfrage via **MGB RSS-Schnittstelle** (stabilste Methode).")

if st.button('🔍 Daten jetzt abrufen'):
    wartezeit, debug = get_furka_rss_data()
    
    # Hauptanzeige
    if wartezeit == "Fehler":
        st.error(f"Verbindungsfehler: {debug['error']}")
    else:
        # Große Anzeige der Wartezeit
        st.metric(label="Aktuelle Wartezeit Furka", value=wartezeit)
        
        # Visuelles Feedback
        min_val = int(re.search(r'\d+', wartezeit).group()) if any(char.isdigit() for char in wartezeit) else 0
        if min_val > 0:
            st.warning(f"Achtung: Aktuell {min_val} Minuten Wartezeit gemeldet!")
        else:
            st.success("Freie Fahrt! Der Verlad ist offen und ohne nennenswerte Wartezeit.")

# --- Debug Sektion ---
with st.expander("🛠️ Debug-Informationen anzeigen (für Entwickler)"):
    st.write("Diese Informationen helfen zu verstehen, warum die App ggf. 0 Min anzeigt.")
    
    if 'debug' in locals():
        st.write(f"**HTTP Status:** {debug['status_code']}")
        st.write(f"**Gefundene Meldungen:** {debug['found_items']}")
        
        if debug['raw_xml']:
            st.code(debug['raw_xml'], language='xml')
        
        if debug['error']:
            st.error(f"Fehlermeldung: {debug['error']}")
    else:
        st.info("Noch keine Daten abgerufen. Klicke oben auf den Button.")

st.divider()
st.caption("Datenquelle: Matterhorn Gotthard Bahn (MGB) RSS Incident Manager")
