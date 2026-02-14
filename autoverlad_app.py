import streamlit as st
import xml.etree.ElementTree as ET
import re

def parse_furka_rss(xml_content):
    """Extrahiert Wartezeiten für Oberwald und Realp aus dem RSS-Feed."""
    results = {
        "Oberwald": {"zeit": "0 Min.", "text": "Keine Meldung"},
        "Realp": {"zeit": "0 Min.", "text": "Keine Meldung"}
    }
    
    try:
        root = ET.fromstring(xml_content)
        items = root.findall('.//item')
        
        for item in items:
            title = item.find('title').text
            desc = item.find('description').text
            full_text = title + " " + desc
            
            # Bestimme die Richtung
            direction = None
            if "Oberwald" in full_text:
                direction = "Oberwald"
            elif "Realp" in full_text:
                direction = "Realp"
                
            if direction:
                # Suche nach Zeitangaben (Minuten oder Stunden)
                results[direction]["text"] = title
                
                # Suche nach "X Stunde(n)"
                std_match = re.search(r'(\d+)\s*Stunde', full_text)
                # Suche nach "X Minute(n)"
                min_match = re.search(r'(\d+)\s*Minute', full_text)
                
                if std_match:
                    results[direction]["zeit"] = f"{std_match.group(1)} Std."
                elif min_match:
                    results[direction]["zeit"] = f"{min_match.group(1)} Min."
                elif "keine wartezeit" in full_text.lower():
                    results[direction]["zeit"] = "0 Min."
                    
        return results
    except Exception as e:
        st.error(f"Parsing Fehler: {e}")
        return results

# --- UI Layout ---
st.title("🏔️ Furka Autoverlad Live-Status")
st.markdown("Echtzeit-Daten direkt aus dem MGB Incident-Manager.")

# Simulation der Antwort, die du gepostet hast (für die App via requests.get().text ersetzen)
xml_data = """[DEIN XML OBEN]""" 

# Daten verarbeiten
daten = parse_furka_rss(xml_data)

# Anzeige in zwei Spalten
col1, col2 = st.columns(2)

with col1:
    st.subheader("📍 Oberwald (VS)")
    zeit_ow = daten["Oberwald"]["zeit"]
    st.metric("Wartezeit", zeit_ow, delta="Frei" if zeit_ow == "0 Min." else "Stau")
    st.caption(daten["Oberwald"]["text"])

with col2:
    st.subheader("📍 Realp (UR)")
    zeit_re = daten["Realp"]["zeit"]
    # Hier würde jetzt "1 Std." stehen
    st.metric("Wartezeit", zeit_re, delta="Verzögerung" if zeit_re != "0 Min." else None, delta_color="inverse")
    st.caption(daten["Realp"]["text"])

# Warnhinweis falls irgendwo Stau ist
if "Std" in zeit_ow or "Std" in zeit_re or "Min" in zeit_ow and int(re.search(r'\d+', zeit_ow).group()) > 20:
    st.warning("⚠️ Achtung: Es besteht eine erhebliche Wartezeit an mindestens einer Verladestation.")
