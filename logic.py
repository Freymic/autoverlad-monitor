import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
import datetime
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai

# --- KONSTANTEN & SETUP ---
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

# Gemini Setup
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- DATENBANK LOGIK ---

def init_db():
    """Initialisiert die DB und stellt bei Bedarf Daten aus GSheets wieder her."""
    with sqlite3.connect(DB_NAME, timeout=20) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS stats
                     (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
        conn.commit()
        
        c.execute("SELECT COUNT(*) FROM stats")
        if c.fetchone()[0] == 0:
            restore_from_gsheets(conn)

def restore_from_gsheets(sqlite_conn):
    """Backup-Wiederherstellung von Google Sheets."""
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Sheet1")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        df = conn_gs.read(worksheet=sheet_name, ttl=0)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
            df_recent = df[df['timestamp'] > cutoff]
            if not df_recent.empty:
                df_recent.to_sql('stats', sqlite_conn, if_exists='append', index=False)
                st.info(f"🔄 Cloud-Restore: {len(df_recent)} Zeilen geladen.")
    except Exception as e:
        st.warning(f"Cloud-Restore übersprungen: {e}")

# --- PARSING & API LOGIK ---

def parse_time_to_minutes(time_str):
    """Mapping von Text-Phrasen zu Minutenwerten."""
    if not time_str: return 0
    text = time_str.lower()
    
    mapping = {
        "4 stunden": 240, "3 stunden": 180, "2 stunden": 120, "1 stunde": 60,
        "45 minuten": 45, "30 minuten": 30, "15 minuten": 15, "keine wartezeit": 0
    }
    for phrase, minutes in mapping.items():
        if phrase in text: return minutes

    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match: total_min += int(hour_match.group(1)) * 60
    min_match = re.search(r'(\b\d+)\s*(?:min|minute)', text)
    if min_match: total_min += int(min_match.group(1))
    return total_min

# --- KI LOGIK (ZENTRALISIERT) ---

def check_all_statuses_with_ai(bls_text, mgb_text):
    """
    Fragt Gemini einmalig für beide Verladestationen ab, um Kosten/Zeit zu sparen.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Analysiere diese Verkehrsmeldungen aus der Schweiz:
        LÖTSCHBERG (BLS): "{bls_text}"
        FURKA (MGB): "{mgb_text}"

        FRAGE: Ist der AUTOVERLAD (Autozüge) für die jeweilige Strecke aktuell GESPERRT?
        HINWEIS: Bahnverkehr-Unterbrüche für Personenzüge sind keine Sperrung für Autozüge.
        
        Antworte NUR im JSON-Format:
        {{"loetschberg": "OFFEN" oder "GESPERRT", "furka": "OFFEN" oder "GESPERRT"}}
        """
        response = model.generate_content(prompt)
        # Extrahiere JSON aus der Antwort (Regex als Fallback falls die KI Markdown drumherum baut)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        status_data = json.loads(json_match.group())
        
        return {
            "loetschberg": status_data.get("loetschberg") == "OFFEN",
            "furka": status_data.get("furka") == "OFFEN"
        }
    except Exception as e:
        print(f"KI-Zentral-Fehler: {e}")
        return {"loetschberg": True, "furka": True}

# --- HAUPTFUNKTION (MIT CACHING) ---

@st.cache_data(ttl=300) # Cache für 5 Minuten
def fetch_all_data():
    """Holt alle Wartezeiten und Status-Informationen gebündelt ab."""
    results = {}
    bls_raw_notes = ""
    mgb_raw_notes = ""

    # 1. LÖTSCHBERG API
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {"min": parse_time_to_minutes(msg), "raw": msg or "Keine Wartezeit"}
        
        # Status-Meldungen sammeln
        l_stat_url = "https://www.bls.ch/api/TrafficInformation/GetNewNotifications?sc_lang=de&sc_site=internet-bls"
        l_stat_res = requests.get(l_stat_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'}).json()
        bls_raw_notes = " | ".join([n.get("title", "") for n in l_stat_res.get("trafficInformations", [])])
    except: pass

    # 2. FURKA RSS
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}".lower()
            mgb_raw_notes += f" {full_text}"
            
            if "wartezeit" in full_text:
                val = parse_time_to_minutes(full_text)
                for s in ["Oberwald", "Realp"]:
                    if s.lower() in full_text and s not in results:
                        results[s] = {"min": val, "raw": title}
        
        # Defaults
        for s in ["Oberwald", "Realp"]:
            if s not in results: results[s] = {"min": 0, "raw": "Keine Meldung"}
    except: pass

    # 3. KI STATUS-VETO
    status_map = check_all_statuses_with_ai(bls_raw_notes, mgb_raw_notes)
    
    return {
        "wait_times": results,
        "active_status": status_map
    }

# --- SPEICHER LOGIK ---

def save_to_db(data_payload):
    """Speichert die Wartezeiten in die lokale Datenbank."""
    try:
        data = data_payload["wait_times"]
        now = datetime.datetime.now(CH_TZ)
        ts_str = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(DB_NAME, timeout=20) as conn:
            c = conn.cursor()
            for station, info in data.items():
                c.execute("INSERT OR IGNORE INTO stats VALUES (?, ?, ?, ?)",
                          (ts_str, station, info.get('min', 0), info.get('raw', '')))
            conn.commit()
    except Exception as e: print(f"DB Save Error: {e}")

def save_to_google_sheets(data_payload):
    """Synchronisiert die Daten mit Google Sheets."""
    try:
        data = data_payload["wait_times"]
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Development")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        
        now = datetime.datetime.now(CH_TZ)
        ts_str = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        new_entries = [{"timestamp": ts_str, "station": s, "minutes": i['min'], "raw_text": i['raw']} for s, i in data.items()]
        df_existing = conn_gs.read(worksheet=sheet_name, ttl=0)
        df_final = pd.concat([df_existing, pd.DataFrame(new_entries)], ignore_index=True).drop_duplicates(subset=['timestamp', 'station'], keep='last')
        
        conn_gs.update(worksheet=sheet_name, data=df_final)
        return True
    except: return False

# --- PÄSSE & REPORT LOGIK ---

def get_pass_status():
    """Fragt den Status der Alpenpässe ab."""
    status_dict = {"Furkapass": False, "Grimselpass": False, "Nufenenpass": False, "Brünigpass": True}
    try:
        resp = requests.get("https://www.alpen-paesse.ch/de/alpenpaesse/status.rss", timeout=10)
        root = ET.fromstring(resp.content)
        for item in root.findall('.//item'):
            title = item.find('title').text.lower()
            for p in status_dict.keys():
                if p.lower() in title:
                    status_dict[p] = "offen" in title
    except: pass
    return status_dict
