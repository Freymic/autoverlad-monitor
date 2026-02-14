import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
from datetime import datetime
import pytz

# Konstanten für die App (Wichtig für image_8d7123.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats', die pandas sucht (image_8d6600.jpg)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Zahlen aus Texten wie '30 Min' oder 'Keine Wartezeit'."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die Ergebnisse in der Tabelle 'stats'."""
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
        
        # Standardwerte setzen
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit Oberwald."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit Realp."}
        
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            full = f"{title} {desc}"
            
            m = re.search(r'(\d+)\s*Minute', full)
            h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            
            if "Oberwald" in full:
                results["Oberwald"] = {"min": val, "raw": desc if desc else "Wartezeit Oberwald"}
            if "Realp" in full:
                results["Realp"] = {"min": val, "raw": desc if desc else "Wartezeit Realp"}
    except:
        pass

    # --- 2. LÖTSCHBERG LOGIK (Deine neue API-Quelle) ---
    try:
        # Die korrigierte URL mit avwV2
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10).json()
        
        for item in l_res:
            name = item.get('stName') # z.B. "Kandersteg"
            info = item.get('stInfo') # z.B. "Keine Wartezeiten"
            
            if name and info:
                results[name] = {
                    "min": parse_time_to_minutes(info),
                    "raw": info
                }
    except:
        # Fallback falls die API doch mal klemmt
        if "Kandersteg" not in results:
            results["Kandersteg"] = {"min": 0, "raw": "Keine Info"}
            results["Goppenstein"] = {"min": 0, "raw": "Keine Info"}

    save_to_db(results)
    return results

# Alias für die App-Importe (image_8d7123.png)
get_quantized_data = fetch_all_data
