import streamlit as st
import requests

def get_furka_live():
    # Dies ist die tatsächliche Datenquelle für die SRF-Verkehrskarte
    url = "https://www.srf.ch/meteo/verkehr/api/incidents"
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        # Wir suchen in allen Verkehrsmeldungen nach "Furka"
        for incident in data.get('incidents', []):
            title = incident.get('title', '')
            desc = incident.get('description', '')
            
            if "Furka" in title or "Furka" in desc:
                # Suche nach der Zahl in der Beschreibung
                import re
                match = re.search(r'(\d+)\s*Minuten', desc)
                if match:
                    return f"{match.group(1)} Min."
                return "Offen (keine Wartezeit)"
        
        return "0 Min." # Keine Meldung = Keine Wartezeit
    except Exception as e:
        return f"Fehler: {str(e)}"

# --- UI ---
st.title("🏔️ Furka Final-Check")

if st.button('🔄 Daten erzwingen'):
    zeit = get_furka_live()
    if "Min." in zeit:
        st.metric("Wartezeit Furka", zeit)
        if "0" not in zeit:
            st.warning("Erhöhtes Verkehrsaufkommen!")
    else:
        st.success("✅ Aktuell freie Fahrt gemeldet.")
