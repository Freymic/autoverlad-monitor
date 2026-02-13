import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
import time

# --- SETUP ---
st.set_page_config(page_title="Furka Realtime", page_icon="🏔️")
st.title("🏔️ Furka Autoverlad Echtzeit-Check")

def get_live_data():
    # Chrome-Optionen für Server-Betrieb (Streamlit Cloud)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        # Browser starten
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
        driver.get(url)
        
        # WICHTIG: Wir geben der Seite 8 Sekunden Zeit, das JavaScript fertig zu laden
        time.sleep(8)
        
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        return f"Fehler: {str(e)}"

# --- UI ---
if st.button("🔍 Live-Daten von MGB abrufen"):
    with st.spinner("Browser-Simulator extrahiert Live-Daten..."):
        raw_html = get_live_data()
        
        # Suche nach den echten Minutenwerten (ignoriert die statische '1')
        # Regex sucht nach: Station + beliebig viel Text + Zahl + "min"
        oberwald_match = re.search(r'Oberwald.*?(\d+)\s*min', raw_html, re.IGNORECASE | re.DOTALL)
        realp_match = re.search(r'Realp.*?(\d+)\s*min', raw_html, re.IGNORECASE | re.DOTALL)

        c1, c2 = st.columns(2)
        
        with c1:
            val_o = oberwald_match.group(1) if oberwald_match else "0"
            st.metric("Abfahrt Oberwald", f"{val_o} Min")
            if int(val_o) > 0: st.warning("⚠️ Wartezeit")
            else: st.success("✅ Freie Fahrt")

        with c2:
            val_r = realp_match.group(1) if realp_match else "0"
            st.metric("Abfahrt Realp", f"{val_r} Min")
            if int(val_r) > 0: st.warning("⚠️ Wartezeit")
            else: st.success("✅ Freie Fahrt")

st.divider()
st.info("Dieser Modus simuliert einen echten Webbesucher, um die JavaScript-Sperre der MGB zu umgehen.")
