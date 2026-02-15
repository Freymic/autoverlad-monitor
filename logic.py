import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
import pandas as pd
import datetime
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Initialisiert die Datenbank-Tabelle und stellt Daten aus GSheets wieder her, falls DB leer."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    
    # Check ob DB leer ist (z.B. nach Reboot auf Streamlit Cloud)
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        restore_from_gsheets(conn)
        
    conn.close()

def restore_from_gsheets(sqlite_conn):
    """Lädt die letzten 24h aus Google Sheets zurück in die lokale SQLite."""
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Sheet1")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        df = conn_gs.read(worksheet=sheet_name)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
            df_recent = df[df['timestamp'] > cutoff]
            
            if not df_recent.empty:
                df_recent.to_sql('stats', sqlite_conn, if_exists='append', index=False)
                st.info(f"🔄 Daten aus Cloud-Tab '{sheet_name}' wiederhergestellt.")
    except Exception as e:
        st.warning(f"Cloud-Restore übersprungen: {e}")

def parse_time_to_minutes(time_str):
    """Lückenloses Mapping von Text-Phrasen zu Minutenwerten bis 4h."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. ERWEITERTES MAPPING
    mapping = {
        "4 stunden": 240,
        "3 stunden 30 minuten": 210,
        "3 stunden": 180,
        "2 stunden 30 minuten": 150,
        "2 stunden": 120,
        "1 stunde 30 minuten": 90,
        "1 stunde": 60,
        "45 minuten": 45,
        "30 minuten": 30,
        "15 minuten": 15,
        "keine wartezeit": 0,
        "no waiting": 0
    }
    
    for phrase, minutes in mapping.items():
        if phrase in text:
            return minutes

    # 2. DYNAMISCHER RECHNER (Fallback)
    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match:
        total_min += int(hour_match.group(1)) * 60
    
    min_match = re.search(r'(?<!:)(\b\d+)\s*(?:min|minute)', text)
    if min_match:
        total_min += int(min_match.group(1))
        
    return total_min

def fetch_all_data():
    """Holt Daten von Lötschberg (API) und Furka (RSS)."""
    results = {}
    
    # --- TEIL 1: LÖTSCHBERG (Kandersteg & Goppenstein) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {
                    "min": parse_time_to_minutes(msg), 
                    "raw": msg if msg else "Keine Wartezeit"
                }
    except Exception as e:
        print(f"Fehler Lötschberg: {e}")

    # --- TEIL 2: FURKA (Oberwald & Realp) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        furka_found = {"Oberwald": False, "Realp": False}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]):
                continue
            
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text and not furka_found["Oberwald"]:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                    furka_found["Oberwald"] = True
                elif "Realp" in full_text and not furka_found["Realp"]:
                    results["Realp"] = {"min": val, "raw": full_text}
                    furka_found["Realp"] = True
        
        if not furka_found["Oberwald"]: results["Oberwald"] = {"min": 0, "raw": "Keine Meldung"}
        if not furka_found["Realp"]: results["Realp"] = {"min": 0, "raw": "Keine Meldung"}
            
    except Exception as e:
        print(f"Fehler Furka: {e}")
    
    return results

def save_to_db(data):
    """Speichert Daten exakt im 5-Minuten-Takt in die SQLite DB."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        now = datetime.datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        timestamp_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (timestamp_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (timestamp_str, station, info.get('min', 0), info.get('raw', '')))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def save_to_google_sheets(data):
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Development")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        
        # 1. Zeitstempel vorbereiten
        now = datetime.datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        ts_str = now.replace(minute=minute_quantized, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        # 2. Neue Daten in DataFrame umwandeln
        new_entries = []
        for station, info in data.items():
            new_entries.append({
                "timestamp": ts_str,
                "station": station,
                "minutes": info.get('min', 0),
                "raw_text": info.get('raw', '')
            })
        df_new = pd.DataFrame(new_entries)
        
        # 3. Bestehende Daten laden (Cache umgehen mit ttl=0)
        try:
            # ttl=0 stellt sicher, dass wir wirklich den aktuellen Stand vom Server holen
            df_existing = conn_gs.read(worksheet=sheet_name, ttl=0)
        except Exception:
            df_existing = pd.DataFrame(columns=["timestamp", "station", "minutes", "raw_text"])
        
        # 4. Anhängen und Index zurücksetzen
        # ignore_index=True ist extrem wichtig, damit Google nicht denkt, es sei die gleiche Zeile
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
        
        # 5. Duplikate entfernen (Zeitpunkt + Station)
        df_final = df_final.drop_duplicates(subset=['timestamp', 'station'], keep='last')
        
        # 6. Das komplette Sheet aktualisieren
        conn_gs.update(worksheet=sheet_name, data=df_final)
        
        # Kleiner Debug-Hinweis für dich (kannst du später löschen)
        # st.toast(f"Cloud-Sync: {len(df_final)} Zeilen gesamt")
        
        return True
        
    except Exception as e:
        st.error(f"GSheets Sync Fehler: {e}")
        return False

def get_latest_wait_times(station):
    # Holt den aktuellsten Wert für eine Station aus der SQLite DB
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(
            "SELECT minutes FROM stats WHERE station = ? ORDER BY timestamp DESC LIMIT 1", 
            conn, params=(station,)
        )
    return int(df['minutes'].iloc[0]) if not df.empty else 0

def get_google_maps_duration(origin, destination):
    """Holt die echte Fahrzeit inkl. Verkehr von Google Maps."""
    api_key = st.secrets["G_MAPS_API_KEY"]
    
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "mode": "driving",
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] == "OK":
            # Zeit in Sekunden umrechnen in Minuten
            seconds = data["rows"][0]["elements"][0]["duration_in_traffic"]["value"]
            return seconds // 60
        else:
            st.error(f"Google Maps Fehler: {data['status']}")
            return 60 # Fallback
    except Exception as e:
        st.error(f"Verbindung zu Google fehlgeschlagen: {e}")
        return 60 # Fallback

def get_furka_departure(arrival_time):
    """Berechnet die nächste Abfahrt ab Realp basierend auf dem PDF-Fahrplan."""
    weekday = arrival_time.weekday()  # 0=Mo, 1=Di... 4=Fr, 5=Sa, 6=So
    hour = arrival_time.hour
    minute = arrival_time.minute
    
    # Wir brauchen einen Puffer von mind. 10 Min für Verlad/Kasse
    earliest_possible = arrival_time + datetime.timedelta(minutes=10)
    check_min = earliest_possible.minute
    check_hour = earliest_possible.hour

    # Aktueller Zeitraum: 14.12.2025 - 14.06.2026
    # Freitag - Sonntag: alle 30 Min (.05 & .35) bis 22:05
    if weekday >= 4: # Fr, Sa, So
        if check_min <= 5: departure_min = 5
        elif check_min <= 35: departure_min = 35
        else:
            departure_min = 5
            check_hour += 1
        last_train = 22
    
    # Montag: alle 30 Min (.05 & .35) bis 21:05
    elif weekday == 0:
        if check_min <= 5: departure_min = 5
        elif check_min <= 35: departure_min = 35
        else:
            departure_min = 5
            check_hour += 1
        last_train = 21

    # Dienstag - Donnerstag: alle 60 Min (.05) bis 21:05
    else:
        departure_min = 5
        if check_min > 5:
            check_hour += 1
        last_train = 21

    # Prüfung auf Betriebsschluss
    if check_hour > last_train or (check_hour == last_train and departure_min > 5):
        return None # Kein Zug mehr heute!
        
    return earliest_possible.replace(hour=check_hour, minute=departure_min, second=0)
