import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

st.set_page_config(page_title="Furka Realtime", page_icon="🏔️")

st.title("🏔️ Furka Autoverlad Echtzeit-Check")
st.info("Der Browser-Simulator startet... Bitte einen Moment Geduld.")

def get_furka_times_live():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Kein Fenster öffnen
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    
    try:
        driver.get(url)
        # Wir warten bis zu 15 Sekunden, bis das Element mit den Zeiten erscheint
        # MGB nutzt oft Text-Elemente für die Anzeige
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_BODY, "body")))
        
        # Kurze Pause damit JS die Zahlen einsetzen kann
        time.sleep(5)
        
        page_text = driver.page_source
        driver.quit()
        return page_text
    except Exception as e:
        driver.quit()
        return str(e)

# Button zum manuellen Starten
if st.button("🔍 Live-Daten jetzt abrufen"):
    raw_data = get_furka_times_live()
    
    # Wir filtern die Zahlen aus dem fertig gerenderten HTML
    import re
    oberwald = re.search(r'Oberwald.*?(\d+)\s*min', raw_data, re.IGNORECASE | re.DOTALL)
    realp = re.search(r'Realp.*?(\d+)\s*min', raw_data, re.IGNORECASE | re.DOTALL)
    
    c1, c2 = st.columns(2)
    with c1:
        val = f"{oberwald.group(1)} Min" if oberwald else "Keine Wartezeit"
        st.metric("Abfahrt Oberwald", val)
    with c2:
        val = f"{realp.group(1)} Min" if realp else "Keine Wartezeit"
        st.metric("Abfahrt Realp", val)

st.divider()
st.caption("Datenquelle: Direkt-Scan der MGB-Webseite via Selenium.")
