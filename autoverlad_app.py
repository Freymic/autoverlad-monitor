import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re
import time
from datetime import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Live-Monitor", layout="centered", page_icon="🏔️")

# CSS für schöneres Design
st.markdown("""
    <style>
    .metric-container { background-color: #1e2130; padding: 20px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_name_with_html=True)

def get_live_data():
    """Simuliert einen mobilen Browser, um die GraphQL-Daten zu laden."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Tarnung als Mobilgerät, um Sicherheits-Checks zu umgehen
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
        driver.get(url)
        
        # WICHTIG: Wir geben der Seite Zeit, die Apollo-GraphQL-Daten zu laden
        # Ein Timeout von 12 Sekunden ist meist ideal für den Server-Betrieb
        time.sleep(12)
        
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        if 'driver' in locals(): driver.quit()
        return f"Fehler: {str(e)}"

# --- UI ANZEIGE ---
st.title("🏔️ Furka Autoverlad Live")
st.markdown(f"**Letzter Check:** {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔍 Echtzeit-Daten abrufen"):
    with st.spinner("Verbindung zum MGB-ContentHub wird hergestellt..."):
        raw_html = get_live_data()
        
        if "Fehler" in raw_html:
            st.error(f"Technisches Problem: {raw_html}")
            st.info("Hinweis: Prüfe, ob 'chromium' in deiner packages.txt steht.")
        else:
            # Suche nach Station + beliebig viel Text + Zahl + "min"
            oberwald = re.search(r'Oberwald.*?(\d+)\s*min', raw_html, re.S | re.I)
            realp = re.search(r'Realp.*?(\d+)\s*min', raw_html, re.S | re.I)
            
            col1, col2 = st.columns(2)
            
            with col1:
                val_o = oberwald.group(1) if oberwald else "0"
                st.metric("Abfahrt Oberwald", f"{val_o} Min")
                if int(val_o) > 0:
                    st.warning("⏳ Wartezeit vorhanden")
                else:
                    st.success("✅ Freie Fahrt")

            with col2:
                val_r = realp.group(1) if realp else "0"
                st.metric("Abfahrt Realp", f"{val_r} Min")
                if int(val_r) > 0:
                    st.warning("⏳ Wartezeit vorhanden")
                else:
                    st.success("✅ Freie Fahrt")
            
            # Falls beide 0 sind, Sicherheitscheck
            if not oberwald and not realp:
                st.info("Keine aktiven Wartezeiten im System gefunden.")

st.divider()
# Backup-Link für den Nutzer
st.subheader("🔗 Notfall-Direktzugriff")
st.markdown("Falls die automatische Abfrage blockiert wird, nutze diesen Link:")
st.link_button("Offizielle MGB Seite öffnen", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
