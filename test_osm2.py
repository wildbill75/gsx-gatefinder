import urllib.request
import json
query = '[out:json];area["icao"="EGCC"]->.a;nwr(area.a)["aeroway"="parking_position"];out center tags;'
req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
data = json.loads(urllib.request.urlopen(req).read().decode())
print("EGCC OSM gates:", len(data['elements']))
for e in data['elements'][:5]:
    print(e.get('tags', {}).get('ref'))
