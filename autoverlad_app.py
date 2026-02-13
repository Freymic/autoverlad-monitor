import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Furka Live-Schnittstelle", page_icon="🏔️")

def fetch_mgb_graphql():
    url = "https://www.matterhorngotthardbahn.ch/graphql"
    
    # Diese Header basieren exakt auf deinem Browser-Scan
    headers = {
        "Content-Type": "application/json",
        "x-ada-client-type": "JAMES-Web",
        "Origin": "https://www.matterhorngotthardbahn.ch",
        "Referer": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15"
    }

    # Wir probieren eine Standard-Abfrage für Wartezeiten in diesem System
    query = """
    query getWartezeiten {
      autoverladStatus {
        items {
          station
          waitingTime
        }
      }
    }
    """
    
    try:
        response = requests.post(url, json={'query': query}, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status {response.status_code}", "body": response.text}
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
st.title("🛰️ Furka Schnittstellen-Tester")

if st.button("📡 Daten von MGB abrufen"):
    with st.spinner("Frage GraphQL-Server an..."):
        daten = fetch_mgb_graphql()
        
        if "data" in daten and daten["data"]:
            st.success("Verbindung erfolgreich!")
            st.json(daten)
        else:
            st.error("Schnittstelle verbunden, aber keine Daten unter dieser Abfrage.")
            st.info("Wir müssen die exakte 'Query' aus deinem Netzwerk-Tab finden.")
            with st.expander("Antwort vom Server"):
                st.write(daten)

st.divider()
st.markdown("""
### Nächster Schritt für dich:
Schau im Browser noch einmal in den **Network-Tab** bei den `graphql`-Einträgen. 
Klicke auf den Reiter **'Anfrage'** (Payload) und kopiere mir den Inhalt von **'Anfragedaten'**. 
Das sieht meistens so aus: `{"query":"query ...", "variables":{...}}`.
""")
