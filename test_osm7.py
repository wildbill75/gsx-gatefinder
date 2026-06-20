import urllib.request
import json
query = """[out:json];
area["icao"="EGCC"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""
try:
    req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
    print(len(json.loads(urllib.request.urlopen(req).read().decode())['elements']))
except Exception as e:
    print("Without timeout:", e)

query2 = """[out:json][timeout:10];
area["icao"="EGCC"]->.a;
nwr(area.a)["aeroway"="parking_position"];
out center tags;"""
try:
    req2 = urllib.request.Request('https://overpass-api.de/api/interpreter', data=query2.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
    print(len(json.loads(urllib.request.urlopen(req2).read().decode())['elements']))
except Exception as e:
    print("With timeout:", e)
