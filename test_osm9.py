import urllib.request
import json
import time

icao = "EGCC"
query = f"""[out:json][timeout:30];
area["icao"="{icao}"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""

try:
    print(f"Fetching gates for {icao}...")
    start = time.time()
    req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'), headers={'User-Agent': 'GateFinder/1.0'})
    with urllib.request.urlopen(req, timeout=40) as response:
        osm_data = json.loads(response.read().decode())
    print(f"Found elements: {len(osm_data.get('elements', []))}")
    print(f"Time: {time.time() - start:.2f}s")
except Exception as e:
    print(f"Error: {e}")
