import streamlit as st
import datetime
from logic import (
    fetch_all_data,
    get_google_maps_duration,
    get_furka_departure,
    get_loetschberg_departure,
    get_gemini_winter_report
)

st.set_page_config(page_title="Routen-Check Wallis | Winter", layout="wide", page_icon="❄️")

st.title("❄️ Entscheidungshilfe Winter")
start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Route jetzt berechnen"):
    with st.spinner("Prüfe Winter-Status..."):
        jetzt = datetime.datetime.now()
        payload = fetch_all_data()
        active_status = payload["active_status"]
        wait_times = payload["wait_times"]

        # Helper für saubere Winter-Berechnung
        def get_winter_route(provider, station_label, start_point, end_point, zug_min):
            is_ok = active_status.get(provider)
            anfahrt = get_google_maps_duration(start, start_point)
            
            if not is_ok: return {"ok": False, "anfahrt": anfahrt}
            
            ankunft = jetzt + datetime.timedelta(minutes=anfahrt)
            dep_func = get_furka_departure if provider == "furka" else get_loetschberg_departure
            next_zug = dep_func(ankunft)
            
            if not next_zug: return {"ok": True, "zug": None, "anfahrt": anfahrt}
            
            warte_stau = wait_times.get(station_label, {}).get("min", 0)
            warte_fp = int((next_zug - ankunft).total_seconds() / 60)
            eff_warte = max(warte_stau, warte_fp)
            
            total = anfahrt + eff_warte + zug_min + get_google_maps_duration(end_point, "Ried-Mörel")
            return {
                "ok": True, "zug": next_zug, "total": total, 
                "warte": eff_warte, "anfahrt": anfahrt, 
                "ankunft_ziel": jetzt + datetime.timedelta(minutes=total)
            }

        res_f = get_winter_route("furka", "Realp", "Autoverlad Realp", "Oberwald", 25)
        res_l = get_winter_route("loetschberg", "Kandersteg", "Autoverlad Kandersteg", "Goppenstein", 20)

    # --- UI RENDERING ---
    col_f, col_l = st.columns(2)
    
    for res, col, name in [(res_f, col_f, "Furka (Realp)"), (res_l, col_l, "Lötschberg (Kandersteg)")]:
        with col:
            st.subheader(f"🏔️ {name}")
            if not res["ok"]:
                st.error("🚨 **BETRIEB EINGESTELLT** (KI-Veto)")
            elif not res.get("zug"):
                st.warning("🌙 Keine Züge mehr für heute.")
            else:
                st.metric("Ankunft Ried-Mörel", res["ankunft_ziel"].strftime('%H:%M'), f"{res['total']} Min")
                st.caption(f"Anfahrt: {res['anfahrt']}min | Wartezeit: {res['warte']}min")

    # --- AI EXPERTEN CHECK ---
    st.divider()
    winter_json = {
        "furka_aktiv": active_status["furka"],
        "loetschberg_aktiv": active_status["loetschberg"],
        "total_f": res_f.get("total", 9999),
        "total_l": res_l.get("total", 9999),
        "abfahrt_f": res_f["zug"].strftime('%H:%M') if res_f.get("zug") else "Keine",
        "abfahrt_l": res_l["zug"].strftime('%H:%M') if res_l.get("zug") else "Keine"
    }
    st.info(get_gemini_winter_report(winter_json))
