import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

# Diese Konstanten werden von autoverlad_app.py erwartet (siehe image_8d7123.png)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats', die pandas in image_8d6600.jpg sucht."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Zahlen aus Texten."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die Daten in der DB."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                      (timestamp, station, info.get('min', 0), info.get('raw', '')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_all_data():
    """Die Hauptfunktion, die alles zusammenführt (Wichtig für den Import)."""
    results = {}
    
    # 1. Furka Daten (API)
    try:
        f_url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
        f_res = requests.get(f_url, timeout=10).json()
        for item in f_res:
            name = item.get('station')
            wait = item.get('waitingTimeMin', 0)
            results[name] = {
                "min": wait,
                "raw": f"{wait} Min. Wartezeit" if wait > 0 else "Keine Wartezeit"
            }
    except:
        results["Realp"] = {"min": 0, "raw": "Keine Info (MGB)"}
        results["Oberwald"] = {"min": 0, "raw": "Keine Info (MGB)"}

    # 2. Lötschberg Daten (Web Scraping basierend auf image_8ceafc.png)
    try:
        l_url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        l_res = requests.get(l_url, headers=headers, timeout=15)
        soup = BeautifulSoup(l_res.text, 'html.parser')
        
        # Suche nach den stLine Containern aus deinem Quelltext-Screenshot
        lines = soup.find_all('div', class_='stLine')
        for line in lines:
            name_div = line.find('div', class_='stName')
            info_div = line.find('div', class_='stInfo')
            if name_div and info_div:
                s_name = name_div.get_text(strip=True)
                s_info = info_div.get_text(strip=True)
                results[s_name] = {
                    "min": parse_time_to_minutes(s_info),
                    "raw": s_info
                }
    except:
        if "Kandersteg" not in results:
            results["Kandersteg"] = {"min": 0, "raw": "Keine Info (BLS)"}
            results["Goppenstein"] = {"min": 0, "raw": "Keine Info (BLS)"}

    # Daten speichern
    save_to_db(results)
    return results

# Alias für die App (falls benötigt)
get_quantized_data = fetch_all_data
