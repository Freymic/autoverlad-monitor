import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
import pytz
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

DB_NAME = 'autoverlad_final_v3.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def parse_time_to_minutes(text):
    if not text: return 0
    std = re.search(r'(\d+)\s*Stunde', text, re.I)
    mn = re.search(r'(\d+)\s*Minute', text, re.I)
    return (int(std.group(1)) * 60 if std else 0) + (int(mn.group(1)) if mn else 0)

def fetch_all_data():
    # Standardwerte setzen
    res = {s: {"min": 0, "raw": "Warte auf Daten..."} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    
    try:
        # --- LÖTSCHBERG (BLS) ---
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        l_resp.encoding = 'utf-8'
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        
        # Wir suchen gezielt nach der Struktur aus deinem Screenshot
        # Falls die Klasse 'stLine' nicht gefunden wird, nutzen wir einen CSS-Selektor als Backup
        lines = soup.find_all("div", class_="stLine")
        
        for line in lines:
            name_div = line.find("div", class_="stName")
            info_div = line.find("div", class_="stInfo")
            
            if name_div and info_div:
                name = name_div.get_text(strip=True)
                info = info_div.get_text(strip=True) # Hier steht dann "Keine Wartezeiten"
                
                if name in res:
                    res[name]["min"] = parse_time_to_minutes(info)
                    res[name]["raw"] = info  # Speichert 1:1 "Keine Wartezeiten"

        # --- FURKA (MGB) ---
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        f_resp.encoding = 'utf-8'
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            # Wir nehmen den Titel als 1:1 Info für Furka
            if "Oberwald" in full_text:
                res["Oberwald"]["min"] = parse_time_to_minutes(full_text)
                res["Oberwald"]["raw"] = title
            if "Realp" in full_text:
                res["Realp"]["min"] = parse_time_to_minutes(full_text)
                res["Realp"]["raw"] = title

    except Exception as e:
        # Falls ein Fehler auftritt, schreiben wir ihn in die Raw-Info zum Debuggen
        for s in res: res[s]["raw"] = f"Fehler: {str(e)}"
        
    return res

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS stats 
                        (timestamp DATETIME, station TEXT, minuten INTEGER, raw_info TEXT)''')

def save_to_db(data_dict):
    now_ch = datetime.now(pytz.utc).astimezone(CH_TZ)
    rounded_minute = (now_ch.minute // 5) * 5
    ts_rounded = now_ch.replace(minute=rounded_minute, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_NAME) as conn:
        exists = conn.execute("SELECT 1 FROM stats WHERE timestamp = ? LIMIT 1", (ts_rounded,)).fetchone()
        if not exists:
            for station, info in data_dict.items():
                conn.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", (ts_rounded, station, info['min'], info['raw']))
            return ts_rounded
    return None
