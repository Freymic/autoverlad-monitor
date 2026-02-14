import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

# Konstanten (Wichtig für den Import in autoverlad_app.py)
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Tabelle 'stats', die pandas sucht."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Zahlen aus dem Text (z.B. '30 Min' -> 30)."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die Ergebnisse in der Datenbank."""
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
    """Kombiniert Furka-API und Lötschberg-Scraping."""
    results = {}
    
    # --- 1. FURKA LOGIK (Wiederhergestellt) ---
    try:
        f_url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
        f_res = requests.get(f_url, timeout=10).json()
        for item in f_res:
            # Nutzt exakt die Keys 'station' und 'waitingTimeMin'
            name = item.get('station')
            wait = item.get('waitingTimeMin', 0)
            results[name] = {
                "min": wait,
                "raw": f"Keine Wartezeit {name}." if wait == 0 else f"{wait} Min. Wartezeit"
            }
    except:
        results["Realp"] = {"min": 0, "raw": "Keine Info"}
        results["Oberwald"] = {"min": 0, "raw": "Keine Info"}

    # --- 2. LÖTSCHBERG LOGIK (Robustes Scraping) ---
    try:
        l_url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        l_res = requests.get(l_url, headers=headers, timeout=15)
        soup = BeautifulSoup(l_res.text, 'html.parser')
        
        # Gezielt nach stName und stInfo suchen
        names = [n.get_text(strip=True) for n in soup.find_all('div', class_='stName')]
        infos = [i.get_text(strip=True) for i in soup.find_all('div', class_='stInfo')]
        
        # Die Listen zusammenführen
        for name, info in zip(names, infos):
            if "Kandersteg" in name or "Goppenstein" in name:
                results[name] = {
                    "min": parse_time_to_minutes(info),
                    "raw": info if info else "Keine Wartezeiten"
                }
    except:
        pass

    # Falls Lötschberg fehlte, mit Standard füllen
    if "Kandersteg" not in results:
        results["Kandersteg"] = {"min": 0, "raw": "Warte auf Daten..."}
    if "Goppenstein" not in results:
        results["Goppenstein"] = {"min": 0, "raw": "Warte auf Daten..."}

    save_to_db(results)
    return results

# Alias für die App-Importe
get_quantized_data = fetch_all_data
