import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Verlad Live", layout="wide", page_icon="🏔️")
# Seite alle 5 Minuten neu laden
st_autorefresh(interval=300000, key="f_refresh")

# --- UI DESIGN ---
st.title("🏔️ Furka Autoverlad Live-Monitor")
st.markdown(f"**Aktualisiert am:** {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr")

# Wir erstellen zwei Spalten für die offizielle Ansicht und deine Infos
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Aktuelle Wartezeiten (Original MGB)")
    # Hier betten wir die offizielle Seite direkt ein
    # Wir nutzen CSS, um genau den Bereich mit den Wartezeiten anzuzeigen
    st.components.v1.iframe(
        "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", 
        height=500, 
        scrolling=True
    )

with col2:
    st.subheader("💡 Reise-Infos")
    st.info("""
    **Legende:**
    * 🟢 **0-15 Min:** Keine Wartezeit
    * 🟡 **15-45 Min:** 1-2 Züge abwarten
    * 🔴 **> 45 Min:** Hohes Verkehrsaufkommen
    """)
    
    st.warning("⚠️ **Hinweis:** Die Daten werden direkt von der Matterhorn Gotthard Bahn geladen.")

# --- FOOTER ---
st.divider()
st.link_button("🎟️ Online Ticket kaufen", "https://www.matterhorngotthardbahn.ch/de/autoverlad/furka/")
