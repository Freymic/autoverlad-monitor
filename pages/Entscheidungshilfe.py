import streamlit as st
import datetime
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
        
        # Nutzt die neue Logik aus der logic.py (inkl. Sprung zum nächsten Tag)
        naechster_zug_f = get_furka_departure(ankunft_realp)
        
        if naechster_zug_f:
            wartezeit_fahrplan_f = int((naechster_zug_f - ankunft_realp).total_seconds() / 60)
            stau_f = get_latest_wait_times("Realp")
            effektive_warte_f = max(wartezeit_fahrplan_f, stau_f)
            
            zug_f_dauer = 25 
            ziel_f = get_google_maps_duration("Oberwald", "Ried-Mörel")
            total_f = anfahrt_f + effektive_warte_f + zug_f_dauer + ziel_f
            ankunft_ziel_f = jetzt + datetime.timedelta(minutes=total_f)
        else:
            total_f = 9999

        # --- ROUTE B: LÖTSCHBERG (KANDERSTEG) ---
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
        
        # Einfache Takt-Logik für Lötschberg (.20 / .50)
        if ankunft_kandersteg.minute <= 10: dep_m = 20
        elif ankunft_kandersteg.minute <= 40: dep_m = 50
        else:
            dep_m = 20
            # Hier fehlt noch die Logik für den Stundenwechsel, falls nötig
        
        # HIER WAR DER FEHLER: Variable konsistent benennen
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
            ist_morgen_f = naechster_zug_f.date() > ankunft_realp.date()
            tag_text_f = " (Morgen)" if ist_morgen_f else ""
            
            st.metric("Ankunft Ried-Mörel", ankunft_ziel_f.strftime('%H:%M'), f"{total_f} Min Gesamt")
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Realp: **{anfahrt_f} Min**")
            st.write(f"🏎️ **Ankunft Terminal:** {ankunft_realp.strftime('%H:%M')}")
            
            if ist_morgen_f:
                st.info("🌙 Keine Züge mehr für heute. Erster Zug morgen berechnet.")
            
            st.warning(f"⏳ **Wartezeit:** {effektive_warte_f} Min")
            st.write(f"🚂 **Abfahrt Realp:** {naechster_zug_f.strftime('%H:%M')}{tag_text_f}")
            st.write(f"🚂 **Zugfahrt:** {zug_f_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_f} Min**")
            st.success(f"🏁 **Ziel Ried-Mörel:** {ankunft_ziel_f.strftime('%H:%M')}{tag_text_f}")

    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        st.metric("Ankunft Ried-Mörel", ankunft_ziel_l.strftime('%H:%M'), f"{total_l} Min Gesamt")
        st.write(f"🏠 **Start:** {start}")
        st.write(f"⬇️ Fahrt bis Kandersteg: **{anfahrt_l} Min**")
        st.write(f"🏎️ **Ankunft Terminal:** {ankunft_kandersteg.strftime('%H:%M')}")
        
        # Korrigierter Variablenname für die Anzeige
        st.warning(f"⏳ **Wartezeit:** {wartezeit_l} Min") 
        
        st.write(f"🚂 **Zugfahrt:** {zug_l_dauer} Min")
        st.write(f"⬇️ Restliche Fahrt: **{ziel_l} Min**")
        st.success(f"🏁 **Ziel Ried-Mörel:** {ankunft_ziel_l.strftime('%H:%M')}")

    st.divider()
    # Empfehlungs-Logik
    if total_f < total_l:
        st.success(f"✅ **Empfehlung:** Über den **Furka** sparst du Zeit.")
    else:
        st.success(f"✅ **Empfehlung:** Über den **Lötschberg** sparst du Zeit.")
