import streamlit as st
import datetime
from logic import (
    fetch_all_data, # Nutzt den Cache!
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_pass_status,
    get_gemini_summer_report
)

st.set_page_config(page_title="Routen-Check Wallis | Sommer", layout="wide", page_icon="☀️")

st.title("☀️ Entscheidungshilfe Sommer")
st.info("Vergleich zwischen Passstrassen und Autoverlad (inkl. KI-Verkehrsanalyse).")

start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Sommer-Route berechnen"):
    with st.spinner("Synchronisiere Pässe, Verkehr und Verlade..."):
        jetzt = datetime.datetime.now()
        
        # --- 1. ZENTRALER DATEN-SNAPSHOT ---
        payload = fetch_all_data()
        wait_times = payload["wait_times"]
        active_status = payload["active_status"]
        pass_status = get_pass_status()

        # --- 2. PASS-ROUTEN ---
        # Wir berechnen Google Maps nur, wenn der Pass auch offen ist
        zeit_furka_p = get_google_maps_duration(start, "Ried-Mörel", ["Furkapass"]) if pass_status.get("Furkapass") else 9999
        zeit_grimsel_p = get_google_maps_duration(start, "Ried-Mörel", ["Brünigpass", "Grimselpass"]) if pass_status.get("Grimselpass") else 9999
        zeit_nufenen_p = get_google_maps_duration(start, "Ried-Mörel", ["Airolo", "Nufenenpass"]) if pass_status.get("Nufenenpass") else 9999

        # --- 3. VERLAD-ROUTEN (LOGIK-REFACTORING) ---
        def calc_verlad(provider, start_node, end_node, station_name, zug_dauer):
            if not active_status.get(provider): return 999999, 0
            
            anfahrt = get_google_maps_duration(start, start_node)
            ankunft_st = jetzt + datetime.timedelta(minutes=anfahrt)
            
            # Fahrplan-Check
            dep_func = get_furka_departure if provider == "furka" else get_loetschberg_departure
            next_zug = dep_func(ankunft_st)
            
            if not next_zug: return 9999, 0
            
            warte_fp = int((next_zug - ankunft_st).total_seconds() / 60)
            warte_real = wait_times.get(station_name, {}).get("min", 0)
            effektive_warte = max(warte_fp, warte_real)
            
            total = anfahrt + effektive_warte + zug_dauer + get_google_maps_duration(end_node, "Ried-Mörel")
            return total, effektive_warte

        total_f_verlad, warte_f = calc_verlad("furka", "Autoverlad Realp", "Oberwald", "Realp", 25)
        total_l_verlad, warte_l = calc_verlad("loetschberg", "Autoverlad Kandersteg", "Goppenstein", "Kandersteg", 20)

    # --- UI DARSTELLUNG (Kompakt) ---
    st.subheader("⛰️ Pässe vs. 🚂 Verlad")
    c1, c2, c3 = st.columns(3)
    c1.metric("Via Furkapass", f"{zeit_furka_p} Min" if zeit_furka_p < 9000 else "GESPERRT")
    c2.metric("Autoverlad Furka", f"{total_f_verlad} Min" if total_f_verlad < 9000 else "ZU")
    c3.metric("Autoverlad Lötschberg", f"{total_l_verlad} Min" if total_l_verlad < 9000 else "ZU")

    # --- KI REPORT ---
    st.divider()
    alle_routen = {
        "den Furkapass": zeit_furka_p, "den Grimselpass": zeit_grimsel_p, "den Nufenenpass": zeit_nufenen_p,
        "den Autoverlad Furka": total_f_verlad, "den Autoverlad Lötschberg": total_l_verlad
    }
    st.info(get_gemini_summer_report(alle_routen, pass_status))
