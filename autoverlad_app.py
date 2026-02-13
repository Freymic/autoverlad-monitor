import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
from streamlit_autorefresh import st_autorefresh

# --- 1. AUTOMATISCHER REFRESH (Alle 15 Minuten) ---
st_autorefresh(interval=900000, key="autoverlad_check")

# --- 2. KONFIGURATION & DATEI-SETUP ---
DB_FILE = "wartezeiten_historie.csv"
STATIONEN = {
    "Furka": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
    "Lötschberg": "https://www.bls.ch/de/fahren/autoverlad/fahrplan"
}

# --- 3. FUNKTIONEN ---
def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # Furka (MGB)
        r_f = requests.get(STATIONEN["Furka"], timeout=10)
        soup_f = BeautifulSoup(r_f.content, 'html.parser').get_text()
        if "Realp" in soup_f and "30 Minuten" in soup_f: daten["Realp"] = 30
        if "Realp" in soup_f and "60 Minuten" in soup_f: daten["Realp"] = 60
        # Lötschberg (BLS)
        r_l = requests.get(STATIONEN["Lötschberg"], timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text()
        if "Kandersteg" in soup_l and "30 Min" in soup_l: daten["Kandersteg"] = 30
    except: pass
    return daten

def save_to_csv(neue_daten):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entries = []
    for ort, dauer in neue_daten.items():
        new_entries.append({"Zeit": now, "Ort": ort, "Wartezeit": dauer})
    
    df_new = pd.DataFrame(new_entries)
    
    if not os.path.isfile(DB_FILE):
        df_new.to_csv(DB_FILE, index=False)
    else:
        df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 4. DATEN VERARBEITEN ---
aktuelle_werte = fetch_wartezeiten()
save_to_csv(aktuelle_werte)

# Historie laden
if os.path.isfile(DB_FILE):
    df_hist = pd.read_csv(DB_FILE)
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    # Nur die letzten 6 Stunden für das Diagramm
    six_hours_ago = datetime.now() - pd.Timedelta(hours=6)
    df_plot = df_hist[df_hist['Zeit'] > six_hours_ago]
else:
    df_plot = pd.DataFrame()

# --- 5. UI ANZEIGE ---
st.set_page_config(page_title="Autoverlad Live", page_icon="🚗")
st.title("🏔️ Autoverlad Monitor & Historie")

# Metriken
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# Diagramm
st.subheader("📈 Verlauf (letzte 6 Stunden)")
if not df_plot.empty:
    chart_data = df_plot.pivot_table(index='Zeit', columns='Ort', values='Wartezeit')
    st.line_chart(chart_data)
else:
    st.info("Noch keine historischen Daten vorhanden. Bitte kurz warten...")

st.caption(f"Letzter Check: {datetime.now().strftime('%H:%M:%S')}")
