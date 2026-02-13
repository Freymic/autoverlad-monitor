import streamlit as st

st.title("🏔️ Furka Live-Verkehrsfluss")

# Wir betten eine Google Maps Karte ein, die auf Oberwald zentriert ist
# Der 'layer=t' Parameter aktiviert die Verkehrsdaten (Traffic)
st.markdown("### 🚗 Echtzeit-Stau-Check (Oberwald & Realp)")
st.info("Ist die Strasse zum Verlad ROT? Dann gibt es Wartezeit.")

# Koordinaten für Oberwald Verlad
map_url = "https://www.google.com/maps/embed/v1/view?key=DEIN_GOOGLE_API_KEY&center=46.5333,8.3500&zoom=15&maptype=roadmap&layer=t"
# Hinweis: Ohne API Key nutzen wir die Standard-Embed-Variante:
st.components.v1.iframe(
    "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2724.444!2d8.348!3d46.533!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zNDbase0zMicwMC4wIk4gOMKwMjAnNDguMCJF!5e0!3m2!1sde!2sch!4v1614000000000",
    height=450
)

st.markdown("""
    <a href="https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten" target="_blank" 
       style="background-color: #ff4b4b; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
       Zusätzlich offizielle MGB-Minuten prüfen
    </a>
""", unsafe_allow_html=True)
