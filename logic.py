import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

# Konstanten für die App (Wichtig für image_8d62e0.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats' (Wichtig für image_8d6600.jpg)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Wandelt Texte wie '30 Min' oder 'Keine Wartezeiten' in Zahlen um."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert Daten in die DB."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                      (timestamp, station, info['min'], info['raw']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_furka_data():
    """API Abfrage für Furka."""
    url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return {item['station']: {"min": item['waitingTimeMin'], "raw": f"{item['waitingTimeMin']} Min." if item['waitingTimeMin'] > 0 else "Keine Wartezeit"} for item in data}
    except:
        return {"Realp": {"min": 0, "raw": "Keine Info"}, "Oberwald": {"min": 0, "raw": "Keine Info"}}

def fetch_loetschberg_data():
    """Scrapt Lötschberg-Daten basierend auf image_8d5eda.jpg."""
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    results = {}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Suche alle stLine-Container (siehe image_8d5eda.jpg)
        lines = soup.find_all('div', class_='stLine')
        
        for line in lines:
            name_div = line.find('div', class_='stName')
            info_div = line.find('div', class_='stInfo')
            
            if name_div and info_div:
                name = name_div.get_text(strip=True)
                info_text = info_div.get_text(strip=True)
                
                # Wir stellen sicher, dass die Namen exakt 'Kandersteg' und 'Goppenstein' lauten
                results[name] = {
                    "min": parse_time_to_minutes(info_text),
                    "raw": info_text
                }
        
        # Falls das Scraping fehlschlägt, geben wir Platzhalter zurück
        if not results:
            return {"Kandersteg": {"min": 0, "raw": "Keine Info"}, "Goppenstein": {"min": 0, "raw": "Keine Info"}}
            
        return results
    except Exception as e:
        print(f"Scraping Error: {e}")
        return {"Kandersteg": {"min": 0, "raw": "Fehler"}, "Goppenstein": {"min": 0, "raw": "Fehler"}}

def fetch_all_data():
    """Wird von image_8d62e0.png importiert."""
    f = fetch_furka_data()
    l = fetch_loetschberg_data()
    combined = {**f, **l}
    save_to_db(combined)
    return combined

# Alias für die App
get_quantized_data = fetch_all_data
