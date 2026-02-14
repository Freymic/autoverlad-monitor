import streamlit as st
import requests
import xml.etree.ElementTree as ET
import re
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# --- Datenbank Setup ---
def init_db():
    conn = sqlite3.connect('furka_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (timestamp DATETIME, oberwald INTEGER, realp INTEGER)''')
    conn.commit()
    return conn

def save_to_db(ow, re_val):
    conn = sqlite3.connect('furka_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?)", (datetime.now(), ow, re_val))
    # Alte Daten löschen, die älter als 24h sind, um die DB sauber zu halten
    c.execute("DELETE FROM history WHERE timestamp < ?", (datetime.now() - timedelta(hours=24),))
    conn.commit()
    conn.close()

def load_history(hours=6):
    conn = sqlite3.connect('furka_history.db')
    cutoff = datetime.now() - timedelta(hours=hours)
    df = pd.read_sql_query("SELECT * FROM history WHERE timestamp > ?", conn, params=(cutoff,))
    conn.close()
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# --- Datenabfrage (RSS) ---
def get_furka_data():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    try:
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            results = {"Oberwald": 0, "Realp": 0}
            for item in root.findall('.//item'):
                text = f"{item.find('title').text} {item.find('description').text}"
                direction = "Oberwald" if "Oberwald" in text else "Realp" if "Realp" in text else None
                if direction:
                    std = re.search(r'(\d+)\s*Stunde', text)
                    mn  = re.search(r'(\d+)\s*Minute', text)
                    results[direction] = int(std.group(1)) * 60 if std else int(mn.group(1)) if mn else 0
            return results, response.text
    except Exception as e:
        st.error(f"Fehler: {e}")
    return None, ""

# --- UI ---
st.title("🏔️ Furka Trend-Monitor (6h History)")
init_db()

if st.button("🔄 Jetzt prüfen & speichern"):
    daten, raw_xml = get_furka_data()
    if daten:
        save_to_db(daten["Oberwald"], daten["Realp"])
        st.success(f"Daten gespeichert: Oberwald {daten['Oberwald']}min, Realp {daten['Realp']}min")
    
    # Debug Info innerhalb des Buttons für direkten Zugriff
    with st.expander("Raw XML Debug"):
        st.code(raw_xml, language="xml")

# --- Trend Anzeige ---
df_hist = load_history(hours=6)

if not df_hist.empty:
    st.subheader("📈 Wartezeit-Trend (letzte 6 Stunden)")
    
    # Chart vorbereiten
    chart_data = df_hist.rename(columns={"timestamp": "Zeit", "oberwald": "Oberwald (min)", "realp": "Realp (min)"})
    st.line_chart(chart_data.set_index("Zeit"))
    
    # Metriken für den aktuellen Stand (letzter Eintrag)
    last_entry = df_hist.iloc[-1]
    c1, c2 = st.columns(2)
    c1.metric("Oberwald aktuell", f"{int(last_entry['oberwald'])} min")
    c2.metric("Realp aktuell", f"{int(last_entry['realp'])} min")
else:
    st.info("Noch keine Trend-Daten vorhanden. Bitte klicke auf 'Daten prüfen'.")
