import streamlit as st
from logic import get_latest_wait_times, get_route_recommendation

st.set_page_config(page_title="Routen-Entscheidung", layout="wide")

# --- NAVIGATION & INPUT ---
st.title("🏔️ Route ins Wallis: Furka oder Lötschberg?")

# Eingabefeld für den Startpunkt mit Buchrain als Default
startpunkt = st.text_input("Dein Startpunkt:", value="Buchrain")

# Daten abrufen basierend auf dem Startpunkt
# Hinweis: Solange wir keine Google API nutzen, bleiben die Fahrzeiten 
# für Buchrain statisch. Sobald die API steht, berechnet sie alles ab 'startpunkt'.
route_data = get_route_recommendation(startpunkt)

wait_realp = get_latest_wait_times("Realp")
wait_kandersteg = get_latest_wait_times("Kandersteg")

# --- VISUALISIERUNG ---
col1, col2 = st.columns(2)

with col1:
    st.header("📍 Via Furka (Realp)")
    # Berechnung: Anfahrt + Wartezeit + Zugfahrt (20min) + Weiterfahrt (55min)
    total_furka = route_data["Furka"]["to_terminal"] + wait_realp + route_data["Furka"]["train_duration"] + route_data["Furka"]["after_train"]
    
    st.metric("Gesamtzeit", f"{total_furka} Min", 
              delta=f"Wartezeit: {wait_realp} Min", delta_color="inverse")
    
    with st.expander("Details anzeigen"):
        st.write(f"🚗 Fahrt nach Realp: {route_data['Furka']['to_terminal']} Min")
        st.write(f"⏳ Aktuelle Wartezeit: {wait_realp} Min")
        st.write(f"🚂 Zugfahrt: 20 Min")
        st.write(f"🏎️ Oberwald -> Ried-Mörel: 55 Min")

with col2:
    st.header("📍 Via Lötschberg (Kandersteg)")
    # Berechnung: Anfahrt + Wartezeit + Zugfahrt (15min) + Weiterfahrt (45min)
    total_loetsch = route_data["Loetschberg"]["to_terminal"] + wait_kandersteg + route_data["Loetschberg"]["train_duration"] + route_data["Loetschberg"]["after_train"]
    
    st.metric("Gesamtzeit", f"{total_loetsch} Min", 
              delta=f"Wartezeit: {wait_kandersteg} Min", delta_color="inverse")
    
    with st.expander("Details anzeigen"):
        st.write(f"🚗 Fahrt nach Kandersteg: {route_data['Loetschberg']['to_terminal']} Min")
        st.write(f"⏳ Aktuelle Wartezeit: {wait_kandersteg} Min")
        st.write(f"🚂 Zugfahrt: 15 Min")
        st.write(f"🏎️ Goppenstein -> Ried-Mörel: 45 Min")

# --- EMPFEHLUNG ---
st.markdown("---")
diff = abs(total_furka - total_loetsch)
if total_furka < total_loetsch:
    st.success(f"💡 **Empfehlung:** Nimm den **Furka-Autoverlad**. Du sparst aktuell ca. **{diff} Minuten**.")
else:
    st.success(f"💡 **Empfehlung:** Nimm den **Lötschberg-Autoverlad**. Du sparst aktuell ca. **{diff} Minuten**.")
