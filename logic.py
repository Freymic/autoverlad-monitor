import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
from datetime import datetime
import pytz

# Konstanten für die App (Behebt ImportError aus image_8d62e0.png und image_8d7123.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Wir nennen die Spalte 'wait_time', um Verwechslungen mit dem Wort 'minutes' zu vermeiden
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, wait_time INTEGER, raw_text TEXT)''')
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
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            # Wir speichern den Wert explizit in 'wait_time'
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                      (timestamp, station, int(info.get('min', 0)), info.get('raw', '')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_all_data():
    results = {}
    
    # --- 1. FURKA LOGIK (RSS-Version) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        
        # Standardwerte (image_8dd31a.png)
        results["Oberwald"] = {"min": 0, "raw": "Aktuell besteht an der Verladestation Oberwald (VS) des Autoverlads Furka keine Wartezeit."}
        results["Realp"] = {"min": 0, "raw": "Aktuell besteht an der Verladestation Realp (UR) des Autoverlads Furka keine Wartezeit."}
        
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            full = f"{title} {desc}"
            m = re.search(r'(\d+)\s*Minute', full); h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": desc}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": desc}
    except:
        pass

    # --- 2. LÖTSCHBERG LOGIK (Angepasst an API-Struktur aus image_8de924.png) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        response = requests.get(l_url, timeout=10)
        l_data = response.json() # Das ist das gesamte Objekt (image_8de924.png)
        
        # Wir greifen auf die Liste unter dem Schlüssel 'Stations' zu
        stations_list = l_data.get("Stations", [])
        
        for entry in stations_list:
            name = entry.get("Station") # "Kandersteg" oder "Goppenstein"
            msg = entry.get("DelayMessage") # "Keine Wartezeiten"
            
            if name in ["Kandersteg", "Goppenstein"]:
                results[name] = {
                    "min": parse_time_to_minutes(msg),
                    # Wir speichern das Element exakt so, wie es in der API-Antwort steht
                    "raw": json.dumps(entry, ensure_ascii=False)
                }
    except Exception as e:
        print(f"Lötschberg API Error: {e}")

    # Fallback, falls die API-Abfrage für Lötschberg komplett scheitert
    for s in ["Kandersteg", "Goppenstein"]:
        if s not in results:
            results[s] = {"min": 0, "raw": "Keine Info"}

    save_to_db(results)
    return results

# Alias für die App-Importe (image_8d62e0.png)
get_quantized_data = fetch_all_data
