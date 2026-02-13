import streamlit as st
from datetime import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="Furka Live-Monitor", layout="wide", page_icon="🏔️")

# CSS für das Design (Fix für den TypeError)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .info-box { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER ---
st.title("🏔️ Furka Autoverlad Live-Monitor")
st.markdown(f"**Stand:** {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} Uhr")

# --- HAUPTBEREICH ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Aktuelle Wartezeiten")
    # Wir betten die Original-Schnittstelle ein, die IMMER die echten Daten lädt
    # Das umgeht alle Scraper-Blockaden und den Fehler 127
    st.components.v1.iframe(
        "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
        height=500,
        scrolling=True
    )

with col2:
    st.subheader("💡 Reise-Info")
    st.markdown("""
    <div class="info-box">
    <strong>Wartezeit-Skala:</strong><br>
    🟢 0-15 Min: Freie Fahrt<br>
    🟡 15-45 Min: Erhöhtes Aufkommen<br>
    🔴 > 45 Min: Starke Verzögerung
    </div>
    """, unsafe_allow_html=True)
    
    st.info("Die Daten werden in Echtzeit direkt vom MGB-Server geladen.")

st.divider()
st.caption("Dieses Dashboard kombiniert die offizielle Live-Quelle mit deinem Monitor-Design.")
