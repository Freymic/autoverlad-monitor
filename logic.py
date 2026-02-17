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

def init_db():
    """Initialisiert die Datenbank-Tabelle und stellt Daten aus GSheets wieder her, falls DB leer."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    
    # Check ob DB leer ist (z.B. nach Reboot auf Streamlit Cloud)
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        restore_from_gsheets(conn)
        
    conn.close()

def restore_from_gsheets(sqlite_conn):
    """Lädt die letzten 24h aus Google Sheets zurück in die lokale SQLite."""
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
    """Lückenloses Mapping von Text-Phrasen zu Minutenwerten bis 4h."""
    if not time_str:
        return 0
    
    text = time_str.lower()
    
    # 1. ERWEITERTES MAPPING
    mapping = {
        "4 stunden": 240,
        "3 stunden 30 minuten": 210,
        "3 stunden": 180,
        "2 stunden 30 minuten": 150,
        "2 stunden": 120,
        "1 stunde 30 minuten": 90,
        "1 stunde": 60,
        "45 minuten": 45,
        "30 minuten": 30,
        "15 minuten": 15,
        "keine wartezeit": 0,
        "no waiting": 0
    }
    
    for phrase, minutes in mapping.items():
        if phrase in text:
            return minutes

    # 2. DYNAMISCHER RECHNER (Fallback)
    total_min = 0
    hour_match = re.search(r'(\d+)\s*stunde', text)
    if hour_match:
        total_min += int(hour_match.group(1)) * 60
    
    min_match = re.search(r'(?<!:)(\b\d+)\s*(?:min|minute)', text)
    if min_match:
        total_min += int(min_match.group(1))
        
    return total_min

def fetch_all_data():
    """Holt Daten von Lötschberg (API) und Furka (RSS)."""
    results = {}
    
    # --- TEIL 1: LÖTSCHBERG (Kandersteg & Goppenstein) ---
    try:
        l_url = "https://www.bls.ch/api/avwV2/delays?dataSourceId={808904A8-0874-44AC-8DE3-4A5FC33D8CF1}"
        l_res = requests.get(l_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).json()
        
        for s in l_res.get("Stations", []):
            name = s.get("Station")
            if name in ["Kandersteg", "Goppenstein"]:
                msg = s.get("DelayMessage", "")
                results[name] = {
                    "min": parse_time_to_minutes(msg), 
                    "raw": msg if msg else "Keine Wartezeit"
                }
    except Exception as e:
        print(f"Fehler Lötschberg: {e}")

    # --- TEIL 2: FURKA (Oberwald & Realp) ---
    try:
        f_url = "https://mgb-prod.oevfahrplan.ch/incident-manager-api/incidentmanager/rss?publicId=av_furka&lang=de"
        f_resp = requests.get(f_url, timeout=10)
        root = ET.fromstring(f_resp.content)
        
        furka_found = {"Oberwald": False, "Realp": False}
        
        for item in root.findall('.//item'):
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            full_text = f"{title} {desc}"
            
            if any(x in full_text.lower() for x in ["stündlich", "abfahrt"]):
                continue
            
            if "wartezeit" in full_text.lower():
                val = parse_time_to_minutes(full_text)
                if "Oberwald" in full_text and not furka_found["Oberwald"]:
                    results["Oberwald"] = {"min": val, "raw": full_text}
                    furka_found["Oberwald"] = True
                elif "Realp" in full_text and not furka_found["Realp"]:
                    results["Realp"] = {"min": val, "raw": full_text}
                    furka_found["Realp"] = True
        
        if not furka_found["Oberwald"]: results["Oberwald"] = {"min": 0, "raw": "Keine Meldung"}
        if not furka_found["Realp"]: results["Realp"] = {"min": 0, "raw": "Keine Meldung"}
            
    except Exception as e:
        print(f"Fehler Furka: {e}")
    
    return results

def save_to_db(data):
    """Speichert Daten exakt im 5-Minuten-Takt in die SQLite DB."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        now = datetime.datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        quantized_now = now.replace(minute=minute_quantized, second=0, microsecond=0)
        timestamp_str = quantized_now.strftime('%Y-%m-%d %H:%M:%S')
        
        for station, info in data.items():
            c.execute("SELECT 1 FROM stats WHERE timestamp = ? AND station = ?", (timestamp_str, station))
            if not c.fetchone():
                c.execute("INSERT INTO stats VALUES (?, ?, ?, ?)",
                          (timestamp_str, station, info.get('min', 0), info.get('raw', '')))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def save_to_google_sheets(data):
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Development")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        
        # 1. Zeitstempel vorbereiten
        now = datetime.datetime.now(CH_TZ)
        minute_quantized = (now.minute // 5) * 5
        ts_str = now.replace(minute=minute_quantized, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        # 2. Neue Daten in DataFrame umwandeln
        new_entries = []
        for station, info in data.items():
            new_entries.append({
                "timestamp": ts_str,
                "station": station,
                "minutes": info.get('min', 0),
                "raw_text": info.get('raw', '')
            })
        df_new = pd.DataFrame(new_entries)
        
        # 3. Bestehende Daten laden (Cache umgehen mit ttl=0)
        try:
            # ttl=0 stellt sicher, dass wir wirklich den aktuellen Stand vom Server holen
            df_existing = conn_gs.read(worksheet=sheet_name, ttl=0)
        except Exception:
            df_existing = pd.DataFrame(columns=["timestamp", "station", "minutes", "raw_text"])
        
        # 4. Anhängen und Index zurücksetzen
        # ignore_index=True ist extrem wichtig, damit Google nicht denkt, es sei die gleiche Zeile
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
        
        # 5. Duplikate entfernen (Zeitpunkt + Station)
        df_final = df_final.drop_duplicates(subset=['timestamp', 'station'], keep='last')
        
        # 6. Das komplette Sheet aktualisieren
        conn_gs.update(worksheet=sheet_name, data=df_final)
        
        # Kleiner Debug-Hinweis für dich (kannst du später löschen)
        # st.toast(f"Cloud-Sync: {len(df_final)} Zeilen gesamt")
        
        return True
        
    except Exception as e:
        st.error(f"GSheets Sync Fehler: {e}")
        return False

def get_latest_wait_times(station):
    # Holt den aktuellsten Wert für eine Station aus der SQLite DB
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(
            "SELECT minutes FROM stats WHERE station = ? ORDER BY timestamp DESC LIMIT 1", 
            conn, params=(station,)
        )
    return int(df['minutes'].iloc[0]) if not df.empty else 0

def get_google_maps_duration(origin, destination, waypoints=None, avoid_tolls=False):
    """
    Holt die Fahrzeit von Google Maps. Unterstützt Wegpunkte und Maut-Optionen.
    """
    api_key = st.secrets["G_MAPS_API_KEY"]
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    # Wegpunkte für Passrouten formatieren
    dest_query = f"{'|'.join(waypoints)}|{destination}" if waypoints else destination

    params = {
        "origins": origin,
        "destinations": dest_query,
        "mode": "driving",
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key
    }
    
    # Füge Maut-Vermeidung hinzu, falls gewünscht
    if avoid_tolls:
        params["avoid"] = "tolls"
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data["status"] == "OK":
            seconds = data["rows"][0]["elements"][0]["duration_in_traffic"]["value"]
            return seconds // 60
        return 999 
    except Exception:
        return 999


def get_furka_departure(arrival_time):
    """Berechnet die nächste Abfahrt ab Realp laut offiziellem Fahrplan."""
    
    def find_next_train(current_dt):
        wd = current_dt.weekday() # 0=Mo, 4=Fr, 6=So
        # 10 Min Puffer für Ticket/Verlad
        earliest = current_dt + datetime.timedelta(minutes=10)
        h, m = earliest.hour, earliest.minute

        # 1. Betriebszeiten definieren
        first_h, first_m = 6, 5
        if wd >= 4: last_h, last_m = 22, 5    # Fr-So bis 22:05
        elif wd == 0: last_h, last_m = 21, 5  # Mo bis 21:05
        else: last_h, last_m = 21, 5         # Di-Do bis 21:05 (aber Stundentakt)

        # 2. Check: Ist es vor dem ersten Zug?
        if h < first_h or (h == first_h and m <= first_m):
            return earliest.replace(hour=6, minute=5, second=0, microsecond=0)

        # 3. Check: Ist es nach dem letzten Zug?
        if h > last_h or (h == last_h and m > last_m):
            return None

        # 4. Takt-Berechnung
        if wd >= 4 or wd == 0: # Mo, Fr-So: 30-Min-Takt (.05 / .35)
            if m <= 5: dep_m = 5
            elif m <= 35: dep_m = 35
            else:
                dep_m = 5
                h += 1
        else: # Di-Do: 60-Min-Takt (.05)
            dep_m = 5
            if m > 5: h += 1
            
        return earliest.replace(hour=h, minute=dep_m, second=0, microsecond=0)

    # Versuch für heute
    zug = find_next_train(arrival_time)
    
    # Wenn heute keiner mehr: Erster Zug morgen früh 06:05
    if zug is None:
        morgen = (arrival_time + datetime.timedelta(days=1)).replace(hour=0, minute=0)
        zug = find_next_train(morgen)
        
    return zug

def get_loetschberg_departure(arrival_time):
    """Berechnet die nächste Abfahrt ab Kandersteg (Mo-So)."""
    
    def find_next_train_l(current_dt):
        wd = current_dt.weekday() # 0=Mo, 4=Fr, 5=Sa, 6=So
        # 10 Min Puffer für Ticket/Verlad
        earliest = current_dt + datetime.timedelta(minutes=10)
        h, m = earliest.hour, earliest.minute

        # 1. Erste Abfahrt am Morgen (05:25)
        if h < 5 or (h == 5 and m <= 25):
            return earliest.replace(hour=5, minute=25, second=0, microsecond=0)

        # 2. Spätverkehr (Mo-Do) laut deiner Liste
        if wd <= 3: 
            if h == 21 and m > 43:
                return earliest.replace(hour=22, minute=48, second=0, microsecond=0)
            if h == 22:
                if m <= 48: return earliest.replace(hour=22, minute=48, second=0, microsecond=0)
                else: return earliest.replace(hour=23, minute=28, second=0, microsecond=0)
            if h == 23:
                if m <= 28: return earliest.replace(hour=23, minute=28, second=0, microsecond=0)
                else: return None

        # 3. Takt-Logik (Fr-So: 15-Min / Mo-Do: 30-Min)
        # Freitag (4), Samstag (5), Sonntag (6)
        if wd >= 4:
            # Deine Screenshots zeigen: .13, .27, .43, .58
            if m <= 13: dep_m = 13
            elif m <= 27: dep_m = 27
            elif m <= 43: dep_m = 43
            elif m <= 58: dep_m = 58
            else:
                dep_m = 13
                h += 1
        else:
            # Montag bis Donnerstag: .13, .43
            if m <= 13: dep_m = 13
            elif m <= 43: dep_m = 43
            else:
                dep_m = 13
                h += 1
            
        return earliest.replace(hour=h % 24, minute=dep_m, second=0, microsecond=0)

    # Versuch für heute
    zug = find_next_train_l(arrival_time)
    
    # Falls heute keiner mehr: Erster Zug morgen
    if zug is None:
        morgen = (arrival_time + datetime.timedelta(days=1)).replace(hour=0, minute=0)
        zug = find_next_train_l(morgen)
        
    return zug

def get_furka_status():
    """
    Prüft den RSS-Feed auf Sperrungen.
    Gibt True zurück, wenn offen, und False, wenn eingestellt.
    """
    # Hier kommt dein RSS-Parsing Code hin (z.B. mit feedparser)
    # Beispiel-Logik:
    feed_text = "Der Autoverlad Furka ist zur Zeit eingestellt" # Das käme vom Feed
    
    status_keywords = ["eingestellt", "geschlossen", "unterbrochen", "Sperrung"]
    
    for word in status_keywords:
        if word.lower() in feed_text.lower():
            return False # Betrieb eingestellt
            
    return True # Betrieb scheint okay

def get_loetschberg_status():
    """
    Prüft die BLS API auf aktuelle Verkehrsmeldungen zum Autoverlad Lötschberg.
    Gibt True zurück, wenn der Betrieb läuft, und False bei Unterbruch.
    """
    url = "https://www.bls.ch/api/TrafficInformation/GetNewNotifications?sc_lang=de&sc_site=internet-bls"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            notifications = response.json()
            
            # Relevante Begriffe für einen Unterbruch
            alarm_keywords = ["eingestellt", "unterbrochen", "Sperrung", "Unterbruch", "keine Verlademöglichkeit"]
            
            for note in notifications:
                text = note.get("Description", "").lower()
                title = note.get("Title", "").lower()
                
                # Wir prüfen, ob die Meldung den Autoverlad Lötschberg betrifft
                if "kandersteg" in text or "goppenstein" in text or "autoverlad" in text:
                    for word in alarm_keywords:
                        if word.lower() in text or word.lower() in title:
                            # Sicherheitshalber prüfen wir, ob es nicht nur eine harmlose Info ist
                            # (z.B. "Unterbruch aufgehoben")
                            if "aufgehoben" not in text:
                                return False # Betrieb gestört
        
        return True # Alles okay oder keine Meldung gefunden
    except Exception as e:
        print(f"Fehler beim BLS-Status-Check: {e}")
        return True # Im Zweifelsfall True, damit die App nicht blockiert

def get_pass_status():
    """
    Fragt den Status der Alpenpässe via alpen-paesse.ch RSS ab.
    Gibt ein Dictionary zurück: {Name: True/False}
    """
    url = "https://www.alpen-paesse.ch/de/alpenpaesse/status.rss"
    # Standardwerte (Brünig meist offen, andere Wintersperre)
    status_dict = {
        "Furkapass": False,
        "Grimselpass": False,
        "Nufenenpass": False,
        "Brünigpass": True 
    }
    
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        
        for item in root.findall('.//item'):
            title_element = item.find('title')
            if title_element is None: continue
            
            title = title_element.text
            for p_name in status_dict.keys():
                if p_name in title:
                    # Logik: Wenn 'offen' im Text steht -> True, sonst False
                    if "offen" in title.lower():
                        status_dict[p_name] = True
                    elif any(x in title.lower() for x in ["wintersperre", "geschlossen", "gesperrt"]):
                        status_dict[p_name] = False
    except Exception as e:
        print(f"Fehler beim Pass-Status-Check: {e}")
    
    return status_dict


def get_gemini_summer_report(routen_daten, pass_status):

    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Dynamische Modellsuche (deine funktionierende Logik)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selected_model = next((n for n in available_models if 'gemini-1.5-flash' in n), available_models[0])
        model = genai.GenerativeModel(selected_model)
        
        machbare = {k: v for k, v in routen_daten.items() if v < 9000}
        
        prompt = f"""
        Du bist ein begeisterter Schweizer Bergführer im Sommer. 
        Analysiere diese Routen nach Ried-Mörel:
        Pässe-Status: {pass_status}
        Fahrzeiten: {machbare}

        Regeln für deine Antwort:
        1. Wenn Furka- oder Grimselpass OFFEN sind, schwärme kurz von der Aussicht 🏔️.
        2. Wenn ein Pass nur maximal 20 Min länger dauert als der Autoverlad, empfiehl UNBEDINGT den Pass.
        3. Erwähne den Autoverlad nur als "Notlösung" für Eilige.
        4. Die Info über den genöffneten Zustand des Brünigpasses soll nur als Zusatzinfo für den Weg durch den Autoverlad Lötschberg erwähnt werden.
        5. Sei herzlich, nutze Schweizer Emojis (☀️, 🏎️, 🏔️) und fasse dich in 3-4 Sätzen kurz.
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"🤖 Sommer-KI hat gerade Sonnenstich... ({e})"


def get_gemini_winter_report(winter_daten):
    import google.generativeai as genai
    import streamlit as st

    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Dynamische Modellsuche (deine bewährte Logik)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selected_model = next((n for n in available_models if 'gemini-1.5-flash' in n), available_models[0])
        model = genai.GenerativeModel(selected_model)
        
        # Status-Checks für den Prompt vorbereiten
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

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"🤖 Der Winter-Guide hat gerade kalte Füsse bekommen... (Fehler: {e})"
