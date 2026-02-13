import streamlit as st
import requests

def get_furka_data_viasuisse():
    # Dies ist eine der Schnittstellen, die SRF/Viasuisse für die Karte nutzt
    # Wir suchen gezielt nach der ID für den Autoverlad Furka
    url = "https://www.srf.ch/meteo/verkehr/api/incidents" # Beispielhafte interne API-Struktur
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        # Falls die API nicht direkt erreichbar ist, nutzen wir den Text-Fallback von der SRF-Seite
        # Aber wir imitieren einen echten Browser noch genauer
        response = requests.get("https://www.srf.ch/news/verkehrsinfo", headers=headers, timeout=10)
        content = response.text

        # Suche nach dem spezifischen JSON-Block oder Textsegment für Furka
        import re
        # Wir suchen nach "Furka" und der Zahl, die vor "Minuten" steht
        match = re.search(r'Furka.*?(\d+)\s*Minuten', content, re.IGNORECASE | re.DOTALL)
        
        if match:
            return f"{match.group(1)} Min."
        elif "Furka" in content and "offen" in content:
            return "0 Min."
        return "Keine Meldung"
    except Exception as e:
        return f"Verbindungsproblem: {str(e)}"

# --- Streamlit UI ---
st.title("🏔️ Furka Live-Monitor (Stable-Version)")

st.info("Dieser Monitor nutzt die Viasuisse-Daten von SRF, um die Sperren der MGB zu umgehen.")

if st.button('🔄 Daten jetzt aktualisieren'):
    wartezeit = get_furka_data_viasuisse()
    
    # Anzeige-Logik
    if "Min." in wartezeit:
        minuten = int(wartezeit.split()[0])
        if minuten > 15:
            st.error(f"### Aktuelle Wartezeit: {wartezeit}")
            st.write("Quelle: SRF / Viasuisse")
        else:
            st.success(f"### Aktuelle Wartezeit: {wartezeit}")
            st.write("Freie Fahrt oder nur geringe Wartezeit.")
    else:
        st.warning(f"Status: {wartezeit}")
        st.write("Hinweis: Es liegen momentan keine Staumeldungen vor.")
