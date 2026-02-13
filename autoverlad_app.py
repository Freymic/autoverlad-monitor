import streamlit as st
import requests
import json

st.title("🕵️ MGB Daten-Detektiv")

def get_raw_graphql_dump():
    url = "https://www.matterhorngotthardbahn.ch/graphql"
    
    # Wir nutzen deine exakten Header
    headers = {
        "Content-Type": "application/json",
        "x-ada-client-type": "JAMES-Web",
        "Origin": "https://www.matterhorngotthardbahn.ch",
        "Referer": "https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }

    # Wir fragen nach dem kompletten 'route' Objekt der Seite. 
    # Das ist der "große Topf", in dem alles drinstecken muss.
    query = """
    query GetPageContent {
      route(path: "/de/stories/autoverlad-furka-wartezeiten") {
        ... on Story {
          id
          name
          content {
            __typename
            ... on ContentGrid {
              items {
                __typename
                ... on ContentText { text }
              }
            }
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(url, json={'query': query}, headers=headers, timeout=15)
        return response.status_code, response.json()
    except Exception as e:
        return 0, {"error": str(e)}

status_code, datensalat = get_raw_graphql_dump()

st.write(f"Server-Status: {status_code}")

if status_code == 200:
    st.subheader("Der komplette Datensalat (JSON):")
    st.json(datensalat)
    
    # Zusätzliche Textsuche für dich
    raw_text = json.dumps(datensalat)
    st.divider()
    st.subheader("Schnell-Scan Ergebnisse:")
    if "Oberwald" in raw_text:
        st.success("Gefunden: 'Oberwald' ist im Datensalat enthalten!")
    else:
        st.error("'Oberwald' wurde nicht im Datensalat gefunden. Der Server liefert uns nur das Grundgerüst.")
else:
    st.error("Konnte keine Verbindung zum GraphQL-Server herstellen.")
