import streamlit as st
import requests
import xml.etree.ElementTree as ET

def get_furka_rss():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Das XML parsen
            root = ET.fromstring(response.content)
            # Wir suchen nach dem <description> Tag im ersten <item>
            items = root.findall('.//item')
            if items:
                desc = items[0].find('description').text
                # Extrahiere die Zahl (Wartezeit) aus dem Text
                import re
                match = re.search(r'(\d+)\s*Minuten', desc)
                if match:
                    return f"{match.group(1)} Min."
                return "0 Min. (Offen)"
            return "Keine aktuellen Meldungen"
    except Exception as e:
        return f"Fehler: {str(e)}"
    return "Quelle nicht erreichbar"

# In deiner Streamlit App:
st.title("🏔️ Furka Live-Monitor (RSS-Quelle)")
if st.button('Daten vom RSS-Feed laden'):
    wartezeit = get_furka_rss()
    st.metric("Aktuelle Wartezeit", wartezeit)
