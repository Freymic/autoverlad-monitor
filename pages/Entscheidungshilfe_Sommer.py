import streamlit as st
import datetime
from logic import (
    fetch_all_data, 
    get_google_maps_duration, 
    get_furka_departure, 
    get_loetschberg_departure,
    get_pass_status,
    get_gemini_summer_report
)

st.set_page_config(page_title="Sommer-Check", layout="wide")

st.title("☀️ Sommer-Entscheidungshilfe")
start = st.text_input("Startpunkt:", value="Buchrain")

if st.button("Berechnen"):
    payload = fetch_all_data() # Einmal aufrufen für alles!
    p_status = get_pass_status()
    
    # Beispiel Logik
    st.write(f"Status Furka Verlad: {'✅ Offen' if payload['active_status']['furka'] else '❌ Gesperrt'}")
    st.metric("Wartezeit Realp", f"{payload['wait_times']['Realp']['min']} Min")
    
    # Rest deiner UI...
