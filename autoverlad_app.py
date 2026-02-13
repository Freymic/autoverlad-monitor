import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from streamlit_autorefresh import st_autorefresh

# --- 1. AUTOMATISCHER REFRESH (Alle 15 Minuten) ---
# Das sorgt dafür, dass die App auch ohne manuelles Klicken aktualisiert
st_autorefresh(interval=900000, key="autoverlad_check")

# --- 2. KONFIGURATION ---
STATIONEN = {
    "Furka": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
    "Lötschberg": "https://www.bls.ch/de/fahren/autoverlad/fahrplan"
}

# --- 3. SCRAPING LOGIK ---
def fetch_wartezeiten():
    daten = {
        "Realp": "0 Min", "Oberwald": "0 Min",
        "Kandersteg": "0 Min", "Goppenstein": "0 Min"
    }
    
    # Furka abfragen
    try:
        r_furka = requests.get(STATIONEN["Furka"], timeout=10)
        soup_f = BeautifulSoup(r_furka.content, 'html.parser')
        text_f = soup_f.get_text()
        if "Realp" in text_f and "30 Minuten" in text_f: daten["Realp"] = "30 Min"
        if "Realp" in text_f and "60 Minuten" in text_f: daten["Realp"] = "60 Min"
        if "Oberwald" in text_f and "30 Minuten" in text_f: daten["Oberwald"] = "30 Min"
    except: pass

    # Lötschberg abfragen
    try:
        r_bls = requests.get(STATIONEN["Lötschberg"], timeout=10)
        soup_b = BeautifulSoup(r_bls.content, 'html.parser')
        text_b = soup_b.get_text()
        # BLS spezifische Suche
        if "Kandersteg" in text_b and "30 Min" in text_b: daten["Kandersteg"] = "30 Min"
        if "Goppenstein" in text_b and "30 Min" in text_b: daten["Goppenstein"] = "30 Min"
    except: pass

    return daten

def send_alert(email, station, dauer):
    # Platzhalter für SMTP-Logik (Gmail/Outlook)
    # st.warning(f"ALERT: {station} hat jetzt {dauer} Wartezeit!")
    pass

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="Autoverlad Live-Monitor", page_icon="🚗")

st.title("🏔️ Schweizer Autoverlad Monitor")
st.write("Aktualisiert sich alle 15 Minuten automatisch.")

# Sidebar für Alerts
st.sidebar.header("📧 Benachrichtigungen")
target_email = st.sidebar.text_input("Deine E-Mail")
alert_on = st.sidebar.checkbox("E-Mail Alerts aktivieren")
threshold = st.sidebar.selectbox("Benachrichtigen ab (Min):", [30, 60, 90])

# Daten abrufen
aktuelle_daten = fetch_wartezeiten()

# Anzeige Furka
st.subheader("🚠 Autoverlad Furka (MGB)")
c1, c2 = st.columns(2)
c1.metric("Realp → Oberwald", aktuelle_daten["Realp"])
c2.metric("Oberwald → Realp", aktuelle_daten["Oberwald"])

# Anzeige Lötschberg
st.divider()
st.subheader("🚆 Autoverlad Lötschberg (BLS)")
c3, c4 = st.columns(2)
c3.metric("Kandersteg → Goppenstein", aktuelle_daten["Kandersteg"])
c4.metric("Goppenstein → Kandersteg", aktuelle_daten["Goppenstein"])

st.caption(f"Letzter Check: {datetime.now().strftime('%H:%M:%S')} Uhr")

# Alert Logik (Beispiel Realp)
if alert_on and target_email:
    val = int(aktuelle_daten["Realp"].split()[0]) if "Min" in aktuelle_daten["Realp"] else 0
    if val >= threshold:
        send_alert(target_email, "Realp", aktuelle_daten["Realp"])
