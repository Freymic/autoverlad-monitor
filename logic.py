import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
from datetime import datetime
import pytz

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def parse_time_to_minutes(time_str):
    """Sicheres Mapping von Text-Phrasen zu Minutenwerten."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. HARDCODED MAPPING (Priorität 1)
    # Da die Texte standardisiert sind, ist dies die stabilste Lösung.
    if "keine wartezeit" in text or "no waiting" in text:
        return 0
    if "1 stunde 30 minuten" in text:
        return 90
    if "2 stunden 30 minuten" in text:
        return 150
    if "1 stunde" in text:
        return 60
    if "2 stunden" in text:
        return 120
    if "30 minuten" in text or "30 min" in text:
        return 30

    # 2. DYNAMISCHER FALLBACK (Priorität 2)
    # Falls eine krumme Zahl auftaucht, die nicht im Mapping ist.
    total_min = 0
    # Stunden finden (1 stunde oder 2 stunden)
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match:
        total_min += int(hour_match.group(1)) * 60
    
    # Minuten finden (nur Zahlen, die nicht Teil einer Uhrzeit XX:XX sind)
    min_match = re.search(r'(?<!:)(\b\d+)\s*min', text)
    if min_match:
        total_min += int(min_match.group(1))
        
    return total_min

def fetch_all_data():
    """Holt Daten von Lötschberg und Furka und kombiniert sie."""
    results = {}
    
    # --- TEIL 1: LÖTSCHBERG (Wiederhergestellt) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {
                    "min": parse_time_to_minutes(msg), 
                    "raw": msg if msg else "No waiting times"
                }
    except Exception as e:
        print(f"Lötschberg Fehler: {e}")

    # --- TEIL 2: FURKA ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        # Sicherstellen, dass Oberwald/Realp existieren
        if "Oberwald" not in results: results["Oberwald"] = {"min": 0, "raw": "Keine Meldung"}
        if "Realp" not in results: results["Realp"] = {"min": 0, "raw": "Keine Meldung"}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # Fahrplan-Rauschen ("stündlich") ignorieren
            if "stündlich" in full_text.lower() or "abfahrt" in full_text.lower():
                continue
            
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                elif "Realp" in full_text:
                    results["Realp"] = {"min": val, "raw": full_text}
    except Exception as e:
        print(f"Furka Fehler: {e}")
        
    return results
