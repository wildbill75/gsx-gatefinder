import urllib.request
import json
import time

def fetch_osm_gates(icao):
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""[out:json][timeout:10];
area["icao"="{icao}"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""
        data = query.encode('utf-8')
        req = urllib.request.Request(overpass_url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=10) as response:
            osm_data = json.loads(response.read().decode())
        t1 = time.time()
        gates = []
        for element in osm_data.get('elements', []):
            tags = element.get('tags', {})
            ref = tags.get('ref')
            if ref: gates.append(ref)
        print(f"{icao} OK: {len(gates)} gates in {t1-t0:.2f}s")
        return gates
    except Exception as e:
        print(f"{icao} Exception:", type(e), e)
        return []

fetch_osm_gates("EGCC")
fetch_osm_gates("LDDU")
fetch_osm_gates("LDSP")
