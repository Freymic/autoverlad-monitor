import streamlit as st
import requests

st.title("🕵️ Rohdaten-Scanner")

url = "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "de-CH,de;q=0.9"
}

if st.button("🔍 Seite komplett auslesen"):
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            # Wir zeigen den "Salat" in einem Code-Block an
            st.success("Seite erfolgreich geladen!")
            
            # Suche nach Stichworten im Salat
            salat = response.text
            st.subheader("Vollständiger Quelltext-Auszug:")
            st.text_area("Rohdaten", salat, height=400)
            
            # Automatische Suche im Salat
            st.subheader("Automatische Fundstellen:")
            points = ["Oberwald", "Realp", "waitingTime", "min"]
            for p in points:
                count = salat.lower().count(p.lower())
                st.write(f"Das Wort **'{p}'** kommt {count} mal vor.")
        else:
            st.error(f"Fehler: Server antwortet mit Status {response.status_code}")
    except Exception as e:
        st.error(f"Verbindungsfehler: {e}")
