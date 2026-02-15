import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Initialisiert SQLite und stellt Daten aus GSheets wieder her, falls DB leer ist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    
    # Check ob DB leer ist
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        restore_from_gsheets(conn)
    
    conn.close()

def restore_from_gsheets(sqlite_conn):
    """Lädt Daten aus dem Google Sheet zurück in die lokale SQLite."""
    try:
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        df = conn_gs.read()
        if not df.empty:
            # Nur die letzten 24h für die Performance laden
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.now() - timedelta(hours=24)
            df_recent = df[df['timestamp'] > cutoff]
            
            df_recent.to_sql('stats', sqlite_conn, if_exists='append', index=False)
            st.info("Daten aus Google Sheets wiederhergestellt.")
    except Exception as e:
        st.warning(f"Restore fehlgeschlagen: {e}")

def parse_time_to_minutes(time_str):
    if not time_str: return 0
    text = time_str.lower()
    mapping = {
        "4 stunden": 240, "3 stunden 30 minuten": 210, "3 stunden": 180,
        "2 stunden 30 minuten": 150, "2 stunden": 120, "1 stunde 30 minuten": 90,
        "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
        "keine wartezeit": 0, "no waiting": 0
    }
    for phrase, minutes in mapping.items():
        if phrase in text: return minutes
    
    # Fallback RegEx
    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match: total_min += int(hour_match.group(1)) * 60
    min_match = re.search(r'(?<!:)(\b\d+)\s*(?:min|minute)', text)
    if min_match: total_min += int(min_match.group(1))
    return total_min

def fetch_all_data():
    results = {}
    # Lötschberg
    try:
        l_res = requests.get("https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}", timeout=10).json()
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {"min": parse_time_to_minutes(msg), "raw": msg if msg else "Keine Wartezeit"}
    except: pass

    # Furka
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        root = ET.fromstring(f_resp.content)
        furka_found = {"Oberwald": False, "Realp": False}
        for item in root.findall('.//item'):
            full_text = f"{item.find('title').text} {item.find('description').text}"
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]): continue
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                for s in ["Oberwald", "Realp"]:
                    if s in full_text and not furka_found[s]:
                        results[s] = {"min": val, "raw": full_text}
                        furka_found[s] = True
        for s in ["Oberwald", "Realp"]:
            if not furka_found[s]: results[s] = {"min": 0, "raw": "Keine Meldung"}
    except: pass
    return results

def save_to_db(data):
    """Speichert lokal in SQLite."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now(CH_TZ)
        ts_str = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (ts_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO
