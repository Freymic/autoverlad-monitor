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
    """Extrahiert Stunden und Minuten präzise aus komplexen/doppelten Texten."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. Sofort-Check für "Keine Wartezeit"
    if any(phrase in text for phrase in ["keine wartezeit", "0 min", "no waiting"]):
        return 0

    # 2. Falls der Text doppelt ist (wie bei Oberwald), nehmen wir nur den ersten Satz
    # Wir trennen am Punkt, um Doppel-Additionen zu vermeiden
    first_sentence = text.split('.')[0]

    total_min = 0

    # 3. STUNDEN extrahieren (sucht nach Zahlen vor 'stunde' oder 'std')
    # Wir suchen im ersten Satz nach der Stundenanzahl
    hour_match = re.search(r'(\d+)\s*(?:stunde|std)', first_sentence)
    if hour_match:
        total_min += int(hour_match.group(1)) * 60

    # 4. MINUTEN extrahieren (sucht nach Zahlen vor 'min')
    # (?<!:) verhindert, dass Uhrzeiten wie 16:35 als Minuten gezählt werden
    minute_match = re.search(r'(?<!:)(\b\d+)\s*(?:min|minute)', first_sentence)
    if minute_match:
        total_min += int(minute_match.group(1))

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
                    "min": parse_time_to_minutes(msg) if msg else 0, 
                    "raw": msg if msg else "No waiting times"
                }
    except Exception as e:
        print(f"Fehler Lötschberg: {e}")

    # --- TEIL 2: FURKA (Oberwald & Realp) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        # Furka-Standardwerte
        furka_stations = {"Oberwald": None, "Realp": None}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # WICHTIG: Überspringe reine Fahrplan-Hinweise
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]):
                continue
            
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text and furka_stations["Oberwald"] is None:
                    furka_stations["Oberwald"] = {"min": val, "raw": full_text}
                elif "Realp" in full_text and furka_stations["Realp"] is None:
                    furka_stations["Realp"] = {"min": val, "raw": full_text}
        
        # Ergebnisse in das Haupt-Dictionary übernehmen
        for st, data in furka_stations.items():
            results[st] = data if data else {"min": 0, "raw": "Keine aktuelle Meldung"}
            
    except Exception as e:
        print(f"Fehler Furka: {e}")
    
    return results

def save_to_db(data):
    """Speichert Daten im 5-Minuten-Takt."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        ts_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (ts_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (ts_str, station, info.get('min', 0), info.get('raw', '')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
