import streamlit as st
import datetime
# Wichtig: get_furka_departure muss in der logic.py vorhanden sein!
from logic import get_latest_wait_times, get_google_maps_duration, get_furka_departure

st.set_page_config(page_title="Routen-Check Wallis", layout="wide")

st.title("🚗 Deine Reise nach Ried-Mörel")
start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Route jetzt berechnen"):
    with st.spinner("Berechne Fahrplan und Verkehrsdaten..."):
        jetzt = datetime.datetime.now()
        
        # --- ROUTE A: FURKA (REALP) ---
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        ankunft_realp = jetzt + datetime.timedelta(minutes=anfahrt_f)
        
        # Fahrplan-Check Furka
        naechster_zug_f = get_furka_departure(ankunft_realp)
        
        if naechster_zug_f:
            wartezeit_fahrplan_f = int((naechster_zug_f - ankunft_realp).total_seconds() / 60)
            stau_f = get_latest_wait_times("Realp")
            # Die echte Wartezeit ist das Maximum aus Fahrplan-Lücke und Stau
            effektive_warte_f = max(wartezeit_fahrplan_f, stau_f)
            zug_f_dauer = 25 # Verlad + Tunnel
            ziel_f = get_google_maps_duration("Oberwald", "Ried-Mörel")
            total_f = anfahrt_f + effektive_warte_f + zug_f_dauer + ziel_f
            ankunft_ziel_f = jetzt + datetime.timedelta(minutes=total_f)
        else:
            total_f = 999 # Fallback falls kein Zug mehr fährt

        # --- ROUTE B: LÖTSCHBERG (KANDERSTEG) ---
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
        
        # Dummy-Fahrplan Lötschberg (Takt .20 / .50)
        # (Kann später durch eine echte Funktion in logic.py ersetzt werden)
        if ankunft_kandersteg.minute <= 10: dep_m = 20
        elif ankunft_kandersteg.minute <= 40: dep_m = 50
        else: dep_m = 20 # Nächste Stunde
        
        wartezeit_l = get_latest_wait_times("Kandersteg")
        zug_l_dauer = 20
        ziel_l = get_google_maps_duration("Goppenstein", "Ried-Mörel")
        total_l = anfahrt_l + wartezeit_l + zug_l_dauer + ziel_l
        ankunft_ziel_l = jetzt + datetime.timedelta(minutes=total_l)

    # Anzeige in zwei Spalten
    col_f, col_l = st.columns(2)

    with col_f:
        st.subheader("🏔️ Via Furka (Realp)")
        if naechster_zug_f:
            st.metric("Ankunft Ried-Mörel", ankunft_ziel_f.strftime('%H:%M'), f"{total_f} Min Gesamt")
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Realp: **{anfahrt_f} Min**")
            st.write(f"🏎️ **Ankunft Terminal:** {ankunft_realp.strftime('%H:%M')}")
            st.warning(f"⏳ **Wartezeit:** {effektive_warte_f} Min (Zug-Abfahrt: {naechster_zug_f.strftime('%H:%M')})")
            st.write(f"🚂 **Zugfahrt:** {zug_f_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_f} Min**")
            st.success(f"🏁 **Ziel:** {ankunft_ziel_f.strftime('%H:%M')}")
        else:
            st.error("❌ Kein Zugverkehr mehr laut Fahrplan.")

    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        st.metric("Ankunft Ried-Mörel", ankunft_ziel_l.strftime('%H:%M'), f"{total_l} Min Gesamt")
        st.write(f"🏠 **Start:** {start}")
        st.write(f"⬇️ Fahrt bis Kandersteg: **{anfahrt_l} Min**")
        st.write(f"🏎️ **Ankunft Terminal:** {ankunft_kandersteg.strftime('%H:%M')}")
        st.warning(f"⏳ **Wartezeit:** {warte_l} Min")
        st.write(f"🚂 **Zugfahrt:** {zug_l_dauer} Min")
        st.write(f"⬇️ Restliche Fahrt: **{ziel_l} Min**")
        st.success(f"🏁 **Ziel:** {ankunft_ziel_l.strftime('%H:%M')}")

    # Zusammenfassendes Fazit
    st.divider()
    if total_f < total_l:
        st.balloons()
        st.success(f"✅ **Empfehlung:** Über den **Furka** bist du ca. **{total_l - total_f} Minuten** früher am Ziel.")
    else:
        st.success(f"✅ **Empfehlung:** Über den **Lötschberg** bist du ca. **{total_f - total_l} Minuten** früher am Ziel.")
