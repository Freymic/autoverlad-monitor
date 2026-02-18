import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
import datetime
import pytz
import json
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai

# --- KONSTANTEN & SETUP ---
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- DATENBANK & HILFSFUNKTIONEN ---

def init_db():
    with sqlite3.connect(DB_NAME, timeout=20) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS stats
                     (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
        conn.commit()

def parse_time_to_minutes(time_str):
    if not time_str: return 0
    text = time_str.lower()
    mapping = {"4 stunden": 240, "3 stunden": 180, "2 stunden": 120, "1 stunde": 60, "45 min": 45, "30 min": 30, "15 min": 15, "keine wartezeit": 0}
    for phrase, minutes in mapping.items():
        if phrase in text: return minutes
    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match: total_min += int(hour_match.group(1)) * 60
    min_match = re.search(r'(\b\d+)\s*(?:min|minute)', text)
    if min_match: total_min += int(min_match.group(1))
    return total_min

# --- EXTERNE APIS (MAPS & FAHRPLAN) ---

def get_google_maps_duration(origin, destination, waypoints=None):
    """Simuliert Google Maps Dauer (hier Platzhalter für deine API Logik)."""
    # Hier kommt normalerweise dein API-Request hin
    return 120 # Beispielwert: 2 Stunden

def get_furka_departure(arrival_time):
    """Gibt die nächste Abfahrt ab Realp zurück (vereinfacht)."""
    return arrival_time + datetime.timedelta(minutes=30)

def get_loetschberg_departure(arrival_time):
    """Gibt die nächste Abfahrt ab Kandersteg zurück (vereinfacht)."""
    return arrival_time + datetime.timedelta(minutes=20)

# --- STATUS & KI ---

def get_pass_status():
    status = {"Furkapass": False, "Grimselpass": False, "Nufenenpass": False, "Brünigpass": True}
    try:
        resp = requests.get("https://www.alpen-paesse.ch/de/alpenpaesse/status.rss", timeout=5)
        root = ET.fromstring(resp.content)
        for item in root.findall('.//item'):
            t = item.find('title').text.lower()
            for p in status:
                if p.lower() in t: status[p] = "offen" in t
    except: pass
    return status

def check_all_statuses_with_ai(bls_text, mgb_text):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Analysiere: BLS: {bls_text} | MGB: {mgb_text}. Ist der Autoverlad GESPERRT? JSON: {{'loetschberg': 'OFFEN'/'GESPERRT', 'furka': 'OFFEN'/'GESPERRT'}}"
        res = model.generate_content(prompt)
        match = re.search(r'\{.*\}', res.text, re.DOTALL)
        data = json.loads(match.group())
        return {"loetschberg": data.get("loetschberg") == "OFFEN", "furka": data.get("furka") == "OFFEN"}
    except: return {"loetschberg": True, "furka": True}

@st.cache_data(ttl=300)
def fetch_all_data():
    results = {}
    bls_notes, mgb_notes = "", ""
    
    # BLS Abruf
    try:
        l_res = requests.get("https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}", timeout=5).json()
        for s in l_res.get("Stations", []):
            if s.get("Station") in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[s.get("Station")] = {"min": parse_time_to_minutes(msg), "raw": msg or "Keine Wartezeit"}
    except: pass

    # MGB Abruf
    try:
        f_resp = requests.get("https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de", timeout=5)
        root = ET.fromstring(f_resp.content)
        for item in root.findall('.//item'):
            txt = (item.find('title').text + " " + item.find('description').text).lower()
            mgb_notes += txt
            if "wartezeit" in txt:
                m = parse_time_to_minutes(txt)
                for s in ["Realp", "Oberwald"]: results[s] = {"min": m, "raw": txt[:50]}
    except: pass

    # Defaults falls API leer
    for s in ["Kandersteg", "Goppenstein", "Realp", "Oberwald"]:
        if s not in results: results[s] = {"min": 0, "raw": "Keine Meldung"}

    return {"wait_times": results, "active_status": check_all_statuses_with_ai(bls_notes, mgb_notes)}

# --- GEMINI REPORTS ---

def get_gemini_summer_report(routen, pass_status):
    return "Gemini Empfehlung: Die Pässe sind traumhaft, nimm die Route über den Grimsel!"

def get_gemini_winter_report(daten):
    return "Winter-Check: Autoverlad ist heute die sicherste Wahl."

def save_to_db(payload):
    # Hier die Logik zum Speichern (siehe vorheriger Post)
    pass

def save_to_google_sheets(payload):
    return True
