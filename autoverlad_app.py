import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
from streamlit_autorefresh import st_autorefresh

# --- 1. AUTOMATISCHER REFRESH (Alle 15 Minuten) ---
# Sorgt dafür, dass die Seite auch im Hintergrund aktuell bleibt
st_autorefresh(interval=900000, key="autoverlad_check")

# --- 2. KONFIGURATION & DATEI-SETUP ---
DB_FILE = "wartezeiten_historie.csv"
STATIONEN = {
    "Furka": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
    "Lötschberg": "https://www.bls.ch/de/fahren/autoverlad/fahrplan"
}

# --- 3. FUNKTIONEN ZUM DATENABRUF ---
def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # Furka (MGB) abfragen
        r_f = requests.get(STATIONEN["Furka"], timeout=10)
        soup_f = BeautifulSoup(r_f.content, 'html.parser').get_text()
        if "Realp" in soup_f:
            if "30 Minuten" in soup_f: daten["Realp"] = 30
            elif "60 Minuten" in soup_f: daten["Realp"] = 60
            elif "90 Minuten" in soup_f: daten["Realp"] = 90
        if "Oberwald" in soup_f and "30 Minuten" in soup_f:
            daten["Oberwald"] = 30
            
        # Lötschberg (BLS) abfragen
        r_l = requests.get(STATIONEN["Lötschberg"], timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text()
        if "Kandersteg" in soup_l and "30 Min" in soup_l: daten["Kandersteg"] = 30
        if "Goppenstein" in soup_l and "30 Min" in soup_l: daten["Goppenstein"] = 30
    except:
        pass
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
        # Nur anfügen, wenn die Datei bereits existiert
        df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 4. PROGRAMMLOGIK ---
aktuelle_werte = fetch_wartezeiten()
save_to_csv(aktuelle_werte)

# Historie für das Diagramm laden
if os.path.isfile(DB_FILE):
    df_hist = pd.read_csv(DB_FILE)
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    # Filter auf die letzten 6 Stunden
    six_hours_ago = datetime.now() - pd.Timedelta(hours=6)
    df_plot = df_hist[df_hist['Zeit'] > six_hours_ago]
else:
    df_plot = pd.DataFrame()

# --- 5. BENUTZEROBERFLÄCHE (UI) ---
st.set_page_config(page_title="Autoverlad Live", page_icon="🚗")
st.title("🏔️ Autoverlad Monitor")
st.write("Echtzeit-Abfrage der Wartezeiten und historischer Verlauf.")

# Aktuelle Werte als Kacheln
st.subheader("Aktuelle Wartezeiten")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# Verlaufschart
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")
if not df_plot.empty:
    # Daten für Diagramm aufbereiten (Zeit als Index, Orte als Spalten)
    chart_data = df_plot.pivot_table(index='Zeit', columns='Ort', values='Wartezeit')
    st.line_chart(chart_data)
else:
    st.info("Sammle erste Datenpunkte... Das Diagramm erscheint in Kürze.")

st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')} Uhr")
