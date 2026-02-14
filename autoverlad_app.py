import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from streamlit_autorefresh import st_autorefresh
from logic import fetch_furka_data, fetch_loetschberg_data, get_quantized_timestamp, DB_NAME, CH_TZ

# --- UI SETUP ---
st.set_page_config(page_title="Alpen-Verlad PRO", layout="wide")
st_autorefresh(interval=5 * 60 * 1000, key="global_refresh")

# --- DATA FLOW ---
# Wir rufen die Funktionen aus logic.py auf
furka = fetch_furka_data()
bls = fetch_loetschberg_data()
all_data = {**furka, **bls}

# Hier käme der Aufruf zur DB-Speicherung (ebenfalls in logic.py ausgelagert)
# save_to_db(all_data, get_quantized_timestamp())

st.title("🏔️ Alpen-Verlad Monitor")

# Metriken anzeigen
cols = st.columns(4)
for i, (name, d) in enumerate(all_data.items()):
    cols[i].metric(label=name, value=f"{d['min']} Min")

# --- TREND CHART ---
# (Hier bleibt der Altair-Code, da er direkt UI-Elemente erzeugt)
