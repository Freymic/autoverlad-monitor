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
    """Extrahiert Stunden und Minuten und addiert sie (z.B. 1 Std 30 Min = 90)."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. Sofort-Check für "Keine Wartezeit"
    if any(phrase in text for phrase in ["keine wartezeit", "0 min", "no waiting"]):
        return 0

    total_min = 0

    # 2. STUNDEN finden (sucht nach Zahlen vor 'stunde' oder 'std')
    hours = re.findall(r'(\d+)\s*(?:stunde|std)', text)
    if hours:
        # Wir addieren die erste gefundene Stundenzahl (mal 60)
        total_min += int(hours[0]) * 60

    # 3. MINUTEN finden (sucht nach Zahlen vor 'min')
    # Der Lookbehind (?<!:) ignoriert Uhrzeiten wie 16:35
    minutes = re.findall(r'(?<!:)(\b\d+)\s*min', text)
    if minutes:
        # Falls eine Stundenangabe da war, nehmen wir oft die Zahl danach.
        # Wir addieren einfach die erste gefundene Minutenzahl.
        total_min += int(minutes[0])

    return total_min

def fetch_all_data():
    """Holt Daten von Lötschberg (API) und Furka (RSS)."""
    results = {}
    
    # --- TEIL 1: LÖTSCHBERG (Kandersteg & Goppenstein) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        # Header hilft, Blockaden durch die API zu vermeiden
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "No waiting times")
                # Wir nutzen die neue parse-Funktion auch für BLS
                results[name] = {
                    "min": parse_time_to_minutes(msg), 
                    "raw": msg
                }
    except Exception as e:
        print(f"Fehler Lötschberg: {e}")

    # --- TEIL 2: FURKA (Oberwald & Realp) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # Filter gegen reine Fahrplan-Meldungen ("stündlich")
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]):
                continue
            
            # Nur verarbeiten, wenn es um Wartezeit geht
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                elif "Realp" in full_text:
                    results["Realp"] = {"min": val, "raw": full_text}
                    
        # Falls Furka-Daten fehlen, mit 0 initialisieren
        if "Oberwald" not in results: results["Oberwald"] = {"min": 0, "raw": "Keine aktuelle Meldung"}
        if "Realp" not in results: results["Realp"] = {"min": 0, "raw": "Keine aktuelle Meldung"}
        
    except Exception as e:
        print(f"Fehler Furka: {e}")
    
    return results

def save_to_db(data):
    """Speichert Daten exakt im 5-Minuten-Takt."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        now = datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        timestamp_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            # Dubletten-Check für das Zeitfenster
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (timestamp_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (timestamp_str, station, info.get('min', 0), info.get('raw', '')))
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
