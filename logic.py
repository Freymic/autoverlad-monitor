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
    res = {s: {"min": 0, "raw": "Warte auf Daten..."} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    
    try:
        # 1. LÖTSCHBERG (BLS) - Jetzt mit tieferer Suche
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=15, headers=headers)
        l_resp.encoding = 'utf-8'
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        
        # Wir suchen alle Container mit der Klasse 'stLine'
        # Wir nutzen .select(), das ist bei komplexen Klassen-Kombinationen oft treffsicherer
        lines = soup.select("div.stLine")
        
        if not lines:
            # Plan B: Falls stLine nicht direkt gefunden wird, suchen wir nach den Namen
            for s_name in ["Kandersteg", "Goppenstein"]:
                name_tag = soup.find(string=re.compile(s_name))
                if name_tag:
                    # Wir hangeln uns vom Namen zum Info-Feld
                    parent = name_tag.find_parent("div", class_="stLine")
                    if parent:
                        info_div = parent.find("div", class_="stInfo")
                        if info_div:
                            txt = info_div.get_text(strip=True)
                            res[s_name] = {"min": parse_time_to_minutes(txt), "raw": txt}
        else:
            for line in lines:
                name_div = line.find("div", class_="stName")
                info_div = line.find("div", class_="stInfo")
                if name_div and info_div:
                    name = name_div.get_text(strip=True)
                    info = info_div.get_text(strip=True)
                    if name in res:
                        res[name] = {"min": parse_time_to_minutes(info), "raw": info}

        # 2. FURKA (MGB) - Dein funktionierender Teil
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            for s in ["Oberwald", "Realp"]:
                if s in title:
                    res[s] = {"min": parse_time_to_minutes(title), "raw": title}

    except Exception as e:
        # Fehler direkt in die Raw-Info schreiben für das Debugging
        for s in ["Kandersteg", "Goppenstein"]:
            res[s]["raw"] = f"Error: {str(e)[:50]}"
            
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
