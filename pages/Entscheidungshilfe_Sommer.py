import streamlit as st
import datetime
from logic import (
    get_latest_wait_times, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_furka_status,
    get_pass_status
)

# 1. Seiteneinstellungen
st.set_page_config(page_title="Routen-Check Wallis | Sommer", layout="wide")

# 2. Titel
st.title("☀️ Entscheidungshilfe Sommer: Deine Reise nach Ried-Mörel")
st.info("Vergleich zwischen Passstrassen und Autoverlad (inkl. aktueller Verkehrslage).")

start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Sommer-Route berechnen"):
    with st.spinner("Frage Verkehrsdaten für Pässe und Verlade ab..."):
        jetzt = datetime.datetime.now()
        
        # --- 1. PASS-ROUTEN (DIREKT) ---
        # Google Maps berechnet hier die Zeit über die Pässe inkl. aktuellem Verkehr
        zeit_furkapass = get_google_maps_duration(start, "Ried-Mörel", avoid_tolls=False) # Via Furkapass
        # Für Grimsel & Nufenen geben wir Zwischenziele an, um die Route zu erzwingen
        zeit_grimsel = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Grimselpass"])
        zeit_nufenen = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Airolo", "Nufenenpass"])

        # --- 2. AUTOVERLAD-ROUTEN (WIE GEWOHNT) ---
        furka_aktiv = get_furka_status()
        
        # Furka Verlad
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        if furka_aktiv:
            ankunft_realp = jetzt + datetime.timedelta(minutes=anfahrt_f)
            naechster_zug_f = get_furka_departure(ankunft_realp)
            if naechster_zug_f:
                effektive_warte_f = max(int((naechster_zug_f - ankunft_realp).total_seconds() / 60), get_latest_wait_times("Realp"))
                total_f_verlad = anfahrt_f + effektive_warte_f + 25 + get_google_maps_duration("Oberwald", "Ried-Mörel")
            else: total_f_verlad = 9999
        else: total_f_verlad = 999999

        # Lötschberg Verlad
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
        naechster_zug_l = get_loetschberg_departure(ankunft_kandersteg)
        if naechster_zug_l:
            effektive_warte_l = max(int((naechster_zug_l - ankunft_kandersteg).total_seconds() / 60), get_latest_wait_times("Kandersteg"))
            total_l_verlad = anfahrt_l + effektive_warte_l + 20 + get_google_maps_duration("Goppenstein", "Ried-Mörel")
        else: total_l_verlad = 9999

    # --- UI DARSTELLUNG ---
    
    # Erste Reihe: Die 3 Pässe
    st.subheader("⛰️ Über die Passstrassen")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Via Furkapass", f"{zeit_furkapass} Min")
        st.write("🏎️ Direkte Fahrt über den Pass")
    
    with col2:
        st.metric("Via Grimselpass", f"{zeit_grimsel} Min")
        st.write("🏎️ Via Brünig und Grimsel")
        
    with col3:
        st.metric("Via Nufenenpass", f"{zeit_nufenen} Min")
        st.write("🏎️ Via Gotthard und Nufenen")

    st.divider()

    # Zweite Reihe: Die Verlade
    st.subheader("🚂 Via Autoverlad (Sommerbetrieb)")
    col_f, col_l = st.columns(2)

    with col_f:
        if not furka_aktiv:
            st.error("🚨 Furka Verlad eingestellt")
        else:
            st.metric("Autoverlad Furka", f"{total_f_verlad} Min", delta=f"{total_f_verlad - zeit_furkapass} vs Pass")
            st.write(f"⏳ Wartezeit Realp: {effektive_warte_f} Min")

    with col_l:
        st.metric("Autoverlad Lötschberg", f"{total_l_verlad} Min")
        st.write(f"⏳ Wartezeit Kandersteg: {effektive_warte_l} Min")

    # --- FAZIT SOMMER ---
    st.divider()
    routen = {
        "den Furkapass": zeit_furkapass,
        "den Grimselpass": zeit_grimsel,
        "den Nufenenpass": zeit_nufenen,
        "den Autoverlad Furka": total_f_verlad,
        "den Autoverlad Lötschberg": total_l_verlad
    }
    
    beste_route = min(routen, key=routen.get)
    st.success(f"✅ **Sommer-Empfehlung:** Nimm **{beste_route}**. Das ist aktuell der schnellste Weg nach Ried-Mörel.")
