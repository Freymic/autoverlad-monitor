import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- SETUP ---
st.set_page_config(page_title="Furka Verlad Live", layout="wide", page_icon="🏔️")
# Automatische Aktualisierung alle 5 Minuten
st_autorefresh(interval=300000, key="mgb_final_refresh")

st.title("🏔️ Furka Autoverlad Live-Monitor")
st.markdown(f"**Stand:** {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr")

# Layout in zwei Spalten
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Aktuelle Wartezeiten (Original)")
    # Wir betten die Original-Webseite ein
    # Da die Daten per JS geladen werden, zeigt dieser IFrame sie korrekt an
    st.components.v1.iframe(
        "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
        height=600,
        scrolling=True
    )

with col2:
    st.subheader("💡 Reise-Infos")
    st.info("""
    **Wartezeit-Skala:**
    * 🟢 **0-15 Min:** Freie Fahrt
    * 🟡 **15-45 Min:** Erhöhtes Aufkommen
    * 🔴 **> 45 Min:** Starke Verzögerung
    """)
    st.warning("Die Daten kommen direkt vom MGB ContentHub.")

st.divider()
st.caption("Dieses Dashboard spiegelt die offiziellen Echtzeitdaten der MGB.")
