import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import json
import pandas as pd
import datetime
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

# --- ZENTRALE ROBUSTE KI-LOGIK MIT FREUNDLICHER FEHLERMELDUNG ---
def generate_content_with_fallback(prompt):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Dynamische Modellsuche
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priorisierte Liste
        preferred_order = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-pro']
        
        models_to_try = []
        for pref in preferred_order:
            found = [m for m in available_models if pref in m]
            models_to_try.extend(found)
        
        if not models_to_try:
            models_to_try = available_models

        last_error = ""
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                last_error = str(e)
                # Falls das Limit erreicht ist (429), sofort die schöne Meldung zurückgeben
                if "429" in last_error:
                    return "🤖 Der KI-Lagebericht macht gerade ein kurzes Päuseli (Limit erreicht). Die Daten unten sind aber aktuell! ✅"
                
                # Bei anderen Fehlern (z.B. 404) nächstes Modell versuchen
                if any(x in last_error.lower() for x in ["404", "not found"]):
                    continue
                else:
                    break
        
        # Wenn alle Modelle durchprobiert wurden oder ein unbekannter Fehler auftrat
        return "🤖 Der KI-Lagebericht macht gerade ein kurzes Päuseli. Die Live-Daten unten sind aber aktuell! ✅"

    except Exception as e:
        # Falls die API-Konfiguration selbst wegen Quota scheitert
        if "429" in str(e):
            return "🤖 Der KI-Lagebericht macht gerade ein kurzes Päuseli (Limit erreicht). Die Daten unten sind aber aktuell! ✅"
        return "🤖 Lagebericht aktuell nicht verfügbar. Die Live-Daten unten sind aber aktuell! ✅"

# --- DATENBANK & FETCH LOGIK (UNVERÄNDERT) ---

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        restore_from_gsheets(conn)
    conn.close()

def restore_from_gsheets(sqlite_conn):
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Sheet1")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        df = conn_gs.read(worksheet=sheet_name)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
            df_recent = df[df['timestamp'] > cutoff]
            if not df_recent.empty:
                df_recent.to_sql('stats', sqlite_conn, if_exists='append', index=False)
                st.info(f"🔄 Daten aus Cloud-Tab '{sheet_name}' wiederhergestellt.")
    except Exception as e:
        st.warning(f"Cloud-Restore übersprungen: {e}")

def parse_time_to_minutes(time_str):
    if not time_str: return 0
    text = time_str.lower()
    mapping = {
        "4 stunden": 240, "3 stunden 30 minuten": 210, "3 stunden": 180,
        "2 stunden 30 minuten": 150, "2 stunden": 120, "1 stunde 30 minuten": 90,
        "1 stunde": 60, "45 minuten": 45, "30 minuten": 30, "15 minuten": 15,
        "keine wartezeit": 0, "no waiting": 0
    }
    for phrase, minutes in mapping.items():
        if phrase in text: return minutes
    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match: total_min += int(hour_match.group(1)) * 60
    min_match = re.search(r'(?<!:)(\b\d+)\s*(?:min|minute)', text)
    if min_match: total_min += int(min_match.group(1))
    return total_min

def fetch_all_data():
    results = {}
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {"min": parse_time_to_minutes(msg), "raw": msg if msg else "Keine Wartezeit"}
    except Exception as e: print(f"Fehler Lötschberg Fetch: {e}")

    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        furka_found = {"Oberwald": False, "Realp": False}
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]): continue
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                for loc in furka_found.keys():
                    if loc in full_text and not furka_found[loc]:
                        results[loc] = {"min": val, "raw": full_text}
                        furka_found[loc] = True
        for loc, found in furka_found.items():
            if not found: results[loc] = {"min": 0, "raw": "Keine Meldung"}
    except Exception as e: print(f"Fehler Furka Fetch: {e}")

    if results:
        save_to_db(results)
        try:
            current_ws = st.secrets["connections"]["gsheets"]["worksheet"]
            if current_ws != "Development": save_to_google_sheets(results)
        except: pass 
    return results

