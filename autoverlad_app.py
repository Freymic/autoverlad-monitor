import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
import time
from datetime import datetime

# --- SETUP & STYLING ---
st.set_page_config(page_title="Furka Live-Monitor", layout="centered", page_icon="🏔️")

# KORREKTUR: Der Parameter heißt 'unsafe_allow_html', nicht 'unsafe_allow_name_with_html'
st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

def get_live_data():
    """Simuliert einen mobilen Browser mit erweiterten Timeouts."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Tarnung als iPhone, um GraphQL-Blockaden zu minimieren
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Erhöhtes Timeout für den Seitenaufbau
        driver.set_page_load_timeout(30)
        url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
        driver.get(url)
        
        # WICHTIG: Wir warten länger, um die 'Zeitüberschreitung' zu vermeiden
        # Die MGB-Daten brauchen oft 15+ Sekunden im Cloud-Netzwerk
        time.sleep(18)
        
        html_content = driver.page_source
        return html_content
    except Exception as e:
        return f"Fehler: {str(e)}"
    finally:
        if driver:
            driver.quit()

# --- HAUPTSEITE ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown(f"**Stand:** {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔍 Echtzeit-Daten jetzt abrufen"):
    with st.spinner("Verbindung zum MGB-Server wird aufgebaut..."):
        raw_html = get_live_data()
        
        if "Fehler" in raw_html:
            st.error(f"Technisches Problem: {raw_html}")
            st.info("Tipp: Ein 'Reboot' in Streamlit Cloud löst oft Treiber-Probleme.")
        else:
            # Suche nach den Zahlenwerten im gerenderten JavaScript-HTML
            oberwald = re.search(r'Oberwald.*?(\d+)\s*min', raw_html, re.S | re.I)
            realp = re.search(r'Realp.*?(\d+)\s*min', raw_html, re.S | re.I)
            
            col1, col2 = st.columns(2)
            
            with col1:
                val_o = oberwald.group(1) if oberwald else "0"
                st.metric("Abfahrt Oberwald", f"{val_o} Min")
                if int(val_o) > 0: st.warning("⏳ Wartezeit")
                else: st.success("✅ Freie Fahrt")

            with col2:
                val_r = realp.group(1) if realp else "0"
                st.metric("Abfahrt Realp", f"{val_r} Min")
                if int(val_r) > 0: st.warning("⏳ Wartezeit")
                else: st.success("✅ Freie Fahrt")

st.divider()
st.subheader("🔗 Direkter Zugriff")
st.link_button("Offizielle MGB Webseite", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
