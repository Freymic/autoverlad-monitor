import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import os
import altair as alt
from streamlit_autorefresh import st_autorefresh

# --- 1. REFRESH & SETUP ---
st_autorefresh(interval=900000, key="autoverlad_check")
DB_FILE = "wartezeiten_historie.csv"

# --- 2. DATENABRUF ---
def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # Furka (MGB)
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=10)
        soup_f = BeautifulSoup(r_f.content, 'html.parser').get_text()
        if "Realp" in soup_f:
            if "90 Minuten" in soup_f: daten["Realp"] = 90
            elif "60 Minuten" in soup_f: daten["Realp"] = 60
            elif "30 Minuten" in soup_f: daten["Realp"] = 30
        
        # Lötschberg (BLS)
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=10)
        soup_l = BeautifulSoup(r_l.content, 'html.parser').get_text()
        if "Kandersteg" in soup_l and "30 Min" in soup_l: daten["Kandersteg"] = 30
        if "Goppenstein" in soup_l and "30 Min" in soup_l: daten["Goppenstein"] = 30
    except: pass
    return daten

def save_to_csv(neue_daten):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_new = pd.DataFrame([{"Zeit": now, **neue_daten}])
    if not os.path.isfile(DB_FILE):
        df_new.to_csv(DB_FILE, index=False)
    else:
        df_new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. LOGIK ---
aktuelle_werte = fetch_wartezeiten()
save_to_csv(aktuelle_werte)

# --- 4. UI ---
st.set_page_config(page_title="Autoverlad Live", layout="wide")
st.title("🏔️ Autoverlad Monitor")

# Metriken oben
c1, c2, c3, c4 = st.columns(4)
c1.metric("Realp", f"{aktuelle_werte['Realp']} Min")
c2.metric("Oberwald", f"{aktuelle_werte['Oberwald']} Min")
c3.metric("Kandersteg", f"{aktuelle_werte['Kandersteg']} Min")
c4.metric("Goppenstein", f"{aktuelle_werte['Goppenstein']} Min")

# Verlauf
st.divider()
st.subheader("📈 Verlauf (letzte 6 Stunden)")

if os.path.isfile(DB_FILE):
    df_hist = pd.read_csv(DB_FILE)
    df_hist['Zeit'] = pd.to_datetime(df_hist['Zeit'])
    
    # Filter auf 6h
    cutoff = datetime.now() - pd.Timedelta(hours=6)
    df_plot = df_hist[df_hist['Zeit'] > cutoff]

    if not df_plot.empty:
        # Umwandlung für Altair (Long-Format)
        df_melted = df_plot.melt('Zeit', var_name='Ort', value_name='Wartezeit')
        
        # Altair Chart mit Halbstundenschritten
        chart = alt.Chart(df_melted).mark_line(interpolate='monotone', point=True).encode(
            x=alt.X('Zeit:T', 
                    title='Uhrzeit',
                    axis=alt.Axis(
                        format='%H:%M', 
                        tickCount={'interval': 'minute', 'step': 30}, # Fixe 30-Min-Schritte
                        labelAngle=0
                    )
            ),
            y=alt.Y('Wartezeit:Q', title='Minuten', scale=alt.Scale(domain=[0, 120])),
            color=alt.Color('Ort:N', title='Station'),
            tooltip=['Zeit:T', 'Ort:N', 'Wartezeit:Q']
        ).properties(height=400).interactive()
        
        st.altair_chart(chart, use_container_width=True)
else:
    st.info("Sammle Daten...")

st.caption(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")
