import urllib.request
import json
import math
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor

def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in meters
    R = 6371000.0
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c

class OnlineNetworkChecker:
    def __init__(self):
        self.cache_time = 0
        self.cache_duration = 30  # 30 seconds cache
        self.cached_pilots = [] # list of dicts: {"lat": float, "lon": float, "network": str, "callsign": str}
        self._lock = threading.Lock()

    def _fetch_vatsim(self):
        res = []
        try:
            req = urllib.request.Request(
                "https://data.vatsim.net/v3/vatsim-data.json",
                headers={'User-Agent': 'GateFinder-Client'}
            )
            with urllib.request.urlopen(req, timeout=2.5) as response:
                data = json.loads(response.read().decode('utf-8'))
                vatsim_pilots = data.get("pilots", [])
                for p in vatsim_pilots:
                    gs = p.get("groundspeed", 999)
                    lat = p.get("latitude")
                    lon = p.get("longitude")
                    if lat is not None and lon is not None and gs < 10:
                        res.append({
                            "lat": float(lat),
                            "lon": float(lon),
                            "network": "VATSIM",
                            "callsign": p.get("callsign", "Unknown")
                        })
        except Exception as e:
            print(f"Error fetching VATSIM data: {e}")
        return res

    def _fetch_ivao(self):
        res = []
        try:
            req = urllib.request.Request(
                "https://api.ivao.aero/v2/tracker/whazzup",
                headers={'User-Agent': 'GateFinder-Client'}
            )
            with urllib.request.urlopen(req, timeout=2.5) as response:
                data = json.loads(response.read().decode('utf-8'))
                ivao_clients = data.get("clients", {})
                ivao_pilots = ivao_clients.get("pilots", [])
                for p in ivao_pilots:
                    last_track = p.get("lastTrack")
                    if last_track:
                        gs = last_track.get("groundSpeed", 999)
                        lat = last_track.get("latitude")
                        lon = last_track.get("longitude")
                        if lat is not None and lon is not None and gs < 10:
                            res.append({
                                "lat": float(lat),
                                "lon": float(lon),
                                "network": "IVAO",
                                "callsign": p.get("callsign", "Unknown")
                            })
        except Exception as e:
            print(f"Error fetching IVAO data: {e}")
        return res

    def is_pilot_self(self, pilot, user_lat=None, user_lon=None, user_callsign=None):
        """
        Returns True if `pilot` from the VATSIM/IVAO feed represents the user's own aircraft
        (matching callsign or parked within 38m of the user's live SimConnect GPS position).
        """
        if not pilot or not isinstance(pilot, dict):
            return False
        if user_callsign:
            u_cs = re.sub(r'[^A-Z0-9]', '', str(user_callsign).upper())
            p_cs = re.sub(r'[^A-Z0-9]', '', str(pilot.get("callsign") or "").upper())
            if u_cs and p_cs and u_cs == p_cs:
                return True
        if user_lat is not None and user_lon is not None:
            p_lat = pilot.get("lat")
            p_lon = pilot.get("lon")
            if p_lat is not None and p_lon is not None:
                try:
                    if haversine(float(user_lat), float(user_lon), float(p_lat), float(p_lon)) < 38.0:
                        return True
                except Exception:
                    pass
        return False

    def fetch_data(self, force=False):
        now = time.time()
        if not force and (now - self.cache_time < self.cache_duration):
            return self.cached_pilots
            
        with self._lock:
            now = time.time()
            if not force and (now - self.cache_time < self.cache_duration):
                return self.cached_pilots

            pilots = []
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_vat = ex.submit(self._fetch_vatsim)
                f_iva = ex.submit(self._fetch_ivao)
                pilots.extend(f_vat.result())
                pilots.extend(f_iva.result())
                
            self.cached_pilots = pilots
            self.cache_time = time.time()
            return pilots
