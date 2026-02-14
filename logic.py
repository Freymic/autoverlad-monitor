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
    """Scrapt Lötschberg-Daten (Kandersteg/Goppenstein)."""
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = {}
        for div in soup.find_all('div', class_='stLine'):
            name = div.find('div', class_='stName').get_text(strip=True)
            info = div.find('div', class_='stInfo').get_text(strip=True)
            results[name] = {"min": parse_time_to_minutes(info), "raw": info}
        return results
    except:
        return {"Kandersteg": {"min": 0, "raw": "Keine Info"}, "Goppenstein": {"min": 0, "raw": "Keine Info"}}

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
