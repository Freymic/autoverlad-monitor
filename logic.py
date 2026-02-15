import requests
import xml.etree.ElementTree as ET
import re
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import pytz
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Konstanten
DB_NAME = 'autoverlad.db'
CH_TZ = pytz.timezone('Europe/Zurich')

def init_db():
    """
    Initialisiert die lokale SQLite-Datenbank. 
    Falls die DB leer ist (z.B. nach einem App-Reboot), 
    werden die Daten aus Google Sheets wiederhergestellt.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (timestamp DATETIME, station TEXT, minutes INTEGER, raw_text TEXT)''')
    conn.commit()
    
    # Prüfen, ob lokale Daten vorhanden sind
    c.execute("SELECT COUNT(*) FROM stats")
    if c.fetchone()[0] == 0:
        restore_from_gsheets(conn)
    
    conn.close()

def restore_from_gsheets(sqlite_conn):
    """Lädt die letzten 24h aus dem konfigurierten GSheet-Tab in die SQLite DB."""
    try:
        sheet_name = st.secrets.get("connections", {}).get("gsheets", {}).get("worksheet", "Sheet1")
        conn_gs = st.connection("gsheets", type=GSheetsConnection)
        
        df = conn_gs.read(worksheet=sheet_name)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Nur Daten der letzten 24h importieren, um die lokale DB schlank zu halten
            cutoff = datetime.now() - timedelta(hours=24)
            df_recent = df[df['timestamp'] > cutoff]
            
            if not df_recent.empty:
                df_recent.to_sql('stats', sqlite_conn, if_exists='append', index=False)
                st.info(f"🔄 {len(df_recent)} Eint
