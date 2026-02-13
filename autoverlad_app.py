import streamlit as st
import requests
import re
from datetime import datetime

# --- SETUP ---
st.set_page_config(page_title="Furka Verlad Live", page_icon="🏔️")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

def get_data_fast():
    """Versucht die Daten ohne Selenium direkt aus dem Seitenquelltext zu lesen."""
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # Wir suchen im Quelltext nach den JSON-Datenfragmenten, die die MGB dort versteckt
        content = response.text
        
        # Suche nach Station + Zahl + min
        oberwald = re.search(r'Oberwald.*?(\d+)\s*min', content, re.S | re.I)
        realp = re.search(r'Realp.*?(\d+)\s*min', content, re.S | re.I)
        
        return {
            "Oberwald": oberwald.group(1) if oberwald else "0",
            "Realp": realp.group(1) if realp else "0"
        }
    except Exception as e:
        return None

# --- UI ---
st.title("🏔️ Furka Autoverlad Live")
st.write(f"Abfragezeit: {datetime.now().strftime('%H:%M:%S')} Uhr")

if st.button("🔄 Daten aktualisieren"):
    with st.spinner("Frage MGB-Server ab..."):
        data = get_data_fast()
        
        if data:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Abfahrt Oberwald", f"{data['Oberwald']} Min")
            with c2:
                st.metric("Abfahrt Realp", f"{data['Realp']} Min")
            
            if data['Oberwald'] == "0" and data['Realp'] == "0":
                st.info("Aktuell werden keine Wartezeiten gemeldet.")
        else:
            st.error("Verbindung zum Server fehlgeschlagen.")

st.divider()
st.subheader("🔗 Direkter Link")
st.link_button("Offizielle MGB Seite prüfen", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
