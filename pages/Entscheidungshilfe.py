import streamlit as st
import pandas as pd
# Hier deine logic.py Funktionen importieren
from logic import get_latest_wait_times, get_google_maps_duration 

st.title("🚗 Routen-Check: Wallis")

# 1. Startpunkt wählen
start = st.text_input("Startpunkt", value="Zürich") # Oder GPS nutzen

if st.button("Beste Route berechnen"):
    # Daten abrufen
    wait_realp = get_latest_wait_times("Realp")
    wait_kandersteg = get_latest_wait_times("Kandersteg")
    
    # Fahrzeiten via Google API
    drive_to_realp = get_google_maps_duration(start, "Autoverlad Realp")
    drive_to_kandersteg = get_google_maps_duration(start, "Autoverlad Kandersteg")
    
    # Visualisierung in Spalten
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Furka (Realp)")
        total_furka = drive_to_realp + wait_realp + 20 + 54
        st.metric("Gesamtzeit", f"{total_furka} Min")
        st.write(f"Wartezeit Realp: {wait_realp} Min")

    with col2:
        st.subheader("Lötschberg")
        total_loetsch = drive_to_kandersteg + wait_kandersteg + 15 + 44
        st.metric("Gesamtzeit", f"{total_loetsch} Min")
        st.write(f"Wartezeit Kandersteg: {wait_kandersteg} Min")
