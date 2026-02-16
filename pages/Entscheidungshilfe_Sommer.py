import streamlit as st
import datetime
from logic import (
    get_latest_wait_times, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_furka_status,
    get_pass_status  # Wichtig: Muss importiert sein
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
        # Wir holen erst den Status, bevor wir rechnen
        pass_status = get_pass_status()
        
        # --- 1. PASS-ROUTEN (DIREKT) ---
        
        # A) FURKAPASS
        if pass_status.get("Furkapass", False):
            zeit_furkapass = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Furkapass"])
        else:
            zeit_furkapass = 9999 # Markierung für "Nicht verfügbar"

        # B) GRIMSELPASS (via Brünig)
        # Logik: Grimsel muss offen sein. Brünig ist fast immer offen, wir prüfen ihn trotzdem.
        if pass_status.get("Grimselpass", False) and pass_status.get("Brünigpass", True):
            zeit_grimsel = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Brünigpass", "Grimselpass"])
        else:
            zeit_grimsel = 9999

        # C) NUFENENPASS (via Gotthard)
        if pass_status.get("Nufenenpass", False):
            zeit_nufenen = get_google_maps_duration(start, "Ried-Mörel", waypoints=["Airolo", "Nufenenpass"])
        else:
            zeit_nufenen = 9999

        # --- 2. AUTOVERLAD-ROUTEN ---
        furka_verlad_aktiv = get_furka_status()
        
        # Furka Verlad
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        if furka_verlad_aktiv:
            ankunft_realp = jetzt + datetime.timedelta(minutes=anfahrt_f)
            naechster_zug_f = get_furka_departure(ankunft_realp)
            if naechster_zug_f:
                # Wartezeit: Minimum Fahrplan vs. Realer Stau
                warte_min = int((naechster_zug_f - ankunft_realp).total_seconds() / 60)
                effektive_warte_f = max(warte_min, get_latest_wait_times("Realp"))
                
                # 25 Min Zug + Fahrt Oberwald->Ried-Mörel
                total_f_verlad = anfahrt_f + effektive_warte_f + 25 + get_google_maps_duration("Oberwald", "Ried-Mörel")
            else: 
                total_f_verlad = 9999
        else: 
            total_f_verlad = 999999 # Sperrung Verlad

        # Lötschberg Verlad
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
        naechster_zug_l = get_loetschberg_departure(ankunft_kandersteg)
        if naechster_zug_l:
            warte_min_l = int((naechster_zug_l - ankunft_kandersteg).total_seconds() / 60)
            effektive_warte_l = max(warte_min_l, get_latest_wait_times("Kandersteg"))
            
            # 20 Min Zug + Fahrt Goppenstein->Ried-Mörel
            total_l_verlad = anfahrt_l + effektive_warte_l + 20 + get_google_maps_duration("Goppenstein", "Ried-Mörel")
        else: 
            total_l_verlad = 9999

    # --- UI DARSTELLUNG ---
    
    st.subheader("⛰️ Über die Passstrassen")
    col1, col2, col3 = st.columns(3)
    
    # Spalte 1: Furkapass
    with col1:
        if pass_status.get("Furkapass", False):
            st.metric("Via Furkapass", f"{zeit_furkapass} Min")
            st.write("✅ Pass offen")
        else:
            st.metric("Via Furkapass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")
    
    # Spalte 2: Grimselpass
    with col2:
        if pass_status.get("Grimselpass", False):
            st.metric("Via Grimselpass", f"{zeit_grimsel} Min")
            st.write("✅ Pass offen (via Brünig)")
        else:
            st.metric("Via Grimselpass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")
        
    # Spalte 3: Nufenenpass
    with col3:
        if pass_status.get("Nufenenpass", False):
            st.metric("Via Nufenenpass", f"{zeit_nufenen} Min")
            st.write("✅ Pass offen (via Gotthard)")
        else:
            st.metric("Via Nufenenpass", "GESPERRT", "Wintersperre", delta_color="inverse")
            st.write("❌ Pass geschlossen")

    st.divider()

    st.subheader("🚂 Via Autoverlad")
    col_f, col_l = st.columns(2)

    with col_f:
        if not furka_verlad_aktiv:
            st.error("🚨 Autoverlad Furka eingestellt")
        elif total_f_verlad >= 9999:
             st.error("Kein Zug mehr heute")
        else:
            # Vergleich Pass vs Verlad anzeigen, aber nur wenn Pass offen ist
            delta_msg = None
            if pass_status.get("Furkapass", False):
                diff = total_f_verlad - zeit_furkapass
                if diff > 0: delta_msg = f"{diff} Min langsamer als Pass"
                else: delta_msg = f"{abs(diff)} Min schneller als Pass"
            
            st.metric("Autoverlad Furka", f"{total_f_verlad} Min", delta=delta_msg, delta_color="inverse")
            st.write(f"⏳ Wartezeit Realp: {effektive_warte_f} Min")

    with col_l:
        if total_l_verlad >= 9999:
            st.error("Kein Zug mehr heute")
        else:
            st.metric("Autoverlad Lötschberg", f"{total_l_verlad} Min")
            st.write(f"⏳ Wartezeit Kandersteg: {effektive_warte_l} Min")

    # --- FAZIT SOMMER ---
    st.divider()
    
    # Wir filtern alle Routen raus, die 9999 (geschlossen/unmöglich) sind
    alle_routen = {
        "den Furkapass": zeit_furkapass,
        "den Grimselpass": zeit_grimsel,
        "den Nufenenpass": zeit_nufenen,
        "den Autoverlad Furka": total_f_verlad,
        "den Autoverlad Lötschberg": total_l_verlad
    }
    # Nur Routen behalten, die machbar sind (< 9000 Min)
    machbare_routen = {k: v for k, v in alle_routen.items() if v < 9000}
    
    if machbare_routen:
        beste_route = min(machbare_routen, key=machbare_routen.get)
        schnellste_zeit = machbare_routen[beste_route]
        st.success(f"✅ **Sommer-Empfehlung:** Nimm **{beste_route}** ({schnellste_zeit} Min). Das ist aktuell der schnellste Weg.")
    else:
        st.error("⚠️ Aktuell scheinen alle Routen gesperrt oder nicht verfügbar zu sein.")
