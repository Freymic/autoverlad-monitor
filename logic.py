import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

# Diese Namen MÜSSEN exakt so bleiben (für image_8d62e0.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats' (passend zu image_8d6600.jpg)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Wir nennen die Tabelle 'stats', weil pandas in Zeile 35 danach sucht
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert Daten in die Tabelle 'stats'."""
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
    """Holt Furka-Daten."""
    url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return {item['station']: {"min": item['waitingTimeMin'], "raw": f"{item['waitingTimeMin']} Min."} for item in data}
    except:
        return {"Realp": {"min": 0, "raw": "Keine Info"}, "Oberwald": {"min": 0, "raw": "Keine Info"}}

def fetch_loetschberg_data():
    """Scrapt Lötschberg-Daten und passt die Namen an die App an."""
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = {}
        
        # Wir suchen die stLine Container aus deinem Screenshot (image_8ceafc.png)
        for div in soup.find_all('div', class_='stLine'):
            name_div = div.find('div', class_='stName')
            info_div = div.find('div', class_='stInfo')
            
            if name_div and info_div:
                raw_name = name_div.get_text(strip=True)
                info_text = info_div.get_text(strip=True)
                
                # WICHTIG: Mapping der Namen
                # Falls deine App "Lötschberg Kandersteg" statt "Kandersteg" sucht:
                display_name = raw_name
                if "Kandersteg" in raw_name:
                    display_name = "Kandersteg" # Oder "Lötschberg Kandersteg" - je nach App
                elif "Goppenstein" in raw_name:
                    display_name = "Goppenstein"
                
                results[display_name] = {
                    "min": parse_time_to_minutes(info_text),
                    "raw": info_text
                }
        return results
    except Exception as e:
        print(f"Lötschberg Fehler: {e}")
        return {}

def fetch_all_data():
    """Kombiniert alles (für den Import in image_8d62e0.png)."""
    f = fetch_furka_data()
    l = fetch_loetschberg_data()
    combined = {**f, **l}
    save_to_db(combined) # Speichert automatisch bei jedem Abruf
    return combined

def get_quantized_data():
    """Zusätzlicher Alias für die App."""
    return fetch_all_data()
