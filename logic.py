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
    """Extrahiert alle Stunden und Minuten aus einem Text und addiert sie."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. Sofortiger Ausschluss bei "Keine Wartezeit"
    if "keine wartezeit" in text or "0 min" in text or "no waiting" in text:
        return 0

    total_minutes = 0

    # 2. Stunden finden (z.B. "1 Stunde") und in Minuten umrechnen
    hour_matches = re.findall(r'(\d+)\s*(?:std|stunde)', text)
    for h in hour_matches:
        total_minutes += int(h) * 60

    # 3. Minuten finden (z.B. "30 Minuten")
    # Der Lookbehind (?<!:) ignoriert Zahlen, die Teil einer Uhrzeit (16:35) sind
    min_matches = re.findall(r'(?<!:)(\b\d+)\s*(?:min|minute)', text)
    for m in min_matches:
        total_minutes += int(m)

    return total_minutes

def fetch_all_data():
    """Holt Wartezeiten von Furka (RSS) und Lötschberg (API)."""
    results = {}
    
    # --- 1. LÖTSCHBERG (JSON API) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        l_res = requests.get(l_url, headers=headers, timeout=10).json()
        
        for entry in l_res.get("Stations", []):
            name = entry.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = entry.get("DelayMessage", "")
                results[name] = {
                    "min": parse_time_to_minutes(msg), 
                    "raw": msg if msg else "Keine Meldung"
                }
    except Exception as e:
        print(f"Fehler Lötschberg-API: {e}")

    # --- 2. FURKA (RSS Feed) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        # Initialisiere Furka-Stationen, falls sie nicht im Feed sind
        if "Oberwald" not in results: results["Oberwald"] = {"min": 0, "raw": "Keine Meldung"}
        if "Realp" not in results: results["Realp"] = {"min": 0, "raw": "Keine Meldung"}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # WICHTIG: Überspringe reine Fahrplan-Informationen
            noise_words = ["stündlich", "abfahrt", "fahrplan", "verkehren"]
            if any(word in full_text.lower() for word in noise_words):
                continue
                
            # Verarbeite nur echte Wartezeit-Meldungen
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                elif "Realp" in full_text:
                    results["Realp"] = {"min": val, "raw": full_text}
    except Exception as e:
        print(f"Fehler Furka-RSS: {e}")
        
    return results
    
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

