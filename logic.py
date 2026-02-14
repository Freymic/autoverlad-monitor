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
    if not time_str:
        return 0
    # Erkennt "Keine", "No waiting", etc. als 0
    if any(word in time_str.lower() for word in ["keine", "no", "none"]):
        return 0
    # Extrahiert alle Ziffern (z.B. "15 Min" -> 15)
    digits = ''.join(filter(str.isdigit, time_str))
    return int(digits) if digits else 0

def save_to_db(data):
    """Speichert Daten exakt im 5-Minuten-Takt (xx:00, xx:05, xx:10...)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Aktuelle Zeit in CH-Zeit holen
        now = datetime.now(CH_TZ)
        
        # --- QUANTISIERUNG ---
        # Berechnet die abgerundete 5-Minuten-Marke
        minute_quantized = (now.minute // 5) * 5
        # Ersetzt Minute durch quantisierten Wert und setzt Sekunden/Mikrosekunden auf 0
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        timestamp_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            # Prüfen, ob für dieses 5-Minuten-Fenster und diese Station schon ein Wert existiert
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (timestamp_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (timestamp_str, station, info.get('min', 0), info.get('raw', '')))
                print(f"Gespeichert: {station} für {timestamp_str}") # Kontroll-Ausgabe
            else:
                # Falls schon ein Eintrag existiert (z.B. durch Refresh), wird nichts getan
                pass
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_all_data():
    """Holt Daten von Furka und Lötschberg mit Profi-Headern."""
    results = {}
    
    # Die neuen Header, damit die BLS-API uns als Browser erkennt
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    # --- 1. FURKA (RSS) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, headers=headers, timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit."}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full = f"{title} {desc}"
            val = parse_time_to_minutes(full)
            
            if "Oberwald" in full: 
                results["Oberwald"] = {"min": val, "raw": desc}
            if "Realp" in full: 
                results["Realp"] = {"min": val, "raw": desc}
    except Exception as e:
        print(f"Furka Fehler: {e}")

    # --- 2. LÖTSCHBERG (JSON API) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        response = requests.get(l_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            l_data = response.json()
            # Wir navigieren direkt in die "Stations" Liste deiner Beispiel-Antwort
            for entry in l_data.get("Stations", []):
                name = entry.get("Station")
                msg = entry.get("DelayMessage")
                
                if name in ["Kandersteg", "Goppenstein"]:
                    results[name] = {
                        "min": parse_time_to_minutes(msg),
                        "raw": json.dumps(entry, ensure_ascii=False)
                    }
        else:
            print(f"Lötschberg API Status Fehler: {response.status_code}")
    except Exception as e:
        print(f"Lötschberg API Verbindungsfehler: {e}")

    # Sicherheitshalber Keys auffüllen
    for s in ["Kandersteg", "Goppenstein", "Oberwald", "Realp"]:
        if s not in results:
            results[s] = {"min": 0, "raw": "Keine Daten verfügbar"}

    return results

# Wichtig für den Import in autoverlad_app.py
get_quantized_data = fetch_all_data
