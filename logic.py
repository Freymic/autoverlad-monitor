import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
import pytz
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

CH_TZ = pytz.timezone('Europe/Zurich')

def parse_time_to_minutes(text):
    """Extrahiert Minuten aus Text (z.B. '1 Stunde 20 Minuten' -> 80)."""
    if not text: return 0
    std = re.search(r'(\d+)\s*Stunde', text, re.IGNORECASE)
    mn = re.search(r'(\d+)\s*Minute', text, re.IGNORECASE)
    val = (int(std.group(1)) * 60 if std else 0) + (int(mn.group(1)) if mn else 0)
    return val

def get_quantized_timestamp():
    """Gibt den aktuellen 5-Minuten-Slot in Schweizer Zeit zurück."""
    now_ch = datetime.now(pytz.utc).astimezone(CH_TZ)
    rounded_minute = (now_ch.minute // 5) * 5
    return now_ch.replace(minute=rounded_minute, second=0, microsecond=0)

def fetch_furka_data():
    results = {"Oberwald": {"min": 0, "raw": ""}, "Realp": {"min": 0, "raw": ""}}
    try:
        resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=10)
        resp.encoding = 'utf-8'
        root = ET.fromstring(resp.content)
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            val = parse_time_to_minutes(full)
            raw = ET.tostring(item, encoding='unicode')
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": raw}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": raw}
    except: pass
    return results

def fetch_loetschberg_data():
    results = {"Kandersteg": {"min": 0, "raw": ""}, "Goppenstein": {"min": 0, "raw": ""}}
    try:
        resp = requests.get("https://www.bls.ch/de/fahren/autoverlad/betriebslage", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        for s in results.keys():
            match = re.search(rf"{s}.{{0,100}}?(\d+)\s*(Minute|Stunde)", text, re.I | re.S)
            if match:
                results[s] = {"min": parse_time_to_minutes(match.group(0)), "raw": match.group(0)}
    except: pass
    return results
