import requests
import xml.etree.ElementTree as ET
import sqlite3
import json
from datetime import datetime, timedelta
import pytz

# Konstanten
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
    if not time_str or any(word in time_str.lower() for word in ["keine", "no", "none"]):
        return 0
    digits = ''.join(filter(str.isdigit, time_str))
    return int(digits) if digits else 0

def save_to_db(data):
    """Speichert Daten im 5-Minuten-Raster (xx:00, xx:05...)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.now(CH_TZ)
        minute_q = (now.minute // 5) * 5
        q_now = now.replace(minute=minute_q, second=0, microsecond=0)
        ts_str = q_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (ts_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (ts_str, station, info.get('min', 0), info.get('raw', '')))
        
        # Cleanup: Alles älter als 14 Tage löschen
        cutoff = (now - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("DELETE FROM stats WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def fetch_all_data():
    """Wartezeiten abrufen."""
    results = {}
    # FURKA
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        results["Oberwald"] = {"min": 0, "raw": "Keine Wartezeit."}
        results["Realp"] = {"min": 0, "raw": "Keine Wartezeit."}
        for item in root.findall('.//item'):
            full = f"{item.find('title').text} {item.find('description').text}"
            val = parse_time_to_minutes(full)
            if "Oberwald" in full: results["Oberwald"] = {"min": val, "raw": full}
            if "Realp" in full: results["Realp"] = {"min": val, "raw": full}
    except: pass

    # LÖTSCHBERG
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10).json()
        for entry in l_res.get("Stations", []):
            name = entry.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                results[name] = {"min": parse_time_to_minutes(entry.get("DelayMessage")), "raw": json.dumps(entry)}
    except: pass
    return results

def fetch_bls_timetable():
    """Holt Fahrplan direkt von BLS (Kandersteg/Goppenstein)."""
    url = "https://www.bls.ch/avl/AutoverladWidgetV2/GetAutoverladModel"
    try:
        # POST Request ohne Payload liefert Standard-Widget-Daten
        res = requests.post(url, json={"query": ""}, timeout=10).json()
        bls_map = {}
        for s in res.get('Stations', []):
            name = s.get('StationName')
            if name in ["Kandersteg", "Goppenstein"]:
                deps = [f"{d['DepartureTime']} -> {d['Destination']}" for d in s.get('Departures', [])[:3]]
                bls_map[name] = deps if deps else ["Keine Abfahrten"]
        return bls_map
    except:
        return {"Kandersteg": ["Fehler"], "Goppenstein": ["Fehler"]}

def fetch_furka_timetable(sid):
    """Holt Fahrplan für Furka via OpenData."""
    try:
        url = f"https://transport.opendata.ch/v1/stationboard?id={sid}&limit=10"
        res = requests.get(url, timeout=5).json()
        deps = []
        for j in res.get('stationboard', []):
            if j.get('category') in ['AT', 'BAT', 'R']:
                t = datetime.fromisoformat(j['stop']['departure'].replace('Z', '+00:00')).astimezone(CH_TZ).strftime('%H:%M')
                deps.append(f"{t} -> {j['to']}")
            if len(deps) >= 3: break
        return deps if deps else ["Keine Abfahrten"]
    except: return ["Fehler"]

def get_all_timetables():
    """Kombiniert BLS und Furka Fahrpläne."""
    data = fetch_bls_timetable()
    data["Oberwald"] = fetch_furka_timetable("8505169")
    data["Realp"] = fetch_furka_timetable("8505165")
    return data
