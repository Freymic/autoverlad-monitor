import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
from datetime import datetime
import pytz

# Konstanten für die App (Behebt ImportError aus image_8d7123.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats', die pandas für das Diagramm benötigt."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Konvertiert Texte wie '30 Min' in Zahlen."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die kombinierten Daten in der Datenbank (image_8d6600.jpg)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                      (timestamp, station, info.get('min', 0), info.get('raw', '')))
        conn.commit()
        conn.close()
    except:
        pass

def fetch_all_data():
    results = {}
    
    # --- 1. FURKA LOGIK (Bewährte RSS-Version) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        
        # Standardwerte
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit Oberwald."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit Realp."}
        
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            full = f"{title} {desc}"
            
            # Zeit-Extraktion (Minuten/Stunden)
            m = re.search(r'(\d+)\s*Minute', full)
            h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            
            if "Oberwald" in full:
                results["Oberwald"] = {"min": val, "raw": desc if desc else "Wartezeit Oberwald"}
            if "Realp" in full:
                results["Realp"] = {"min": val, "raw": desc if desc else "Wartezeit Realp"}
    except:
        pass

    # --- 2. LÖTSCHBERG LOGIK (API-Version mit JSON-Formatierung) ---
    try:
        # Nutzung der korrekten avwV2 URL
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10).json()
        
        for item in l_res:
            name = item.get('stName')
            info = item.get('stInfo')
            
            if name and info:
                # Erstellt das gewünschte JSON-Format für die Raw Message
                raw_json = json.dumps({"Station": name, "DelayMessage": info}, ensure_ascii=False)
                
                results[name] = {
                    "min": parse_time_to_minutes(info),
                    "raw": raw_json
                }
    except:
        if "Kandersteg" not in results:
            results["Kandersteg"] = {"min": 0, "raw": "Keine Info"}
            results["Goppenstein"] = {"min": 0, "raw": "Keine Info"}

    save_to_db(results)
    return results

# Alias für die App-Importe
get_quantized_data = fetch_all_data
