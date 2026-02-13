import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
import time
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="Furka Live", page_icon="🏔️")

# KORREKTUR: 'unsafe_allow_html' statt des fehlerhaften Namens
st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

def get_live_data():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # iPhone-Tarnung gegen GraphQL-Blockaden
    options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1")

    driver = None
    try:
        # WebDriver-Manager installiert den passenden Treiber automatisch
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
        driver.get(url)
        
        # WICHTIG: 15 Sek. warten, damit die GraphQL-Daten laden
        time.sleep(15)
        
        html = driver.page_source
        return html
    except Exception as e:
        return f"Fehler: {str(e)}"
    finally:
        if driver: driver.quit()

st.title("🏔️ Furka Autoverlad Live")
st.write(f"Abfragezeitpunkt: {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔍 Jetzt Live-Daten prüfen"):
    with st.spinner("MGB-Server wird abgefragt..."):
        content = get_live_data()
        
        if "Fehler" in content:
            st.error(f"Technisches Problem (Code 127): {content}")
            st.info("💡 Lösung: Stelle sicher, dass die Datei 'packages.txt' im GitHub-Ordner liegt.")
        else:
            # Suche nach Station + Zahl + min
            o_match = re.search(r'Oberwald.*?(\d+)\s*min', content, re.S | re.I)
            r_match = re.search(r'Realp.*?(\d+)\s*min', content, re.S | re.I)
            
            c1, c2 = st.columns(2)
            with c1: st.metric("Oberwald", f"{o_match.group(1) if o_match else '0'} Min")
            with c2: st.metric("Realp", f"{r_match.group(1) if r_match else '0'} Min")

st.divider()
st.link_button("Offizielle Webseite", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
