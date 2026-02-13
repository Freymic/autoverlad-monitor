import streamlit as st
import requests
import re
from datetime import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Hybrid-Monitor", page_icon="🏔️")

st.markdown("""
    <style>
    .report-box { background-color: #1e2130; padding: 20px; border-radius: 10px; border: 1px solid #30363d; }
    .source-tag { font-size: 0.8em; color: #8b949e; }
    </style>
    """, unsafe_allow_html=True)

def fetch_source(url, label):
    """Generische Funktion zum Abrufen von Web-Inhalten."""
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"}
    try:
        response = requests.get(url, headers=headers, timeout=8)
        return response.text if response.status_code == 200 else ""
    except:
        return ""

def scan_for_furka():
    # Quelle 1: TCS Verkehrsinfo
    tcs_url = "https://www.tcs.ch/de/tools/verkehrsinfo-kontrollen/aktuelle-verkehrslage.php"
    # Quelle 2: SRF Verkehrs-Feed
    srf_url = "https://www.srf.ch/news/verkehrsinfo"
    
    tcs_html = fetch_source(tcs_url, "TCS")
    srf_html = fetch_source(srf_url, "SRF")
    
    combined = tcs_html + srf_html
    
    # Suche nach 'Furka' und einer Zahl vor 'min'
    # Wir suchen flexibel: 'Furka... 20 min' oder 'Wartezeit Furka... 15 min'
    match = re.search(r'Furka.*?(\d+)\s*min', combined, re.S | re.I)
    
    if match:
        return match.group(1), "TCS/SRF Live-Feed"
    return "0", "Keine Meldungen"

# --- UI ---
st.title("🏔️ Furka Hybrid-Monitor")
st.write(f"Kombinierte Abfrage (TCS & SRF) - {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔍 Alle Verkehrsquellen scannen"):
    with st.spinner("Scanne TCS und SRF Datenbanken..."):
        zeit, quelle = scan_for_furka()
        
        st.markdown(f"""
        <div class="report-box">
            <h3>Wartezeit Autoverlad</h3>
            <h1 style="color: {'#ff4b4b' if int(zeit) > 0 else '#28a745'};">{zeit} Min.</h1>
            <p class="source-tag">Quelle: {quelle}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if int(zeit) == 0:
            st.success("✅ Beide Quellen melden derzeit keine nennenswerten Wartezeiten.")
        else:
            st.warning(f"⚠️ Achtung: Es wird eine Verzögerung von {zeit} Minuten gemeldet.")

st.divider()
st.info("Dieser Monitor nutzt Text-Analysen von TCS und SRF, um die JavaScript-Sperren der MGB zu umgehen.")
