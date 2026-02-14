import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

# Konstanten für die App
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """Erstellt die Datenbank-Struktur, falls sie noch nicht existiert."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS waiting_times
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Wandelt Texte wie '30 Min' oder 'Keine Wartezeit' in Zahlen um."""
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die kombinierten Daten in die SQLite DB."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO waiting_times VALUES (?, ?, ?, ?)",
                      (timestamp, station, info['min'], info['raw']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Datenbankfehler: {e}")

def fetch_furka_data():
    """API Abfrage für Furka (Realp & Oberwald)."""
    url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        results = {}
        for item in data:
            station = item.get("station")
            wait_min = item.get("waitingTimeMin", 0)
            results[station] = {
                "min": wait_min,
                "raw": f"{wait_min} Min." if wait_min > 0 else "Keine Wartezeit"
            }
        return results
    except:
        return {}

def fetch_loetschberg_data():
    """Web-Scraping für Lötschberg (Kandersteg & Goppenstein)."""
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = {}
        # Nutzt die Klassen aus deinem Screenshot (Image 8ceafc)
        stations = soup.find_all('div', class_='stLine')
        for station in stations:
            name_div = station.find('div', class_='stName')
            info_div = station.find('div', class_='stInfo')
            if name_div and info_div:
                name = name_div.get_text(strip=True)
                info_text = info_div.get_text(strip=True)
                results[name] = {
                    "min": parse_time_to_minutes(info_text),
                    "raw": info_text
                }
        return results
    except:
        return {}

def fetch_all_data():
    """Zentraler Aufruf für beide Pässe."""
    data_f = fetch_furka_data()
    data_l = fetch_loetschberg_data()
    combined = {**data_f, **data_l}
    return combined

def get_quantized_data():
    """Hilfsfunktion, falls die App diesen Namen statt fetch_all_data nutzt."""
    return fetch_all_data()
