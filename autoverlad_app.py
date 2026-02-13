import streamlit as st
import requests
import re
from datetime import datetime

# --- SETUP & STYLING ---
st.set_page_config(page_title="Furka Live-Monitor", page_icon="🏔️")

st.markdown("""
    <style>
    .status-card { background-color: #1e2130; padding: 20px; border-radius: 12px; border: 1px solid #30363d; text-align: center; }
    .wait-time { font-size: 48px; font-weight: bold; color: #ff4b4b; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

def get_srf_waiting_time():
    """Scannt die SRF-Verkehrsinformationen gezielt nach Furka-Wartezeiten."""
    url = "https://www.srf.ch/news/verkehrsinfo"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        content = response.text
        
        # Wir suchen im SRF-Inhalt nach 'Furka' und der darauf folgenden Zahl vor 'Minuten'
        # Regex-Erklärung: Suche 'Furka', dann beliebigen Text (.*?), dann eine Zahl (\d+), dann 'Minuten'
        match = re.search(r'Furka.*?(\d+)\s*Minuten', content, re.S | re.I)
        
        if match:
            return match.group(1)
        return "0"
    except:
        return "Fehler"

# --- UI ---
st.title("🏔️ Furka Autoverlad Monitor")
st.write(f"Datenquelle: SRF Verkehrszentrum • {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔍 Live-Abfrage starten"):
    with st.spinner("SRF-Datenbank wird durchsucht..."):
        zeit = get_srf_waiting_time()
        
        if zeit == "Fehler":
            st.error("Verbindung zum SRF-Server fehlgeschlagen.")
        else:
            st.markdown(f"""
                <div class="status-card">
                    <h3>Aktuelle Wartezeit (Oberwald)</h3>
                    <div class="wait-time">{zeit} Min.</div>
                    <p>{'⚠️ Erhöhtes Aufkommen' if int(zeit) > 0 else '✅ Freie Fahrt'}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if int(zeit) > 0:
                st.info(f"Bestätigt durch SRF: {zeit} Minuten Wartezeit am Verlad Furka.")

st.divider()
st.subheader("🔗 Direkte Links")
st.link_button("SRF Verkehrskarte öffnen", "https://www.srf.ch/verkehrsinformationen")
