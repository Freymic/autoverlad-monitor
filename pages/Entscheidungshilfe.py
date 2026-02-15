import streamlit as st
from logic import get_latest_wait_times, get_google_maps_duration

st.title("🏔️ Live-Routenvergleich ins Wallis")

start = st.text_input("Dein Startpunkt:", value="Buchrain")

if st.button("Route jetzt prüfen"):
    with st.spinner("Berechne Fahrzeiten inkl. Verkehr..."):
        # --- ROUTE A: FURKA ---
        anfahrt_realp = get_google_maps_duration(start, "Autoverlad Realp")
        wartezeit_realp = get_latest_wait_times("Realp")
        weiterfahrt_ried = get_google_maps_duration("Oberwald", "Ried-Mörel")
        total_furka = anfahrt_realp + wartezeit_realp + 20 + weiterfahrt_ried
        
        # --- ROUTE B: LÖTSCHBERG ---
        anfahrt_kandersteg = get_google_maps_duration(start, "Autoverlad Kandersteg")
        wartezeit_kandersteg = get_latest_wait_times("Kandersteg")
        weiterfahrt_ried_b = get_google_maps_duration("Goppenstein", "Ried-Mörel")
        total_loetsch = anfahrt_kandersteg + wartezeit_kandersteg + 15 + weiterfahrt_ried_b

        # --- ANZEIGE ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Furka", f"{total_furka} Min", f"{anfahrt_realp} Min Fahrt")
            st.caption(f"Ankunft Realp ca.: {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_realp)).strftime('%H:%M')}")

        with col2:
            st.metric("Lötschberg", f"{total_loetsch} Min", f"{anfahrt_kandersteg} Min Fahrt")
            st.caption(f"Ankunft Kandersteg ca.: {(datetime.datetime.now() + datetime.timedelta(minutes=anfahrt_kandersteg)).strftime('%H:%M')}")

        if total_furka < total_loetsch:
            st.success(f"👉 Nimm den **Furka**! Du sparst {total_loetsch - total_furka} Minuten.")
        else:
            st.success(f"👉 Nimm den **Lötschberg**! Du sparst {total_furka - total_loetsch} Minuten.")
