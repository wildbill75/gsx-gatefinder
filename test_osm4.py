import urllib.request
import json
def fetch_osm_gates(icao):
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        area["icao"="{icao}"]->.a;
        node(area.a)["aeroway"="parking_position"];
        out tags;
        """
        print(query)
        req = urllib.request.Request(overpass_url, data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
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

print("EGCC:", fetch_osm_gates("EGCC"))
print("LDDU:", fetch_osm_gates("LDDU"))
print("KPBI:", fetch_osm_gates("KPBI"))
