import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re

# --- Konfiguration ---
st.set_page_config(page_title="Furka Autoverlad Live", page_icon="🏔️", layout="wide")

def get_furka_data():
    """Holt die Daten vom MGB RSS-Feed und bereitet sie für das UI und Debugging auf."""
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    
    debug_info = {
        "url": url,
        "status_code": None,
        "raw_xml": "",
        "error": None
    }
    
    results = {
        "Oberwald": {"zeit": "0 Min.", "meldung": "Keine Meldung vorhanden"},
        "Realp": {"zeit": "0 Min.", "meldung": "Keine Meldung vorhanden"}
    }

    try:
        response = requests.get(url, timeout=10)
        # Wichtig für Umlaute wie 'beträgt'
        response.encoding = 'utf-8' 
        
        debug_info["status_code"] = response.status_code
        debug_info["raw_xml"] = response.text
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            
            for item in items:
                title = item.find('title').text or ""
                desc = item.find('description').text or ""
                full_text = f"{title} {desc}"
                
                # Richtung bestimmen
                direction = None
                if "Oberwald" in full_text:
                    direction = "Oberwald"
                elif "Realp" in full_text:
                    direction = "Realp"
                
                if direction:
                    results[direction]["meldung"] = title
                    
                    # Zeit-Extraktion (Stunden oder Minuten)
                    std_match = re.search(r'(\d+)\s*Stunde', full_text)
                    min_match = re.search(r'(\d+)\s*Minute', full_text)
                    
                    if std_match:
                        results[direction]["zeit"] = f"{std_match.group(1)} Std."
                    elif min_match:
                        results[direction]["zeit"] = f"{min_match.group(1)} Min."
                    elif "keine wartezeit" in full_text.lower():
                        results[direction]["zeit"] = "0 Min."
        else:
            debug_info["error"] = f"Server antwortete mit Status {response.status_code}"
            
    except Exception as e:
        debug_info["error"] = str(e)
        
    return results, debug_info

# --- Haupt-UI ---
st.title("🏔️ Furka Autoverlad Live-Monitor")
st.info("Datenquelle: Offizieller MGB Incident-Manager (RSS-Feed)")

if st.button("🔄 Daten jetzt aktualisieren"):
    daten, debug = get_furka_data()
    
    # Anzeige der Ergebnisse in Spalten
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Oberwald (VS)")
        z_ow = daten["Oberwald"]["zeit"]
        st.metric("Wartezeit", z_ow, delta="Normalbetrieb" if z_ow == "0 Min." else "Verzögerung", delta_color="inverse")
        st.caption(daten["Oberwald"]["meldung"])
        
    with col2:
        st.subheader("📍 Realp (UR)")
        z_re = daten["Realp"]["zeit"]
        st.metric("Wartezeit", z_re, delta="Normalbetrieb" if z_re == "0 Min." else "Verzögerung", delta_color="inverse")
        st.caption(daten["Realp"]["meldung"])

    # Warn-Banner falls Stau
    if "Std" in z_ow or "Std" in z_re:
        st.error("⚠️ Massive Wartezeit! Es wird eine Wartezeit von mindestens einer Stunde gemeldet.")

    st.divider()

    # --- Debug Sektion (Inklusive Response) ---
    with st.expander("🛠️ Debug-Informationen & Server-Response"):
        st.write("**Angeforderte URL:**", debug["url"])
        st.write("**HTTP Status-Code:**", debug["status_code"])
        
        if debug["error"]:
            st.error(f"**Fehler:** {debug['error']}")
            
        if debug["raw_xml"]:
            st.write("**Rohdaten vom Server (XML):**")
            st.code(debug["raw_xml"], language="xml")
else:
    st.write("Klicke auf den Button, um die aktuellen Wartezeiten zu laden.")
