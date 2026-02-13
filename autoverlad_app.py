import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. SETUP ---
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

def parse_time_string(text):
    """Rechnet '1 Stunde 30 Minuten' präzise in 90 Minuten um."""
    total_minutes = 0
    found = False
    # Stunden finden
    hr_match = re.search(r'(\d+)\s*(?:Stunde|h|Std)', text, re.IGNORECASE)
    if hr_match:
        total_minutes += int(hr_match.group(1)) * 60
        found = True
    # Minuten finden
    min_match = re.search(r'(\d+)\s*(?:Minute|min|Min)', text, re.IGNORECASE)
    if min_match:
        total_minutes += int(min_match.group(1))
        found = True
    return total_minutes if found else 0

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        text_f = soup_f.get_text(separator=' ')
        
        # Fokus auf den Bereich zwischen 'Verkehrsinformation' und 'aktualisiert'
        if "Verkehrsinformation" in text_f:
            text_f = text_f.split("Verkehrsinformation")[-1]
        if "aktualisiert" in text_f:
            text_f = text_f.split("aktualisiert")[0]
        
        for station in ["Realp", "Oberwald"]:
            match = re.search(f"{station}(.{{0,500}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
