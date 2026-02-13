import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import altair as alt
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. REFRESH & SETUP ---
# Aktualisiert die App alle 15 Minuten automatisch
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

# --- 2. ROBUSTE SCRAPING LOGIK ---
def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=10)
        soup_f = BeautifulSoup(r_f.content, 'html.parser').get_text()
        
        for station in ["Realp", "Oberwald"]:
            pos = soup_f.find(station)
            if pos != -1:
                # Wir schauen uns die nächsten 150 Zeichen nach dem Stationsnamen an
                kontext = soup_f[pos:pos+150]
                # Sucht flexibel nach Zahlen vor "Min", "min" oder "Minuten"
                zahlen = re.findall(r'(\d+)\s*(?:Min|min|Minuten)', kontext)
                if zahlen:
                    daten[station] = int(zahlen[0])
        
        # --- LÖTSCHBERG (BLS) ---
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text()
        
        for station in ["Kandersteg", "Goppenstein"]:
            pos = soup_l.find(station)
            if pos != -1:
                kontext = soup_l[pos:pos+200]
                # BLS nutzt oft das Format "30 Min"
                zahlen = re.findall(r'(\d+)\s*(?:Min|min)', kontext)
                if zahlen:
                    daten[station] = int(zahlen[0])
                    
    except Exception as e:
        st.sidebar.error(f"Fehler beim Abruf: {e}")
        
    return daten

def save_to_csv(neue_daten):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_new = pd.DataFrame([{"Zeit": now, **neue_daten}])
    if not os.path.isfile(DB_FILE):
        df_new.to_csv(DB_FILE, index=False)
    else:
        df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. UI SETUP ---
st.set_page_config(page_title="Autoverlad Live-Monitor", layout="wide", page_icon="🚗")
st.title("🏔️ Autoverlad Monitor")

# Sidebar für Admin-Funktionen
st.sidebar.header("🛠️ Admin Tools")

if st.sidebar.button("🧪 Testdaten generieren"):
    test_entries = []
    for i in range(12): # Erzeugt Daten für die letzten 3 Stunden
        test_time = (datetime.now() - timedelta(minutes=15*i)).strftime("%Y-%m-%d %H:%M:%S")
        test_entries.append({
            "Zeit": test_time,
            "Realp": random.choice([0, 30, 60]),
            "Oberwald": random.choice([0, 30]),
            "Kandersteg": random.choice([0, 30, 60, 90]),
            "Goppenstein": random.choice([0, 30])
        })
    df_test = pd.DataFrame(test_entries)
    if not os.path.isfile(DB_FILE):
        df_test.to_csv(DB_FILE, index=False)
    else:
        df_test.to_csv(DB_FILE, mode='a', header=False, index=False)
    st.sidebar.success("Testdaten generiert!")
    st.rerun()

if st.sidebar.button("🗑️ Historie löschen"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        st.sidebar.warning("Historie gelöscht.")
        st.rerun()

# --- 4. AKTUELLE DATEN ---
# Button für manuellen Refresh
if st.button("🔄 Jetzt Live-Daten abrufen"):
    aktuelle_werte = fetch_wartezeiten()
    save_to_csv(aktuelle_werte)
    st.success("Daten wurden frisch vom Server geladen!")
else:
    aktuelle_werte = fetch_wartezeiten()
    # Wir speichern bei jedem Seitenaufruf/Refresh den aktuellen Stand
    save_to_csv(aktuelle_werte)

# Metriken anzeigen
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp (Furka)", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald (Furka)", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg (Lötschberg)", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein (Lötschberg)", f"{aktuelle_werte['Goppenstein']} Min")

# --- 5. VERLAUFS-DIAGRAMM ---
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    df_hist = pd.read_csv(DB_FILE)
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    
    # Aufräumen: Sortieren und Duplikate entfernen
    df_hist = df_hist.sort_values('Zeit').drop_duplicates()
    
    # Filter auf die letzten 6 Stunden
    cutoff = datetime.now() - timedelta(hours=6)
    df_plot = df_hist[df_hist['Zeit'] > cutoff]

    if not df_plot.empty and len(df_plot) > 1:
        # Daten für Altair ins Long-Format umwandeln
        df_melted = df_plot.melt('Zeit', var_name='Station', value_name='Wartezeit')
        
        # Das interaktive Diagramm
        chart = alt.Chart(df_melted).mark_line(point=True, interpolate='monotone').encode(
            x=alt.X('Zeit:T', 
                    title='Uhrzeit', 
                    axis=alt.Axis(format='%H:%M', tickCount={'interval': 'minute', 'step': 30}, labelAngle=0)),
            y=alt.Y('Wartezeit:Q', title='Minuten Wartezeit', scale=alt.Scale(domain=[0, 120])),
            color=alt.Color('Station:N', title='Verladestation'),
            tooltip=['Zeit:T', 'Station:N', 'Wartezeit:Q']
        ).properties(height=450).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Sammle Daten... Das Diagramm erscheint, sobald zwei Messpunkte vorliegen.")
else:
    st.info("Noch keine Historie vorhanden. Nutze die Testdaten-Funktion links zum Ausprobieren.")

st.caption(f"Letzter Abruf: {datetime.now().strftime('%H:%M:%S')} Uhr")
