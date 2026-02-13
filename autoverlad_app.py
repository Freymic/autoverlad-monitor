import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import time

def get_live_data_v2():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
        driver.get(url)
        
        # NEU: Wir warten bis zu 20 Sekunden, bis irgendwo "min" auftaucht
        # Das gibt dem JAMES-Web Gateway genug Zeit
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'min')]"))
        )
        
        # Sicherheits-Pause für den finalen Render
        time.sleep(2)
        
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        if 'driver' in locals(): driver.quit()
        return None

# --- UI Anzeige ---
if st.button("🔍 Tiefen-Scan starten"):
    with st.spinner("Warte auf Antwort vom MGB-Server..."):
        raw_html = get_live_data_v2()
        
        if raw_html:
            # Wir suchen gezielt nach den Textblöcken neben den Stationsnamen
            oberwald = re.findall(r'Oberwald.*?(\d+)\s*min', raw_html, re.S | re.I)
            realp = re.findall(r'Realp.*?(\d+)\s*min', raw_html, re.S | re.I)
            
            o_min = oberwald[0] if oberwald else "0"
            r_min = realp[0] if realp else "0"
            
            st.metric("Abfahrt Oberwald", f"{o_min} Min")
            st.metric("Abfahrt Realp", f"{r_min} Min")
            
            if o_min == "0" and r_min == "0":
                st.info("Aktuell scheint keine Wartezeit gemeldet zu sein (0 Min).")
        else:
            st.error("Zeitüberschreitung: Der MGB-Server hat die Daten nicht rechtzeitig gesendet.")
