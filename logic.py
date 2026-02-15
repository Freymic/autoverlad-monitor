import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
from datetime import datetime
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
    """Lückenloses Mapping von Text-Phrasen zu Minutenwerten bis 4h."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. ERWEITERTES MAPPING (Priorität 1)
    # Sortierung von lang nach kurz, um Teil-Matches zu verhindern.
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

    # 2. DYNAMISCHER RECHNER (Priorität 2 - Fallback)
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
        
        # Furka-Standardwerte initialisieren
        furka_found = {"Oberwald": False, "Realp": False}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # Filter gegen reine Fahrplan-Hinweise ("stündlich")
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
        
        # Fallback falls keine Meldung im Feed war
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
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
