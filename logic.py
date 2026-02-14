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
    res = {s: {"min": 0, "raw": "Keine Info"} for s in ["Oberwald", "Realp", "Kandersteg", "Goppenstein"]}
    try:
        # --- FURKA (MGB) ---
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            val = parse_time_to_minutes(full)
            if "Oberwald" in full: res["Oberwald"] = {"min": val, "raw": ET.tostring(item, encoding='unicode')}
            if "Realp" in full: res["Realp"] = {"min": val, "raw": ET.tostring(item, encoding='unicode')}
        
        # --- LÖTSCHBERG (BLS) - GEZIELTE SUCHE ---
        l_resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(l_resp.text, 'html.parser')
        
        # Wir suchen alle "stLine" Container aus deinem Screenshot
        delay_elements = soup.find_all("div", class_="stLine")
        
        for element in delay_elements:
            name_div = element.find("div", class_="stName")
            info_div = element.find("div", class_="stInfo")
            
            if name_div and info_div:
                st_name = name_div.get_text(strip=True)
                st_info = info_div.get_text(strip=True)
                
                if st_name in ["Kandersteg", "Goppenstein"]:
                    val = parse_time_to_minutes(st_info)
                    # Wir speichern den exakten HTML-Teil als Raw-Info
                    res[st_name] = {
                        "min": val, 
                        "raw": str(element) 
                    }
    except Exception as e:
        print(f"Fetch Error: {e}")
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
