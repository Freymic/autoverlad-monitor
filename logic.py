import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pytz

DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    conn.close()

def parse_time_to_minutes(time_str):
    """Extrahiert Zahlen aus Texten wie 'ca. 20 Min' oder 'Keine Wartezeit'."""
    if not time_str:
        return 0
    
    # Alles in Kleinbuchstaben für leichteren Vergleich
    text = time_str.lower()
    
    if "keine" in text or "0" in text:
        return 0
        
    # Extrahiere alle Ziffern
    digits = ''.join(filter(str.isdigit, text))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def fetch_loetschberg_data():
    url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    
    results = {}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Suche nach den Containern aus deinem Screenshot image_8ceafc.png
        lines = soup.find_all('div', class_='stLine')
        
        for line in lines:
            name_div = line.find('div', class_='stName')
            info_div = line.find('div', class_='stInfo')
            
            if name_div and info_div:
                # Text extrem sauber extrahieren
                name = name_div.get_text(" ", strip=True)
                info_text = info_div.get_text(" ", strip=True)
                
                # Wir speichern es genau so, wie die App es braucht
                results[name] = {
                    "min": parse_time_to_minutes(info_text),
                    "raw": info_text if info_text else "Keine Info"
                }
        
        # Sicherheit: Falls die Liste leer blieb
        if not results:
             return {"Kandersteg": {"min": 0, "raw": "Warte auf BLS..."}, 
                     "Goppenstein": {"min": 0, "raw": "Warte auf BLS..."}}
        return results
    except Exception as e:
        return {"Kandersteg": {"min": 0, "raw": f"Fehler: {str(e)[:20]}"}, 
                "Goppenstein": {"min": 0, "raw": "Fehler"}}

def fetch_furka_data():
    url = "https://www.matterhorngotthardbahn.ch/api/autoverlad/waiting-times"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        results = {}
        for item in data:
            station = item.get('station')
            wait_min = item.get('waitingTimeMin', 0)
            results[station] = {
                "min": wait_min,
                "raw": f"{wait_min} Min." if wait_min > 0 else "Keine Wartezeit"
            }
        return results
    except:
        return {"Realp": {"min": 0, "raw": "Keine Info (MGB)"}, 
                "Oberwald": {"min": 0, "raw": "Keine Info (MGB)"}}

def fetch_all_data():
    f_data = fetch_furka_data()
    l_data = fetch_loetschberg_data()
    combined = {**f_data, **l_data}
    
    # Speichern für die Historie-Grafik (Wichtig für image_8d6600.jpg)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for s, i in combined.items():
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", (now, s, i['min'], i['raw']))
        conn.commit()
        conn.close()
    except:
        pass
        
    return combined

get_quantized_data = fetch_all_data