def save_to_db(data):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        now = datetime.datetime.now(CH_TZ)
        ts_str = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (ts_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", (ts_str, station, info.get('min', 0), info.get('raw', '')))
        conn.commit()
        conn.close()
    except Exception as e: print(f"DB Error: {e}")

def save_to_google_sheets(data):
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Development")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        now = datetime.datetime.now(CH_TZ)
        ts_str = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        new_entries = [{"timestamp": ts_str, "station": s, "minutes": i.get('min', 0), "raw_text": i.get('raw', '')} for s, i in data.items()]
        df_new = pd.DataFrame(new_entries)
        try: df_existing = conn_gs.read(worksheet=sheet_name, ttl=0)
        except: df_existing = pd.DataFrame(columns=["timestamp", "station", "minutes", "raw_text"])
        df_final = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=['timestamp', 'station'], keep='last')
        conn_gs.update(worksheet=sheet_name, data=df_final)
        return True
    except Exception as e:
        st.error(f"GSheets Sync Fehler: {e}")
        return False

def get_latest_wait_times(station):
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT minutes FROM stats WHERE station = ? ORDER BY timestamp DESC LIMIT 1", conn, params=(station,))
    return int(df['minutes'].iloc[0]) if not df.empty else 0

def get_google_maps_duration(origin, destination, waypoints=None, avoid_tolls=False):
    api_key = st.secrets["G_MAPS_API_KEY"]
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    dest_query = f"{'|'.join(waypoints)}|{destination}" if waypoints else destination
    params = {"origins": origin, "destinations": dest_query, "mode": "driving", "departure_time": "now", "traffic_model": "best_guess", "key": api_key}
    if avoid_tolls: params["avoid"] = "tolls"
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data["status"] == "OK":
            return data["rows"][0]["elements"][0]["duration_in_traffic"]["value"] // 60
        return 999 
    except: return 999

def get_furka_departure(arrival_time):
    def find_next_train(current_dt):
        wd = current_dt.weekday()
        earliest = current_dt + datetime.timedelta(minutes=10)
        h, m = earliest.hour, earliest.minute
        if h < 6 or (h == 6 and m <= 5): return earliest.replace(hour=6, minute=5, second=0, microsecond=0)
        last_h = 22 if wd >= 4 else 21
        if h > last_h or (h == last_h and m > 5): return None
        if wd >= 4 or wd == 0:
            if m <= 5: dep_m = 5
            elif m <= 35: dep_m = 35
            else: dep_m = 5; h += 1
        else:
            dep_m = 5
            if m > 5: h += 1
        return earliest.replace(hour=h, minute=dep_m, second=0, microsecond=0)
    zug = find_next_train(arrival_time)
    if zug is None: zug = find_next_train((arrival_time + datetime.timedelta(days=1)).replace(hour=0, minute=0))
    return zug

def get_loetschberg_departure(arrival_time):
    def find_next_train_l(current_dt):
        wd = current_dt.weekday()
        earliest = current_dt + datetime.timedelta(minutes=10)
        h, m = earliest.hour, earliest.minute
        if h < 5 or (h == 5 and m <= 25): return earliest.replace(hour=5, minute=25, second=0, microsecond=0)
        if wd <= 3: 
            if h == 21 and m > 43: return earliest.replace(hour=22, minute=48, second=0, microsecond=0)
            if h == 22:
                if m <= 48: return earliest.replace(hour=22, minute=48, second=0, microsecond=0)
                else: return earliest.replace(hour=23, minute=28, second=0, microsecond=0)
            if h == 23:
                if m <= 28: return earliest.replace(hour=23, minute=28, second=0, microsecond=0)
                else: return None
        if wd >= 4:
            if m <= 13: dep_m = 13
            elif m <= 27: dep_m = 27
            elif m <= 43: dep_m = 43
            elif m <= 58: dep_m = 58
            else: dep_m = 13; h += 1
        else:
            if m <= 13: dep_m = 13
            elif m <= 43: dep_m = 43
            else: dep_m = 13; h += 1
        return earliest.replace(hour=h % 24, minute=dep_m, second=0, microsecond=0)
    zug = find_next_train_l(arrival_time)
    if zug is None: zug = find_next_train_l((arrival_time + datetime.timedelta(days=1)).replace(hour=0, minute=0))
    return zug

