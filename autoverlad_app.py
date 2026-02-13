import streamlit as st
import requests
import re

def get_furka_wait_time():
    # Die Hauptseite von SRF Verkehr
    url = "https://www.srf.ch/news/verkehrsinfo"
    
    # Wir geben uns als Browser aus, damit SRF uns nicht blockiert
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "Server-Fehler"

        # Wir suchen im Text nach dem Muster aus deinem Screenshot:
        # "Autoverlad Furka" ... "Wartezeit beträgt" ... "X Minuten"
        text = response.text
        
        # Regulärer Ausdruck (Regex): Sucht nach Furka und fängt die erste Zahl vor 'Minuten' ein
        # Das 're.IGNORECASE' macht es unempfindlich gegen Groß/Kleinschreibung
        match = re.search(r'Furka.*?Wartezeit.*?(\d+)\s*Minuten', text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return f"{match.group(1)} Min."
        else:
            # Wenn Furka gefunden wird, aber keine Zahl dabei steht, ist es oft "0"
            if "Furka" in text:
                return "0 Min."
            return "Keine Meldung"
            
    except Exception as e:
        return f"Fehler: {str(e)}"

# --- Streamlit Oberfläche ---
st.set_page_config(page_title="Furka Live-Check")
st.title("🏔️ Furka Autoverlad Monitor")

if st.button('🔍 Jetzt SRF-Daten prüfen'):
    with st.spinner('Lese SRF Verkehrsdaten...'):
        resultat = get_furka_wait_time()
        
        if "Min." in resultat:
            minuten = int(resultat.split()[0])
            if minuten > 0:
                st.error(f"⚠️ Aktuelle Wartezeit laut SRF: {resultat}")
            else:
                st.success("✅ Laut SRF aktuell keine Wartezeit.")
        else:
            st.info(f"Status: {resultat}")
            st.write("Hinweis: Wenn 'Keine Meldung' erscheint, liegen SRF momentan keine Staumeldungen für den Furka vor.")

st.divider()
st.caption("Datenquelle: SRF.ch via Viasuisse Text-Extraktion")
