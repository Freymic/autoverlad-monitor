import streamlit as st
import requests
import re

def get_real_traffic_data():
    # Wir fragen direkt die Datenquelle ab, die im SRF-Quelltext steht
    url = "https://trafficmapsrgssr.trafficintelligence.ch/1"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # Wir suchen im Text der echten Datenquelle nach Furka und Minuten
        content = response.text
        
        # Suche nach 'Furka' und der Zahl vor 'Minuten'
        match = re.search(r'Furka.*?(\d+)\s*Minuten', content, re.S | re.I)
        
        if match:
            return match.group(1)
        return "0"
    except:
        return "Fehler"

st.title("🏔️ Furka Live-Check (Direkt-Quelle)")

if st.button("Jetzt prüfen"):
    zeit = get_real_traffic_data()
    if zeit == "0":
        st.success("Aktuell keine Wartezeit bei SRF/TrafficIntelligence gelistet.")
    elif zeit == "Fehler":
        st.error("Datenquelle konnte nicht erreicht werden.")
    else:
        st.warning(f"Bestätigte Wartezeit: {zeit} Minuten")
        st.info("Diese Info stammt direkt aus dem SRF-Verkehrssystem.")