# --- STATUS-CHECKS MIT ORIGINALEN PROMPTS ---

def get_furka_status():
    url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return True
        feed_text = response.text
        if any(word in feed_text.lower() for word in ["eingestellt", "geschlossen", "unterbrochen", "sperrung", "unterbruch"]):
            prompt = f"""
            Analysiere diesen RSS-Feed der Matterhorn Gotthard Bahn: "{feed_text}"
            
            FRAGE: Ist der AUTOVERLAD (Autozüge) am Furka zwischen Realp und Oberwald aktuell eingestellt oder gesperrt?
            HINWEIS: Meldungen über den Glacier Express, den Regionalverkehr oder andere Linien (z.B. Visp-Zermatt) 
            bedeuten NICHT, dass der Autoverlad am Furka zu ist.
            
            Antworte NUR mit 'GESPERRT' oder 'OFFEN'.
            """
            return "GESPERRT" not in generate_content_with_fallback(prompt).upper()
        return True
    except: return True

def get_loetschberg_status():
    url = "https://www.bls.ch/api/TrafficInformation/GetNewNotifications?sc_lang=de&sc_site=internet-bls"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).json()
        meldungen = " | ".join([n.get("title", "") for n in res.get("trafficInformations", [])])
        if any(x in meldungen.lower() for x in ["unterbrochen", "eingestellt", "sperrung", "unterbruch"]):
            prompt = f"""
            Analysiere diese Verkehrsmeldungen der BLS: "{meldungen}"
            
            FRAGE: Ist der AUTOVERLAD (Autozüge) zwischen Kandersteg und Goppenstein aktuell GESPERRT?
            HINWEIS: Ein Unterbruch des BAHNVERKEHRS (Personenzüge) bedeutet NICHT zwingend, dass der Autoverlad zu ist.
            
            Antworte NUR mit 'GESPERRT' oder 'OFFEN'.
            """
            return "GESPERRT" not in generate_content_with_fallback(prompt).upper()
        return True
    except: return True

def get_pass_status():
    url = "https://www.alpen-paesse.ch/de/alpenpaesse/status.rss"
    status_dict = {"Furkapass": False, "Grimselpass": False, "Nufenenpass": False, "Brünigpass": True}
    try:
        root = ET.fromstring(requests.get(url, timeout=10).content)
        for item in root.findall('.//item'):
            title = item.find('title').text
            for p in status_dict.keys():
                if p in title:
                    if "offen" in title.lower(): status_dict[p] = True
                    elif any(x in title.lower() for x in ["wintersperre", "geschlossen", "gesperrt"]): status_dict[p] = False
    except: pass
    return status_dict

# --- KI REPORTE MIT ORIGINALEN PROMPTS ---

def get_gemini_summer_report(routen_daten, pass_status):
    machbare = {k: v for k, v in routen_daten.items() if v < 9000}
    paesse_offen = any([pass_status.get("Furkapass"), pass_status.get("Grimselpass"), pass_status.get("Nufenenpass")])
    prompt = f"""
        Du bist ein herzlicher, urchiger Schweizer Bergführer im Sommer.
        Analysiere diese Lage für die Fahrt nach Ried-Mörel:
        - Pässe-Status: {pass_status}
        - Fahrzeiten (was noch geht): {machbare}

        STRATEGISCHE ANWEISUNGEN:
        1. FALL BEIDE VERLADE ZU (Furka & Lötschberg): Preise die Pässe (Furka, Grimsel oder Nufenen) als die 'perfekte Ausweichroute' an. Schwärme von der Freiheit auf der Strasse und dem Panorama! 🏔️
        2. FALL ALLES ZU (Verlade UND Pässe): Schlage mit einem Augenzwinkern vor, jetzt den Helikopter zu rufen, da Ried-Mörel sonst nur noch für Adler erreichbar ist. 🚁
        3. FALL NORMALBETRIEB: Wenn ein Pass offen ist und maximal 20 Min länger dauert als der Tunnel, befiehl fast schon den Pass zu nehmen – wegen der Aussicht. ☀️
        4. ZUSATZINFO: Brünigpass-Status nur erwähnen, wenn Lötschberg ein Thema ist.

        TONFALL:
        - Begeistert, herzlich, maximal 4 Sätze.
        - Emojis: 🏔️, ☀️, 🏎️, 🚁, 🧀.
        """
    return generate_content_with_fallback(prompt)

