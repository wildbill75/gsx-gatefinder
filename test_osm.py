import urllib.request
import json
query = '[out:json];area["icao"="EGCC"]->.a;node(area.a)["aeroway"="parking_position"];out tags;'
req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'))
data = json.loads(urllib.request.urlopen(req).read().decode())
print("EGCC OSM gates:", len(data['elements']))

query2 = '[out:json];area["icao"="LDDU"]->.a;node(area.a)["aeroway"="parking_position"];out tags;'
req2 = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query2.encode('utf-8'))
data2 = json.loads(urllib.request.urlopen(req2).read().decode())
print("LDDU OSM gates:", len(data2['elements']))
