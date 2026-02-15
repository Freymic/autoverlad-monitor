import streamlit as st
import datetime
# Importiere die Logik-Funktionen aus deiner logic.py
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
    with st.spinner("Frage Verkehrsdaten und Fahrpläne ab..."):
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

    # --- ANZEIGE DER ERGEBNISSE ---
    col_f, col_l = st.columns(2)

    # SPALTE FURKA
    with col_f:
        st.subheader("🏔️ Via Furka (Realp)")
        if naechster_zug_f:
            ist_morgen_f = naechster_zug_f.date() > jetzt.date()
            
            if ist_morgen_f:
                st.error(f"📅 **Abfahrt erst morgen, {naechster_zug_f.strftime('%d.%m.')}**")
                st.metric("Ankunft", ankunft_ziel_f.strftime('%H:%M'), "MORGEN", delta_color="inverse")
                # Wartezeit in Stunden anzeigen
                st.warning(f"⏳ **Nachtpause:** {effektive_warte_f // 60}h {effektive_warte_f % 60}min warten.")
            else:
                st.metric("Ankunft", ankunft_ziel_f.strftime('%H:%M'), f"{total_f} Min")
                st.warning(f"⏳ **Wartezeit:** {effektive_warte_f} Min")

            st.write(f"🏎️ Ankunft Terminal: {ankunft_realp.strftime('%H:%M')}")
            st.write(f"🚂 Nächster Zug: **{naechster_zug_f.strftime('%H:%M')} Uhr**")
            st.write(f"🏁 Ziel Ried-Mörel: {ankunft_ziel_f.strftime('%H:%M')} Uhr")
        else:
            st.error("Kein Fahrplan für Furka gefunden.")

    # SPALTE LÖTSCHBERG
    with col_l:
        st.subheader("🚆 Via Lötschberg (Kandersteg)")
        if naechster_zug_l:
            ist_morgen_l = naechster_zug_l.date() > jetzt.date()
            
            if ist_morgen_l:
                st.error(f"📅 **Abfahrt erst morgen, {naechster_zug_l.strftime('%d.%m.')}**")
                st.metric("Ankunft", ankunft_ziel_l.strftime('%H:%M'), "MORGEN", delta_color="inverse")
                st.warning(f"⏳ **Nachtpause:** {effektive_warte_l // 60}h {effektive_warte_l % 60}min warten.")
            else:
                st.metric("Ankunft", ankunft_ziel_l.strftime('%H:%M'), f"{total_l} Min")
                st.warning(f"⏳ **Wartezeit:** {effektive_warte_l} Min")

            st.write(f"🏎️ Ankunft Terminal: {ankunft_kandersteg.strftime('%H:%M')}")
            st.write(f"🚂 Nächster Zug: **{naechster_zug_l.strftime('%H:%M')} Uhr**")
            st.write(f"🏁 Ziel Ried-Mörel: {ankunft_ziel_l.strftime('%H:%M')} Uhr")
        else:
            st.error("Kein Fahrplan für Lötschberg gefunden.")

    # --- FAZIT ---
    st.divider()
    
    # Spezialfall: Beide Routen erst morgen möglich
    if (naechster_zug_f and naechster_zug_f.date() > jetzt.date()) and \
       (naechster_zug_l and naechster_zug_l.date() > jetzt.date()):
        st.info("💡 **Geduld ist gefragt:** Beide Autoverlade haben aktuell Nachtpause. Es spielt keine grosse Rolle, welche Route du nimmst – du kommst bei beiden erst morgen früh an.")
    
    # Normale Empfehlung
    elif total_f < total_l:
        st.success(f"✅ **Empfehlung:** Nimm den **Furka**. Du sparst ca. {total_l - total_f} Minuten.")
    else:
        st.success(f"✅ **Empfehlung:** Nimm den **Lötschberg**. Du sparst ca. {total_f - total_l} Minuten.")