def get_gemini_winter_report(winter_daten):
    f_aktiv = winter_daten.get('furka_aktiv', False)
    l_aktiv = winter_daten.get('loetschberg_aktiv', False)
    prompt = f"""
        Du bist ein humorvoller, aber sehr kompetenter Schweizer Bergführer.
        Analysiere die aktuelle Winter-Verkehrslage nach Ried-Mörel:

        DATEN:
        - Autoverlad Lötschberg: {'AKTIV' if l_aktiv else 'GESPERRT'} (Zeit: {winter_daten.get('total_l')} Min)
        - Autoverlad Furka: {'AKTIV' if f_aktiv else 'GESPERRT'} (Zeit: {winter_daten.get('total_f')} Min)
        - Nächste Abfahrten: Lötschberg {winter_daten.get('abfahrt_l')}, Furka {winter_daten.get('abfahrt_f')}

        AUFGABE:
        1. TOTALAUSFALL: Wenn BEIDE Verladestationen gesperrt sind, rate dem User DRINGEND, zu Hause zu bleiben. 
           Empfiehl eine lustige Indoor-Aktivität (z.B. Käsefondue im Wohnzimmer, "Trocken-Skifahren" auf dem Teppich oder Walliser Weisswein-Degustation im Pyjama).
        2. NUR EINER OFFEN: Erkläre kurz, dass dies aktuell die einzige Verbindung ins Wallis ist.
        3. BEIDE OFFEN: Vergleiche Wartezeiten und Abfahrten, empfiehl die effizienteste Route.
        4. TONFALL: Herzlich, "urchig" schweizerisch, max. 4 Sätze. Nutze Emojis: ❄️, 🧀, 🍷, 🚂.
        """
    return generate_content_with_fallback(prompt)

def get_gemini_situation_report(current_data, df_history):
    trend_summary = ""
    if df_history is not None and not df_history.empty:
        latest_entries = df_history.head(20) 
        trend_summary = latest_entries[['timestamp', 'station', 'minutes']].to_string()

    prompt = f"""
        Du bist ein Experte für Verkehrsfluss beim Schweizer Autoverlad.
        Analysiere die aktuelle Lage und den Trend der letzten Stunden:
        
        AKTUELL: {current_data}
        HISTORIE/TREND: {trend_summary}

        AUFGABE:
        - Erstelle einen kompakten Lagebericht (max. 3-4 Sätze). Der Text soll ohne Überschrift ausgegeben werden.
        - Erwähne, ob die Wartezeiten gerade steigen, fallen oder stabil sind.
        - Fasse die Lage in Richtung Wallis (Realp, Kandersteg) und in Richtung Mittelland (Oberwald, Goppenstein) zusammen.
        - Nutze Sätze wie "am Furka Autoverlad in xxx...", "Auf dem Weg ins Wallis in xxx ...", "Vor dem Autoverlad in xxx..." oder ähnlich.
        - Gib eine kurze Empfehlung (z.B. "Geduld einpacken" oder "Freie Fahrt").
        - Tonalität: Sachlich, hilfsbereit, leicht "schweizerisch" angehaucht.
        - Nutze sparsam Emojis passend zur Lage (🚗, ⏳, ✅, ⚠️).
        """
    return generate_content_with_fallback(prompt)
