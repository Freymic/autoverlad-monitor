import streamlit as st
import datetime
# Wichtig: get_loetschberg_departure muss in der logic.py vorhanden sein!
from logic import (
    get_latest_wait_times, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure
)

st.set_page_config(page_title="Routen-Check Wallis", layout="wide")

st.title("🚗 Deine Reise nach Ried-Mörel")
start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Route jetzt berechnen"):
    with st.spinner("Berechne Fahrplan und Verkehrsdaten..."):
        jetzt = datetime.datetime.now()
        
        # --- ROUTE A: FURKA (REALP) ---
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        ankunft_realp = jetzt + datetime.timedelta(minutes=anfahrt_f)
        
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
        
        # NEU: Nutzt jetzt deine präzise Logik aus logic.py
        naechster_zug_l = get_loetschberg_departure(ankunft_kandersteg)
        
        if naechster_zug_l:
            wartezeit_fahrplan_l = int((naechster_zug_l - ankunft_kandersteg).total_seconds() / 60)
            stau_l = get_latest_wait_times("Kandersteg")
            # Die echte Wartezeit vor Ort
            effektive_warte_l = max(wartezeit_fahrplan_l, stau_l)
            
            zug_l_dauer = 20
            ziel_l = get_google_maps_duration("Goppenstein", "Ried-Mörel")
            total_l = anfahrt_l + effektive_warte_l + zug_l_dauer + ziel_l
            ankunft_ziel_l = jetzt + datetime.timedelta(minutes=total_l)
        else:
            total_l = 9999

    # --- ANZEIGE IN ZWEI SPALTEN ---
    col_f, col_l = st.columns(2)

    with col_f:
        st.subheader("🏔️ Via Furka (Realp)")
        if naechster_zug_f:
            ist_morgen_f = naechster_zug_f.date() > ankunft_realp.date()
            tag_text_f = " (Morgen)" if ist_morgen_f else ""
            
            st.metric("Ankunft Ried-Mörel", ankunft_ziel_f.strftime('%H:%M'), f"{total_f} Min")
            if ist_morgen_f:
                st.info("🌙 Erster Zug morgen früh berechnet.")
            
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Realp: **{anfahrt_f} Min**")
            st.write(f"🏎️ **Ankunft Terminal:** {ankunft_realp.strftime('%H:%M')}")
            st.warning(f"⏳ **Wartezeit:** {effektive_warte_f} Min")
            st.write(f"🚂 **Abfahrt Realp:** {naechster_zug_f.strftime('%H:%M')}{tag_text_f}")
            st.write(f"🚂 **Zugfahrt:** {zug_f_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_f} Min**")
            st.success(f"🏁 **Ziel:** {ankunft_ziel_f.strftime('%H:%M')}{tag_text_f}")

    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        if naechster_zug_l:
            ist_morgen_l = naechster_zug_l.date() > ankunft_kandersteg.date()
            tag_text_l = " (Morgen)" if ist_morgen_l else ""
            
            st.metric("Ankunft Ried-Mörel", ankunft_ziel_l.strftime('%H:%M'), f"{total_l} Min")
            if ist_morgen_l:
                st.info("🌙 Erster Zug morgen früh berechnet.")
            
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Kandersteg: **{anfahrt_l} Min**")
            st.write(f"🏎️ **Ankunft Terminal:** {ankunft_kandersteg.strftime('%H:%M')}")
            st.warning(f"⏳ **Wartezeit:** {effektive_warte_l} Min")
            st.write(f"🚂 **Abfahrt Kandersteg:** {naechster_zug_l.strftime('%H:%M')}{tag_text_l}")
            st.write(f"🚂 **Zugfahrt:** {zug_l_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_l} Min**")
            st.success(f"🏁 **Ziel:** {ankunft_ziel_l.strftime('%H:%M')}{tag_text_l}")

    st.divider()
    # Empfehlungs-Logik
    if total_f < total_l:
        st.success(f"✅ **Empfehlung:** Über den **Furka** sparst du heute ca. {total_l - total_f} Minuten.")
    else:
        st.success(f"✅ **Empfehlung:** Über den **Lötschberg** sparst du heute ca. {total_f - total_l} Minuten.")
