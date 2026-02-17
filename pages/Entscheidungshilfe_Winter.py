import streamlit as st
import datetime
from logic import (
    get_latest_wait_times, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_furka_status,
    get_loetschberg_status,
    get_gemini_winter_report  # Neu importiert
)

# 1. Seiteneinstellungen umbenannt
st.set_page_config(page_title="Routen-Check Wallis | Winter", layout="wide")

# 2. Titel angepasst
st.title("❄️ Entscheidungshilfe Winter: Deine Reise nach Ried-Mörel")
st.info("Diese Ansicht berücksichtigt die Autoverlade Furka & Lötschberg.")

start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Route jetzt berechnen"):
    with st.spinner("Frage Verkehrsdaten und Fahrpläne ab..."):
        jetzt = datetime.datetime.now()
        
        # --- DATENABFRAGE & STATUS ---
        furka_aktiv = get_furka_status()
        
        # --- ROUTE A: FURKA (REALP) ---
        anfahrt_f = get_google_maps_duration(start, "Autoverlad Realp")
        if furka_aktiv:
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
        else:
            total_f = 999999
            naechster_zug_f = None

        # --- ROUTE B: LÖTSCHBERG (KANDERSTEG) ---
        anfahrt_l = get_google_maps_duration(start, "Autoverlad Kandersteg")
        ankunft_kandersteg = jetzt + datetime.timedelta(minutes=anfahrt_l)
        naechster_zug_l = get_loetschberg_departure(ankunft_kandersteg)
        if naechster_zug_l:
            wartezeit_fahrplan_l = int((naechster_zug_l - ankunft_kandersteg).total_seconds() / 60)
            stau_l = get_latest_wait_times("Kandersteg")
            effektive_warte_l = max(wartezeit_fahrplan_l, stau_l)
            zug_l_dauer = 20
            ziel_l = get_google_maps_duration("Goppenstein", "Ried-Mörel")
            total_l = anfahrt_l + effektive_warte_l + zug_l_dauer + ziel_l
            ankunft_ziel_l = jetzt + datetime.timedelta(minutes=total_l)
        else:
            total_l = 9999

    # --- UI DARSTELLUNG ---
    col_f, col_l = st.columns(2)

    # --- SPALTE FURKA ---
    with col_f:
        st.subheader("🏔️ Via Furka (Realp)")
        if not furka_aktiv:
            st.error("🚨 **BETRIEB EINGESTELLT**")
            st.info("Der Autoverlad Furka meldet aktuell einen Unterbruch.")
            st.write(f"🏎️ Anfahrt bis Autoverlad Realp: **{anfahrt_f} Min**")
        elif naechster_zug_f:
            ist_morgen_f = naechster_zug_f.date() > jetzt.date()
            label_f = "Ankunft (MORGEN)" if ist_morgen_f else "Ankunft Ried-Mörel"
            
            st.metric(label_f, ankunft_ziel_f.strftime('%H:%M'), f"{total_f} Min Gesamt")
            
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Autoverlad Realp: **{anfahrt_f} Min**")
            st.write(f"🏎️ **Ankunft Autoverlad Realp:** {ankunft_realp.strftime('%H:%M')}")
            
            if ist_morgen_f:
                st.warning(f"⏳ **Nachtpause:** {effektive_warte_f // 60}h {effektive_warte_f % 60}min")
            else:
                st.warning(f"⏳ **Wartezeit:** {effektive_warte_f} Min")
                
            tag_f = " (Morgen)" if ist_morgen_f else ""
            st.write(f"🚂 **Abfahrt Realp:** {naechster_zug_f.strftime('%H:%M')}{tag_f}")
            st.write(f"🚂 **Zugfahrt:** {zug_f_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_f} Min**")
            st.success(f"🏁 **Ziel Ried-Mörel:** {ankunft_ziel_f.strftime('%H:%M')}{tag_f}")
        else:
            st.error("Kein Fahrplan verfügbar.")

    # --- SPALTE LÖTSCHBERG ---
    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        if naechster_zug_l:
            ist_morgen_l = naechster_zug_l.date() > jetzt.date()
            label_l = "Ankunft (MORGEN)" if ist_morgen_l else "Ankunft Ried-Mörel"
            
            st.metric(label_l, ankunft_ziel_l.strftime('%H:%M'), f"{total_l} Min Gesamt")
            
            st.write(f"🏠 **Start:** {start}")
            st.write(f"⬇️ Fahrt bis Autoverlad Kandersteg: **{anfahrt_l} Min**")
            st.write(f"🏎️ **Ankunft Autoverlad Kandersteg:** {ankunft_kandersteg.strftime('%H:%M')}")
            
            if ist_morgen_l:
                st.warning(f"⏳ **Nachtpause:** {effektive_warte_l // 60}h {effektive_warte_l % 60}min")
            else:
                st.warning(f"⏳ **Wartezeit:** {effektive_warte_l} Min")
                
            tag_l = " (Morgen)" if ist_morgen_l else ""
            st.write(f"🚂 **Abfahrt Kandersteg:** {naechster_zug_l.strftime('%H:%M')}{tag_l}")
            st.write(f"🚂 **Zugfahrt:** {zug_l_dauer} Min")
            st.write(f"⬇️ Restliche Fahrt: **{ziel_l} Min**")
            st.success(f"🏁 **Ziel Ried-Mörel:** {ankunft_ziel_l.strftime('%H:%M')}{tag_l}")

   # --- GEMINI WINTER AI REPORT ---
    st.divider()
    st.subheader("🤖 Der Gemini Experten-Check")
    
    # Hier packen wir jetzt ALLES rein, was wir oben berechnet haben
    winter_daten_komplett = {
        "start": start,
        "furka_aktiv": furka_aktiv,
        "total_f": total_f if 'total_f' in locals() else None,
        "total_l": total_l,
        "warte_f": effektive_warte_f if 'effektive_warte_f' in locals() else 0,
        "warte_l": effektive_warte_l,
        "abfahrt_f": naechster_zug_f.strftime('%H:%M') if naechster_zug_f else "Keine",
        "abfahrt_l": naechster_zug_l.strftime('%H:%M') if naechster_zug_l else "Keine"
    }

    with st.spinner("Gemini analysiert Fahrpläne und Status..."):
        ai_bericht = get_gemini_winter_report(winter_daten_komplett)
        st.info(ai_bericht, icon="❄️")

    # --- FAZIT ---
    st.divider()
    if not furka_aktiv:
        st.warning("👉 **Empfehlung:** Da der Furka aktuell geschlossen ist, bleibt nur die Route über den Lötschberg.")
    elif total_f < total_l:
        st.success(f"✅ **Empfehlung:** Über den **Furka** sparst du ca. {total_l - total_f} Minuten.")
    else:
        st.success(f"✅ **Empfehlung:** Über den **Lötschberg** sparst du ca. {total_f - total_l} Minuten.")
