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

def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    raw_text_debug = ""
    
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        soup_f = BeautifulSoup(r_f.content, 'html.parser')
        text_f = " ".join(soup_f.get_text(separator=' ').split())
        raw_text_debug = text_f[:1500]
        
        for station in ["Realp", "Oberwald"]:
            # Suche im Umkreis von 500 Zeichen
            match = re.search(f"(.{{0,500}}{station}.{{0,500}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                zahlen = re.findall(r'(\d+)\s*(?:Min|min|Minuten|h|Std)', kontext)
                if zahlen:
                    daten[station] = int(zahlen[0])
                # Spezialfall: Wenn 'Wartezeit' vorkommt aber keine Zahl direkt dabei steht
                elif "Wartezeit" in kontext and any(x in kontext for x in ["30", "60", "90"]):
                    find_val = re.findall(r'(30|60|90|120)', kontext)
                    if find_val: daten[station] = int(find_val[0])

        # --- LÖTSCHBERG (BLS) ---
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = " ".join(BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ').split())
        
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"(.{{0,400}}{station}.{{0,400}})", text_l, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                zahlen = re.findall(r'(\d+)\s*(?:Min|min|h|Std)', kontext)
                if zahlen: daten[station] = int(zahlen[0])

    except Exception as e:
        st.sidebar.error(f"Scraping Fehler: {e}")
        
    return daten, raw_text_debug

# --- 2. LOGIK ---
st.set_page_config(page_title="Autoverlad Monitor", layout="wide")
aktuelle_werte, raw_debug = fetch_wartezeiten()

# Speichern in CSV
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_new = pd.DataFrame([{"Zeit": now, **aktuelle_werte}])
if not os.path.isfile(DB_FILE):
    df_new.to_csv(DB_FILE, index=False)
else:
    df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI ---
st.title("🏔️ Autoverlad Live-Monitor")

c1, c2, c3, c4 =
