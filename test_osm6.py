import urllib.request
import urllib.parse
import json
def fetch_osm_gates(icao):
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""[out:json][timeout:10];
area["icao"="{icao}"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""
        data = urllib.parse.urlencode({'data': query}).encode('utf-8')
        req = urllib.request.Request(overpass_url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            osm_data = json.loads(response.read().decode())
        gates = []
        for element in osm_data.get('elements', []):
            tags = element.get('tags', {})
            ref = tags.get('ref')
            if ref: gates.append(ref)
        return sorted(list(set(gates)))
    except Exception as e:
        print("Exception:", e)
        return []

print("EGCC:", len(fetch_osm_gates("EGCC")))
