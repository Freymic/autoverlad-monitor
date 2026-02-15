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
    """Extrahiert alle Zeitangaben und addiert sie (z.B. 1 Std + 30 Min = 90)."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # Sofort-Check für "Keine Wartezeit"
    if any(phrase in text for phrase in ["keine wartezeit", "0 min", "no waiting"]):
        return 0

    total_min = 0

    # 1. STUNDEN finden (sucht nach Zahlen vor 'stunde' oder 'std')
    # findall stellt sicher, dass wir auch mehrere Nennungen finden
    hours = re.findall(r'(\d+)\s*(?:stunde|std)', text)
    if hours:
        # Wir nehmen nur die erste Nennung, um Verdopplungen im Text zu vermeiden
        total_min += int(hours[0]) * 60

    # 2. MINUTEN finden (sucht nach Zahlen vor 'min')
    # Der Lookbehind (?<!:) ignoriert Uhrzeiten wie 16:35
    minutes = re.findall(r'(?<!:)(\b\d+)\s*min', text)
    if minutes:
        # Falls Stunden gefunden wurden, nehmen wir die Minuten danach
        # Falls keine Stunden da sind, nehmen wir die erste Minutenzahl
        total_min += int(minutes[0])

    return total_min

def fetch_all_data():
    results = {}
    
    # --- TEIL 1: LÖTSCHBERG ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10).json()
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "No waiting times")
                results[name] = {"min": parse_time_to_minutes(msg), "raw": msg}
    except: pass

    # --- TEIL 2: FURKA ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        for item in root.findall('.//item'):
            full_text = f"{item.find('title').text} {item.find('description').text}"
            
            # Filter gegen die stündlichen Fahrplan-Meldungen
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]):
                continue
            
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                elif "Realp" in full_text:
                    results["Realp"] = {"min": val, "raw": full_text}
    except: pass
    
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

