import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime

def parse_time_to_minutes(time_str):
    """Konvertiert Texte wie '30 Min' oder 'Keine Wartezeit' in Integer-Minuten."""
    if not time_str or "Keine" in time_str:
        return 0
    # Extrahiert alle Ziffern aus dem String
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    """Speichert die aktuellen Werte in der lokalen SQLite Datenbank."""
    try:
        conn = sqlite3.connect('autoverlad.db')
        c = conn.cursor()
        # Tabelle anlegen, falls sie noch nicht existiert
        c.execute('''CREATE TABLE IF NOT EXISTS waiting_times
                     (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO waiting_times VALUES (?, ?, ?, ?)",
                      (timestamp, station, info['min'], info['raw']))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Datenbankfehler: {e}")

def fetch_furka_data():
    """Holt Furka-Daten via API."""
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
    """Holt Lötschberg-Daten via Web-Scraping (BLS)."""
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        results = {}
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

def get_quantized_data():
    """Hauptfunktion für Streamlit: Holt Daten und speichert sie."""
    data_furka = fetch_furka_data()
    data_loetschberg = fetch_loetschberg_data()
    
    # Kombinieren
    combined_data = {**data_furka, **data_loetschberg}
    
    # Speichern für die Historie-Grafiken
    if combined_data:
        save_to_db(combined_data)
        
    return combined_data
