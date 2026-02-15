import streamlit as st
import datetime
from logic import get_latest_wait_times, get_google_maps_duration

st.set_page_config(page_title="Routen-Check Wallis", layout="wide")

st.title("🚗 Deine Reise nach Ried-Mörel")
start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Route jetzt berechnen"):
    with st.spinner("Frage Verkehrsdaten ab..."):
        # Daten für Furka
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        warte_f = get_latest_wait_times("Realp")
        zug_f = 25
        ziel_f = get_google_maps_duration("Oberwald", "Ried-Mörel")
        total_f = anfahrt_f + warte_f + zug_f + ziel_f

        # Daten für Lötschberg
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        warte_l = get_latest_wait_times("Kandersteg")
        zug_l = 20
        ziel_l = get_google_maps_duration("Goppenstein", "Ried-Mörel")
        total_l = anfahrt_l + warte_l + zug_l + ziel_l

    # Anzeige in zwei großen Spalten
    col_f, col_l = st.columns(2)

    with col_f:
        st.subheader("🏔️ Via Furka (Realp)")
        st.metric("Gesamtzeit", f"{total_f} Min", delta=None)
        
        # Etappen-Darstellung
        st.write(f"🏠 **Start:** {start}")
        st.write(f"⬇️ _Fahrzeit:_ **{anfahrt_f} Min**")
        st.write(f"🏎️ **Ankunft Realp:** {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_f)).strftime('%H:%M')}")
        
        st.warning(f"⏳ **Wartezeit:** {warte_f} Min")
        
        st.write(f"⬇️ _Zugfahrt:_ **{zug_f} Min**")
        st.write(f"🚂 **Abfahrt Oberwald:** ca. {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_f + warte_f + zug_f)).strftime('%H:%M')}")
        
        st.write(f"⬇️ _Fahrzeit:_ **{ziel_f} Min**")
        st.success(f"🏁 **Ziel Ried-Mörel:** {(datetime.datetime.now() + datetime.timedelta(minutes=total_f)).strftime('%H:%M')}")

    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        st.metric("Gesamtzeit", f"{total_l} Min", delta=None)

        st.write(f"🏠 **Start:** {start}")
        st.write(f"⬇️ _Fahrzeit:_ **{anfahrt_l} Min**")
        st.write(f"🏎️ **Ankunft Kandersteg:** {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_l)).strftime('%H:%M')}")
        
        st.warning(f"⏳ **Wartezeit:** {warte_l} Min")
        
        st.write(f"⬇️ _Zugfahrt:_ **{zug_l} Min**")
        st.write(f"🚂 **Abfahrt Goppenstein:** ca. {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_l + warte_l + zug_l)).strftime('%H:%M')}")
        
        st.write(f"⬇️ _Fahrzeit:_ **{ziel_l} Min**")
        st.success(f"🏁 **Ziel Ried-Mörel:** {(datetime.datetime.now() + datetime.timedelta(minutes=total_l)).strftime('%H:%M')}")

    # Zusammenfassendes Fazit
    st.divider()
    if total_f < total_l:
        st.balloons()
        st.success(f"✅ **Empfehlung:** Über den **Furka** sparst du heute **{total_l - total_f} Minuten**!")
    else:
        st.balloons()
        st.success(f"✅ **Empfehlung:** Über den **Lötschberg** sparst du heute **{total_f - total_l} Minuten**!")
