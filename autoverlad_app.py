def fetch_wartezeiten():
    daten = {"Realp": 0, "Oberwald": 0, "Kandersteg": 0, "Goppenstein": 0}
    try:
        # --- FURKA (MGB) ---
        r_f = requests.get("https://www.matterhorngotthardbahn.ch/de/stories/autoverlad-furka-wartezeiten", timeout=15)
        text_f = BeautifulSoup(r_f.content, 'html.parser').get_text(separator=' ')
        
        # Wir säubern den Text: Alles vor 'Verkehrsinformation' und nach 'aktualisiert' weg
        if "Verkehrsinformation" in text_f:
            text_f = text_f.split("Verkehrsinformation")[-1]
        if "aktualisiert" in text_f:
            text_f = text_f.split("aktualisiert")[0]
            
        # Bereinigung von überflüssigen Leerzeichen
        text_f = " ".join(text_f.split())
        
        for station in ["Realp", "Oberwald"]:
            # Suche 500 Zeichen nach dem Stationsnamen
            match = re.search(f"{station}(.{{0,500}})", text_f, re.IGNORECASE)
            if match:
                kontext = match.group(1)
                # Wenn 'keine' im Kontext steht, bleibt es bei 0
                if "keine" in kontext.lower():
                    daten[station] = 0
                else:
                    daten[station] = parse_time_string(kontext)

        # --- LÖTSCHBERG (BLS) ---
        r_l = requests.get("https://www.bls.ch/de/fahren/autoverlad/fahrplan", timeout=15)
        text_l = BeautifulSoup(r_l.content, 'html.parser').get_text(separator=' ')
        for station in ["Kandersteg", "Goppenstein"]:
            match = re.search(f"{station}(.{{0,400}})", text_l, re.IGNORECASE)
            if match:
                daten[station] = parse_time_string(match.group(1))
    except:
        pass
    return daten
