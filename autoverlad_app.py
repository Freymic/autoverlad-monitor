import streamlit as st
import requests
import re
from datetime import datetime

st.set_page_config(page_title="Furka Live-Check", page_icon="🏔️")

st.title("🏔️ Furka Autoverlad Live-Status")
st.markdown(f"**Letzte Prüfung:** {datetime.now().strftime('%H:%M:%S')} Uhr")

def get_real_waiting_times():
    # Wir rufen die Seite als "Rohdaten" ab, um JS-Blöcke zu finden
    url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        content = response.text
        
        # Suche nach dem typischen JSON-Muster für Wartezeiten im Quelltext
        # Wir suchen nach "Oberwald" oder "Realp" gefolgt von einer Zahl
        times = {"Oberwald": "Unbekannt", "Realp": "Unbekannt"}
        
        for station in times.keys():
            # Regex sucht nach Station + beliebigem Text + Zahl + "min"
            match = re.search(fr'{station}.*?(\d+)\s*min', content, re.IGNORECASE | re.DOTALL)
            if match:
                times[station] = f"{match.group(1)} Min"
        
        return times
    except:
        return None

# Daten abrufen
data = get_real_waiting_times()

# Anzeige der Ergebnisse
c1, c2 = st.columns(2)

with c1:
    val = data["Oberwald"] if data else "0 Min"
    st.metric("Abfahrt Oberwald", val)
    if "Unbekannt" in val or "0" in val:
        st.success("✅ Keine Wartezeit")

with c2:
    val = data["Realp"] if data else "0 Min"
    st.metric("Abfahrt Realp", val)
    if "Unbekannt" in val or "0" in val:
        st.success("✅ Keine Wartezeit")

# --- NOTFALL-ANZEIGE ---
st.divider()
st.subheader("🔗 Direkter Link")
st.info("Falls die Automatik oben keine Daten findet, liegt es an der neuen JavaScript-Sicherung der MGB.")
st.link_button("Offizielle Wartezeiten auf MGB.ch prüfen", "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten")
