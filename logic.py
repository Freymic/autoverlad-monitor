import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
from datetime import datetime, timedelta
import pytz

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Initialisiert die Datenbank-Tabelle."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Minuten aus den API-Texten."""
    if not time_str or any(word in time_str.lower() for word in ["keine", "no", "none"]):
        return 0
    # Sucht nach Zahlen im Text (z.B. '15' aus '15 Min')
    digits = ''.join(filter(str.isdigit, time_str))
    return int(digits) if digits else 0

def save_to_db(data):
    """Speichert Daten im 5-Minuten-Raster und löscht alte Einträge."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Zeit auf 5 Minuten abrunden (xx:00, xx:05, xx:10...)
        now = datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        timestamp_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            # Dubletten-Check für dieses Zeitfenster
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (timestamp_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (timestamp_str, station, info.get('min', 0), info.get('raw', '')))
        
        # Automatische Reinigung: Alles älter als 14 Tage löschen
        cutoff = (now - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("DELETE FROM stats WHERE timestamp < ?", (cutoff,))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_all_data():
    """Holt Wartezeiten von Furka und Lötschberg."""
    results = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    # --- FURKA (RSS) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit."}
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            val = parse_time_to_minutes(full)
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": full}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": full}
    except: pass

    # --- LÖTSCHBERG (JSON) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, headers=headers, timeout=10).json()
        for entry in l_res.get("Stations", []):
            name = entry.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = entry.get("DelayMessage")
                results[name] = {"min": parse_time_to_minutes(msg), "raw": json.dumps(entry)}
    except: pass

    return results

def fetch_timetable(station_id):
    """Holt die nächsten 3 Abfahrten für Autozüge."""
    try:
        url = f"https://transport.opendata.ch/v1/stationboard?id={station_id}&limit=15"
        response = requests.get(url, timeout=5).json()
        departures = []
        for journey in response.get('stationboard', []):
            cat = journey.get('category')
            # Filter für Autozüge und Regionalzüge
            if cat in ['AT', 'BAT', 'EXT', 'R']:
                time_dt = datetime.fromisoformat(journey['stop']['departure'].replace('Z', '+00:00'))
                time_str = time_dt.astimezone(CH_TZ).strftime('%H:%M')
                dest = journey.get('to')
                departures.append(f"{time_str} -> {dest}")
            if len(departures) >= 3: break
        return departures if departures else ["Keine Abfahrten"]
    except:
        return ["API Fehler"]

def get_all_timetables():
    """Mapping der Bahnhof-IDs."""
    ids = {"Kandersteg": "8501140", "Goppenstein": "8501142", "Oberwald": "8505169", "Realp": "8505165"}
    return {name: fetch_timetable(sid) for name, sid in ids.items()}
