import urllib.request
import json
icao = "LDDU"
query = f"""
            [out:json][timeout:10];
            area["icao"="{icao}"]->.a;
            nwr(area.a)["aeroway"="parking_position"];
            out center tags;
            """.strip()

try:
    req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
    print("Test Strip:", len(json.loads(urllib.request.urlopen(req).read().decode())['elements']))
except Exception as e:
    print("Error:", e)
