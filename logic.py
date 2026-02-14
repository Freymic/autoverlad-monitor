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
    """Erstellt die Tabelle 'stats', die pandas sucht (image_8d6600.jpg)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Zahlen aus Texten (z.B. '30 Min' -> 30)."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert Ergebnisse in der Tabelle 'stats'."""
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
    
    # --- 1. FURKA LOGIK (Deine bewährte RSS-Version) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        
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
                results["Oberwald"] = {"min": val, "raw": desc}
            if "Realp" in full:
                results["Realp"] = {"min": val, "raw": desc}
    except:
        pass

    # --- 2. LÖTSCHBERG LOGIK (Angepasst an deine API-Antwort) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10).json()
        
        # Zugriff auf die Liste unter dem Key 'Stations'
        for entry in l_res.get("Stations", []):
            name = entry.get("Station")
            msg = entry.get("DelayMessage")
            
            if name:
                # Wir speichern das komplette Station-Objekt als raw-Text
                results[name] = {
                    "min": parse_time_to_minutes(msg),
                    "raw": json.dumps(entry, ensure_ascii=False)
                }
    except Exception as e:
        print(f"Lötschberg API Fehler: {e}")

    # Sicherstellen, dass Kandersteg/Goppenstein Keys existieren
    for s in ["Kandersteg", "Goppenstein"]:
        if s not in results:
            results[s] = {"min": 0, "raw": "Keine Info"}

    save_to_db(results)
    return results

# Import für Streamlit
get_quantized_data = fetch_all_data
