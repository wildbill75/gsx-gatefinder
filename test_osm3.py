import urllib.request
import json
query = """[out:json];
area["icao"="EGCC"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""
req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
try:
    data = json.loads(urllib.request.urlopen(req).read().decode())
    elements = data.get('elements', [])
    print("EGCC OSM gates:", len(elements))
    for e in elements[:10]:
        print(e.get('tags'))
except Exception as e:
    print("Error:", e)
