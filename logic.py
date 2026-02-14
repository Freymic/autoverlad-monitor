import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
import sqlite3
from datetime import datetime
import pytz

# Konstanten für die App (Wichtig für image_8d7123.png)
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
    if not time_str or "Keine" in time_str:
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

def save_to_db(data):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        timestamp = datetime.now(CH_TZ).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                      (timestamp, station, info.get('min', 0), info.get('raw', '')))
        conn.commit()
        conn.close()
    except:
        pass

def fetch_all_data():
    results = {}
    
    # --- 1. FURKA LOGIK (Deine RSS-Version) ---
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        
        # Standardwerte, falls nichts im Feed steht
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit Oberwald."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit Realp."}
        
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            full = f"{title} {desc}"
            
            # Zeit-Extraktion aus deinem Code
            m = re.search(r'(\d+)\s*Minute', full)
            h = re.search(r'(\d+)\s*Stunde', full)
            val = (int(h.group(1))*60 if h else int(m.group(1)) if m else 0)
            
            raw_text = desc if desc else "Keine Wartezeit."
            
            if "Oberwald" in full:
                results["Oberwald"] = {"min": val, "raw": raw_text}
            if "Realp" in full:
                results["Realp"] = {"min": val, "raw": raw_text}
    except Exception as e:
        print(f"Furka RSS Fehler: {e}")

    # --- 2. LÖTSCHBERG LOGIK (Web Scraping) ---
    try:
        l_url = "https://www.bls.ch/de/fahren/autoverlad/loetschberg/betriebslage"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        l_res = requests.get(l_url, headers=headers, timeout=15)
        soup = BeautifulSoup(l_res.text, 'html.parser')
        
        # Suche nach stName und stInfo (siehe image_8ceafc.png)
        lines = soup.find_all('div', class_='stLine')
        for line in lines:
            n_div = line.find('div', class_='stName')
            i_div = line.find('div', class_='stInfo')
            if n_div and i_div:
                name = n_div.get_text(strip=True)
                info = i_div.get_text(strip=True)
                results[name] = {"min": parse_time_to_minutes(info), "raw": info}
    except:
        pass

    # Sicherstellen, dass die Keys für die App existieren
    for s in ["Kandersteg", "Goppenstein"]:
        if s not in results:
            results[s] = {"min": 0, "raw": "Keine Info"}

    save_to_db(results)
    return results

# Alias für die App
get_quantized_data = fetch_all_data
