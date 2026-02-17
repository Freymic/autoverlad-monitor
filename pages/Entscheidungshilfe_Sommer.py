import streamlit as st
import datetime
from logic import (
    get_latest_wait_times, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_furka_status,
    get_loetschberg_status, # Neu importiert
    get_pass_status,
    get_gemini_summer_report
)

# 1. Seiteneinstellungen
st.set_page_config(page_title="Routen-Check Wallis | Sommer", layout="wide")

# 2. Titel
st.title("☀️ Entscheidungshilfe Sommer: Deine Reise nach Ried-Mörel")
st.info("Vergleich zwischen Passstrassen und Autoverlad (inkl. aktueller Verkehrslage).")

start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Sommer-Route berechnen"):
    with st.spinner("Frage Pässe, Verkehr und Verlade ab..."):
        jetzt = datetime.datetime.now()
        
        # --- 0. STATUS CHECK PÄSSE ---
        pass_status = get_pass_status()
        
        # --- 1. PASS-ROUTEN (DIREKT) ---
        if pass_status.get("Furkapass", False):
            zeit_furkapass = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Furkapass"])
        else:
            zeit_furkapass = 9999

        if pass_status.get("Grimselpass", False) and pass_status.get("Brünigpass", True):
            zeit_grimsel = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Brünigpass", "Grimselpass"])
        else:
            zeit_grimsel = 9999

        if pass_status.get("Nufenenpass", False):
            zeit_nufenen = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Airolo", "Nufenenpass"])
        else:
            zeit_nufenen = 9999

        # --- 2. AUTOVERLAD-ROUTEN ---
        furka_verlad_aktiv = get_furka_status()
        loetschberg_verlad_aktiv = get_loetschberg_status() # Neu: Status Lötschberg prüfen
        
        # Furka Verlad Berechnung
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        if furka_verlad_aktiv:
            ankunft_realp = jetzt + datetime.timedelta(minutes=anfahrt_f)
            naechster_zug_f = get_furka_departure(ankunft_realp)
            if naechster_zug_f:
                warte_min = int((naechster_zug_f - ankunft_realp).total_seconds() / 60)
                effektive_warte_f = max(warte_min, get_latest_wait_times("Realp"))
                total_f_verlad = anfahrt_f + effektive_warte_f + 25 + get_google_maps_duration("Oberwald", "Ried-Mörel")
            else: 
                total_f_verlad = 9999
        else: 
            total_f_verlad = 999999

        # Lötschberg Verlad Berechnung
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        if loetschberg_verlad_aktiv: # Neu: Prüfung eingebaut
            ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
            naechster_zug_l = get_loetschberg_departure(ankunft_kandersteg)
            if naechster_zug_l:
                warte_min_l = int((naechster_zug_l - ankunft_kandersteg).total_seconds() / 60)
                effektive_warte_l = max(warte_min_l, get_latest_wait_times("Kandersteg"))
                total_l_verlad = anfahrt_l + effektive_warte_l + 20 + get_google_maps_duration("Goppenstein", "Ried-Mörel")
            else: 
                total_l_verlad = 9999
        else:
            total_l_verlad = 999999

    # --- UI DARSTELLUNG PÄSSE ---
    st.subheader("⛰️ Über die Passstrassen")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if pass_status.get("Furkapass", False):
            st.metric("Via Furkapass", f"{zeit_furkapass} Min")
            st.write("✅ Pass offen")
        else:
            st.metric("Via Furkapass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")
    
    with col2:
        if pass_status.get("Grimselpass", False):
            st.metric("Via Grimselpass", f"{zeit_grimsel} Min")
            st.write("✅ Pass offen (via Brünig)")
        else:
            st.metric("Via Grimselpass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")
        
    with col3:
        if pass_status.get("Nufenenpass", False):
            st.metric("Via Nufenenpass", f"{zeit_nufenen} Min")
            st.write("✅ Pass offen (via Gotthard)")
        else:
            st.metric("Via Nufenenpass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")

    st.divider()

    # --- UI DARSTELLUNG VERLAD ---
    st.subheader("🚂 Via Autoverlad")
    col_f, col_l = st.columns(2)

    with col_f:
        if not furka_verlad_aktiv:
            st.error("🚨 Autoverlad Furka eingestellt")
        elif total_f_verlad >= 9999:
             st.error("Kein Zug mehr heute")
        else:
            delta_msg = None
            if pass_status.get("Furkapass", False):
                diff = total_f_verlad - zeit_furkapass
                delta_msg = f"{diff} Min vs. Pass"
            st.metric("Autoverlad Furka", f"{total_f_verlad} Min", delta=delta_msg, delta_color="inverse")
            st.write(f"⏳ Wartezeit Realp: {effektive_warte_f} Min")

    with col_l:
        if not loetschberg_verlad_aktiv: # Neu: Rote Warnung für Lötschberg
            st.error("🚨 Autoverlad Lötschberg eingestellt")
        elif total_l_verlad >= 9999:
            st.error("Kein Zug mehr heute")
        else:
            st.metric("Autoverlad Lötschberg", f"{total_l_verlad} Min")
            st.write(f"⏳ Wartezeit Kandersteg: {effektive_warte_l} Min")

    # --- GEMINI SUMMER AI REPORT ---
    st.divider()
    st.subheader("🤖 Der Gemini Sommer-Check")
    
    alle_routen = {
        "den Furkapass": zeit_furkapass,
        "den Grimselpass": zeit_grimsel,
        "den Nufenenpass": zeit_nufenen,
        "den Autoverlad Furka": total_f_verlad,
        "den Autoverlad Lötschberg": total_l_verlad
    }

    with st.spinner("Gemini analysiert die schönste Passroute für dich..."):
        # Wir übergeben hier auch den Status der Verlade im Dictionary für Gemini, falls du den Prompt anpassen willst
        ai_bericht = get_gemini_summer_report(alle_routen, pass_status)
        st.info(ai_bericht, icon="☀️")

    # --- FAZIT SOMMER ---
    machbare_routen = {k: v for k, v in alle_routen.items() if v < 9000}
    
    if machbare_routen:
        beste_route = min(machbare_routen, key=machbare_routen.get)
        schnellste_zeit = machbare_routen[beste_route]
        st.success(f"✅ **Mathematische Empfehlung:** Nimm **{beste_route}** ({schnellste_zeit} Min).")
    else:
        st.error("⚠️ Aktuell scheinen alle Routen gesperrt zu sein.")
