import os
import re
import json
import math
import time
import heapq
import ssl
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed


def haversine_m(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def bearing_deg(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def angle_diff_deg(a, b):
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def point_to_segment_projection(plat, plon, alat, alon, blat, blon):
    """Returns (proj_lat, proj_lon, t, dist_m) of point P onto segment AB."""
    cos_lat = math.cos(math.radians(plat))
    px, py = plon * cos_lat, plat
    ax, ay = alon * cos_lat, alat
    bx, by = blon * cos_lat, blat
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-16:
        return alat, alon, 0.0, haversine_m(plat, plon, alat, alon)
    t = ((px - ax) * dx + (py - ay) * dy) / len_sq
    t = max(0.0, min(1.0, t))
    proj_lat = alat + t * (blat - alat)
    proj_lon = alon + t * (blon - alon)
    dist = haversine_m(plat, plon, proj_lat, proj_lon)
    return proj_lat, proj_lon, t, dist


class TaxiRouter:
    """
    Fetches & caches geo-referenced airport vector geometry (Runways, Taxiways, Aprons,
    Terminals, Holding Points, Stands) for Lido-Styled Vector Chart rendering, and
    computes optimal A* ground taxi routes with live SimConnect runway exit detection.
    """

    def __init__(self, cache_dir=None, defer_load=False):
        self.memory_cache = {}
        self.graph_cache = {}
        self.locked_arrival_exit = {}  # {icao: exit_ref} when aircraft vacates runway
        self.arr_vacated_runway = {}   # {icao: bool} latched once aircraft vacates landing runway (ignores subsequent runway crossings)
        self.dep_runway_entered = {}   # {icao: rwy_ref} latched when aircraft lines up on active departure runway
        self._failed_overpass_ts = {}  # {icao: timestamp} cooldown to avoid re-querying Overpass 3x on timeout
        self._fetch_lock = threading.Lock()
        self._cache_load_lock = threading.Lock()
        self._disk_cache_loaded = False
        self._icao_locks = {}
        self._mirror_idx = 0
        if cache_dir is None:
            import sys
            if getattr(sys, 'frozen', False):
                cache_dir = os.path.dirname(sys.executable)
            else:
                cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        self.cache_file = os.path.join(cache_dir, "taxi_charts_cache.json")
        if not defer_load:
            self.ensure_disk_cache_loaded()

    def ensure_disk_cache_loaded(self):
        if self._disk_cache_loaded:
            return
        with self._cache_load_lock:
            if self._disk_cache_loaded:
                return
            self._load_disk_cache()
            self._disk_cache_loaded = True

    def _sanitize_chart_geometry(self, chart):
        """
        Repairs any cached chart geometry where sub-tile splitting in dense urban areas
        (e.g. KLAX) caused duplicate OSM ways or folded/palindrome runway polylines.
        Returns True if any modification was made.
        """
        if not isinstance(chart, dict):
            return False
        modified = False
        all_lats = []
        all_lons = []

        # 1. Unfold any palindrome / hairpin-folded runway polylines and recompute ends
        rwys = chart.get("runways") or []
        clean_rwys = []
        seen_rwy_keys = set()
        for rwy in rwys:
            pts = list(rwy.get("points") or [])
            ref = str(rwy.get("ref") or "").strip()
            if len(pts) < 2:
                continue
            # Detect if the polyline folds back on itself (>90 deg turn or pts[0] == pts[-1])
            has_fold = (pts[0] == pts[-1])
            if not has_fold and len(pts) >= 3:
                for k in range(len(pts) - 2):
                    if pts[k] == pts[k + 1] or pts[k + 1] == pts[k + 2]:
                        continue
                    b_in = bearing_deg(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1])
                    b_out = bearing_deg(pts[k + 1][0], pts[k + 1][1], pts[k + 2][0], pts[k + 2][1])
                    if angle_diff_deg(b_in, b_out) > 90.0:
                        has_fold = True
                        break
            if has_fold:
                # Truncate at the apex point furthest from pts[0]
                apex_idx = max(
                    range(len(pts)),
                    key=lambda idx: haversine_m(pts[0][0], pts[0][1], pts[idx][0], pts[idx][1])
                )
                if apex_idx >= 1 and apex_idx < len(pts) - 1:
                    pts = pts[:apex_idx + 1]
                    rwy["points"] = pts
                    length_m = sum(
                        haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                        for i in range(len(pts) - 1)
                    )
                    rwy["length_m"] = round(length_m, 1)
                    rwy["ends"] = self._compute_runway_ends(ref, pts)
                    modified = True

            # Ensure ends always match the outer endpoints of pts
            ends = rwy.get("ends") or {}
            expected_ends = self._compute_runway_ends(ref, pts)
            if ends != expected_ends:
                rwy["ends"] = expected_ends
                modified = True

            pts_tuple = tuple((round(p[0], 6), round(p[1], 6)) for p in pts)
            rev_tuple = tuple(reversed(pts_tuple))
            r_key = (ref, min(pts_tuple, rev_tuple))
            if r_key in seen_rwy_keys:
                modified = True
                continue
            seen_rwy_keys.add(r_key)
            clean_rwys.append(rwy)
            for p in pts:
                all_lats.append(p[0])
                all_lons.append(p[1])

        if len(clean_rwys) != len(rwys):
            chart["runways"] = clean_rwys
            modified = True

        # 2. Deduplicate taxiways if sub-tile split produced duplicate ways
        tws = chart.get("taxiways") or []
        if tws:
            clean_tws = []
            seen_tw = set()
            for tw in tws:
                tpts = tw.get("points") or []
                tkey = (tw.get("ref", ""), tw.get("type", ""), tuple((round(p[0], 6), round(p[1], 6)) for p in tpts))
                if tkey in seen_tw:
                    modified = True
                    continue
                seen_tw.add(tkey)
                clean_tws.append(tw)
                for p in tpts:
                    all_lats.append(p[0])
                    all_lons.append(p[1])
            if len(clean_tws) != len(tws):
                chart["taxiways"] = clean_tws

        if modified and all_lats and all_lons:
            min_lat, max_lat = min(all_lats), max(all_lats)
            min_lon, max_lon = min(all_lons), max(all_lons)
            chart["center_lat"] = round((min_lat + max_lat) / 2.0, 6)
            chart["center_lon"] = round((min_lon + max_lon) / 2.0, 6)
            chart["bbox"] = [round(min_lat, 6), round(min_lon, 6), round(max_lat, 6), round(max_lon, 6)]
            rwy_ids = []
            for rwy in sorted(chart.get("runways", []), key=lambda r: -r.get("length_m", 0)):
                for end_id in rwy.get("ends", {}).keys():
                    if end_id not in rwy_ids:
                        rwy_ids.append(end_id)
            chart["available_runways"] = rwy_ids

        return modified

    def _load_disk_cache(self):
        any_repaired = False
        seen_paths = set()
        for cf in (os.path.join(os.getcwd(), "taxi_charts_cache.json"), self.cache_file):
            if cf and os.path.exists(cf):
                norm_cf = os.path.normcase(os.path.abspath(cf))
                if norm_cf in seen_paths:
                    continue
                seen_paths.add(norm_cf)
                try:
                    with open(cf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            for k, v in data.items():
                                if isinstance(v, dict) and (v.get("runways") or v.get("taxiways")):
                                    if self._sanitize_chart_geometry(v):
                                        any_repaired = True
                                    self.memory_cache[k] = v
                except Exception:
                    pass
        if any_repaired:
            self._save_disk_cache()

    def _save_disk_cache(self):
        try:
            # Keep up to 500 valid airports in disk cache so user airports are never evicted
            valid_keys = [
                k for k, v in self.memory_cache.items()
                if isinstance(v, dict) and (v.get("runways") or v.get("taxiways"))
            ][-500:]
            subset = {k: self.memory_cache[k] for k in valid_keys}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(subset, f)
        except Exception:
            pass

    @staticmethod
    def _canon_stand_ref(raw_ref):
        s = re.sub(r'[\s_\-]+', '', str(raw_ref or '').upper())
        for p in ("GATE", "STAND", "PARKING", "RAMP", "DOCK"):
            if s.startswith(p) and len(s) > len(p):
                s = s[len(p):]
        return re.sub(r'^([A-Z]*)0+(\d+[A-Z]*)$', r'\1\2', s)

    def _fetch_via_osm_api06(self, center_lat, center_lon, extra_stands=None):
        """
        Reliable fallback using the official OpenStreetMap Core API v0.6 (Fastly CDN)
        when public Overpass API mirrors are down (502/504), rate-limited (429), or time out.
        Automatically expands and tiles across the full extent of all runways and aerodrome
        boundaries so long runways offset from the terminal (e.g. LPPR RWY 17, LFPG 26L, LSZH 14)
        never have their far-end taxiways clipped.
        """
        if center_lat is None or center_lon is None:
            return None
        import requests
        headers = {
            'User-Agent': 'GateFinder/2.0 (https://github.com/wildbill75/gsx-gatefinder)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }

        def _fetch_tile(w_b, s_b, e_b, n_b, depth=0):
            w_r, s_r, e_r, n_r = round(w_b, 5), round(s_b, 5), round(e_b, 5), round(n_b, 5)
            if e_r <= w_r or n_r <= s_r:
                return []
            url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={w_r},{s_r},{e_r},{n_r}"
            try:
                r = requests.get(url, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    d = r.json()
                    if isinstance(d, dict) and d.get("elements"):
                        return d["elements"]
                    return []
                elif r.status_code == 400 and depth < 4:
                    # Bbox exceeded 50,000 nodes in a dense urban area -> split along longer axis up to depth 4
                    if (e_b - w_b) >= (n_b - s_b):
                        mid_x = (w_b + e_b) / 2.0
                        return _fetch_tile(w_b, s_b, mid_x, n_b, depth + 1) + _fetch_tile(mid_x, s_b, e_b, n_b, depth + 1)
                    else:
                        mid_y = (s_b + n_b) / 2.0
                        return _fetch_tile(w_b, s_b, e_b, mid_y, depth + 1) + _fetch_tile(w_b, mid_y, e_b, n_b, depth + 1)
            except Exception:
                pass
            return []

        c_lat = float(center_lat)
        c_lon = float(center_lon)
        s0, w0, n0, e0 = c_lat - 0.014, c_lon - 0.018, c_lat + 0.014, c_lon + 0.018
        raw_elements = _fetch_tile(w0, s0, e0, n0)
        if not raw_elements:
            return None

        # Deduplicate elements in case _fetch_tile split a dense urban bbox (status_code == 400)
        seen_el_keys = set()
        dedup_init = []
        for el in raw_elements:
            ek = (el.get("type"), el.get("id"))
            if ek not in seen_el_keys:
                seen_el_keys.add(ek)
                dedup_init.append(el)
        raw_elements = dedup_init

        # Inspect runway & aerodrome nodes in the initial tile to detect if any runway extends outside [w0, s0, e0, n0]
        init_nodes = {
            el["id"]: (el["lat"], el["lon"])
            for el in raw_elements
            if el.get("type") == "node" and "lat" in el and "lon" in el
        }
        aero_lats, aero_lons = [], []
        for el in raw_elements:
            if el.get("type") == "way":
                aw = (el.get("tags") or {}).get("aeroway", "")
                if aw in ("runway", "aerodrome", "taxiway", "apron"):
                    for nid in el.get("nodes", ()):
                        pt = init_nodes.get(nid)
                        if pt:
                            aero_lats.append(pt[0])
                            aero_lons.append(pt[1])
        if extra_stands:
            for st in extra_stands:
                if st.get("lat") is not None and st.get("lon") is not None:
                    aero_lats.append(float(st["lat"]))
                    aero_lons.append(float(st["lon"]))

        if aero_lats and aero_lons:
            margin_lat = 0.0045  # ~500m margin beyond runway thresholds for turnaround pads / holding points
            margin_lon = 0.0055
            req_s = max(c_lat - 0.055, min(aero_lats) - margin_lat)
            req_n = min(c_lat + 0.055, max(aero_lats) + margin_lat)
            req_w = max(c_lon - 0.070, min(aero_lons) - margin_lon)
            req_e = min(c_lon + 0.070, max(aero_lons) + margin_lon)

            extra_tiles = []
            if req_n > n0 + 0.0005:
                extra_tiles.append((req_w, n0 - 0.0005, req_e, req_n))
            if req_s < s0 - 0.0005:
                extra_tiles.append((req_w, req_s, req_e, s0 + 0.0005))
            mid_s = max(req_s, s0)
            mid_n = min(req_n, n0)
            if req_e > e0 + 0.0005 and mid_n > mid_s:
                extra_tiles.append((e0 - 0.0005, mid_s, req_e, mid_n))
            if req_w < w0 - 0.0005 and mid_n > mid_s:
                extra_tiles.append((req_w, mid_s, w0 + 0.0005, mid_n))

            if extra_tiles:
                for tw_b, ts_b, te_b, tn_b in extra_tiles:
                    for x_el in _fetch_tile(tw_b, ts_b, te_b, tn_b):
                        ek = (x_el.get("type"), x_el.get("id"))
                        if ek not in seen_el_keys:
                            seen_el_keys.add(ek)
                            raw_elements.append(x_el)

        node_coords = {}
        way_geom = {}
        for el in raw_elements:
            if el.get("type") == "node" and "lat" in el and "lon" in el:
                node_coords[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}

        out_els = []
        for el in raw_elements:
            t = el.get("type")
            tags = el.get("tags") or {}
            if t == "node":
                if tags.get("aeroway") in ("parking_position", "holding_position", "gate") or "holding_position" in tags:
                    out_els.append(el)
            elif t == "way":
                geom = [node_coords[nid] for nid in el.get("nodes", []) if nid in node_coords]
                if geom:
                    way_geom[el["id"]] = geom
                    if "aeroway" in tags or "building" in tags:
                        el_c = dict(el)
                        el_c["geometry"] = geom
                        out_els.append(el_c)

        for el in raw_elements:
            if el.get("type") == "relation":
                tags = el.get("tags") or {}
                if tags.get("aeroway") in ("terminal", "apron", "hangar") or tags.get("building") in ("terminal", "hangar"):
                    el_c = dict(el)
                    new_members = []
                    for m in el.get("members", []):
                        mc = dict(m)
                        if m.get("type") == "way" and m.get("ref") in way_geom:
                            mc["geometry"] = way_geom[m["ref"]]
                        new_members.append(mc)
                    el_c["members"] = new_members
                    out_els.append(el_c)

        return {"elements": out_els} if out_els else None

    def fetch_airport_vector_data(self, icao, center_lat=None, center_lon=None, extra_stands=None):
        icao = (icao or "").upper().strip()
        if not icao:
            return None

        if (center_lat is None or center_lon is None) and extra_stands:
            valid_lats = [float(s["lat"]) for s in extra_stands if s.get("lat") is not None]
            valid_lons = [float(s["lon"]) for s in extra_stands if s.get("lon") is not None]
            if valid_lats and valid_lons:
                center_lat = sum(valid_lats) / len(valid_lats)
                center_lon = sum(valid_lons) / len(valid_lons)

        def _is_coords_valid(c_dict):
            if not c_dict:
                return False
            if center_lat is not None and center_lon is not None:
                c_lat = c_dict.get("center_lat")
                c_lon = c_dict.get("center_lon")
                if c_lat is not None and c_lon is not None:
                    if abs(float(c_lat) - float(center_lat)) > 0.15 or abs(float(c_lon) - float(center_lon)) > 0.20:
                        return False
            return True

        def _is_chart_complete(c_dict):
            if not c_dict or not c_dict.get("runways") or c_dict.get("geom_v") != 4:
                return False
            tw_pts = [p for t in c_dict.get("taxiways", []) for p in t.get("points", [])]
            if not tw_pts:
                return False
            for rwy in c_dict.get("runways", []):
                for end_info in rwy.get("ends", {}).values():
                    elat, elon = end_info.get("lat"), end_info.get("lon")
                    if elat is not None and elon is not None:
                        if min(haversine_m(elat, elon, tp[0], tp[1]) for tp in tw_pts) > 320.0:
                            return False
            if extra_stands and len(extra_stands) >= 5:
                min_tw_lat = min(p[0] for p in tw_pts) - 0.004
                max_tw_lat = max(p[0] for p in tw_pts) + 0.004
                min_tw_lon = min(p[1] for p in tw_pts) - 0.005
                max_tw_lon = max(p[1] for p in tw_pts) + 0.005
                valid_st = [
                    (float(s["lat"]), float(s["lon"]))
                    for s in extra_stands
                    if s.get("lat") is not None and s.get("lon") is not None
                ]
                if len(valid_st) >= 5:
                    covered = sum(
                        1 for slat, slon in valid_st
                        if min_tw_lat <= slat <= max_tw_lat and min_tw_lon <= slon <= max_tw_lon
                    )
                    if covered < len(valid_st) * 0.85:
                        return False
            return True

        self.ensure_disk_cache_loaded()
        cached = self.memory_cache.get(icao)
        if cached and not _is_coords_valid(cached):
            cached = None
        if cached and _is_chart_complete(cached):
            self._merge_extra_stands(cached, extra_stands)
            return cached
        if cached and (center_lat is None or center_lon is None):
            center_lat = cached.get("center_lat")
            center_lon = cached.get("center_lon")

        if center_lat is not None and center_lon is not None:
            s = round(float(center_lat) - 0.038, 5)
            w = round(float(center_lon) - 0.052, 5)
            n = round(float(center_lat) + 0.038, 5)
            e = round(float(center_lon) + 0.052, 5)
            bbox_str = f"({s},{w},{n},{e})"
            query = (
                f'[out:json][timeout:8];('
                f'way["aeroway"]{bbox_str};'
                f'node["aeroway"="parking_position"]{bbox_str};'
                f'node["aeroway"="holding_position"]{bbox_str};'
                f'node["aeroway"="gate"]{bbox_str};'
                f'way["building"="terminal"]{bbox_str};'
                f');out body geom;'
            )
        else:
            query = (
                f'[out:json][timeout:8];area["icao"="{icao}"]->.a;('
                f'way(area.a)["aeroway"="runway"];'
                f'way(area.a)["aeroway"="taxiway"];'
                f'way(area.a)["aeroway"="taxilane"];'
                f'way(area.a)["aeroway"="apron"];'
                f'way(area.a)["aeroway"="terminal"];'
                f'way(area.a)["building"="terminal"];'
                f'relation(area.a)["aeroway"="terminal"];'
                f'relation(area.a)["building"="terminal"];'
                f'relation(area.a)["aeroway"="apron"];'
                f'way(area.a)["aeroway"="hangar"];'
                f'way(area.a)["aeroway"="tower"];'
                f'way(area.a)["aeroway"="jet_bridge"];'
                f'node(area.a)["aeroway"="parking_position"];'
                f'way(area.a)["aeroway"="parking_position"];'
                f'node(area.a)["holding_position"];'
                f');out body geom;'
            )

        endpoints = [
            "https://overpass.private.coffee/api/interpreter",
            "https://overpass-api.de/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ]
        headers = {
            'User-Agent': 'GateFinderEFB/2.0 (https://github.com/wildbill75/gsx-gatefinder)',
            'Accept-Encoding': 'gzip, deflate'
        }

        with self._fetch_lock:
            icao_lock = self._icao_locks.setdefault(icao, threading.Lock())
            start_idx = self._mirror_idx
            self._mirror_idx = (self._mirror_idx + 1) % len(endpoints)

        ordered_endpoints = [endpoints[(start_idx + i) % len(endpoints)] for i in range(len(endpoints))]

        osm_data = None
        with icao_lock:
            # Re-check cache inside per-ICAO lock in case another thread just fetched it
            cur_c = self.memory_cache.get(icao)
            if cur_c and _is_coords_valid(cur_c) and _is_chart_complete(cur_c):
                self._merge_extra_stands(cur_c, extra_stands)
                return cur_c
            if time.time() - self._failed_overpass_ts.get(icao, 0.0) < 5.0:
                empty_c = self._parse_osm_geometry(icao, None, center_lat, center_lon)
                self._merge_extra_stands(empty_c, extra_stands)
                return empty_c

            for ep in ordered_endpoints:
                try:
                    import requests
                    r = requests.post(ep, data={'data': query}, headers=headers, timeout=8.0)
                    if r.status_code == 200:
                        d = r.json()
                        if isinstance(d, dict) and d.get('elements') and any(el.get("type") == "way" for el in d.get("elements", [])):
                            osm_data = d
                            break
                except Exception:
                    continue

            # Tier 3 Automatic Fallback: Official OpenStreetMap Core API v0.6 (Fastly CDN)
            if not osm_data or not osm_data.get("elements"):
                if center_lat is None or center_lon is None:
                    try:
                        import requests
                        nom_url = f"https://nominatim.openstreetmap.org/search?q={icao}+airport&format=jsonv2&limit=1"
                        nr = requests.get(nom_url, headers=headers, timeout=3.0)
                        if nr.status_code == 200 and nr.json():
                            center_lat = float(nr.json()[0]["lat"])
                            center_lon = float(nr.json()[0]["lon"])
                    except Exception:
                        pass
                osm_data = self._fetch_via_osm_api06(center_lat, center_lon, extra_stands=extra_stands)

        if (not osm_data or not osm_data.get("elements")) and cached and cached.get("runways"):
            self._merge_extra_stands(cached, extra_stands)
            return cached

        chart = self._parse_osm_geometry(icao, osm_data, center_lat, center_lon)
        self._merge_extra_stands(chart, extra_stands)

        if chart.get("runways") or chart.get("taxiways"):
            self._failed_overpass_ts.pop(icao, None)
            self.memory_cache[icao] = chart
            self.graph_cache.pop(icao, None)
            self._save_disk_cache()
        else:
            self._failed_overpass_ts[icao] = time.time()

        return chart

    def _enrich_stand_headings(self, stands_list, taxiways, terminals=None):
        if not stands_list:
            return
        taxiways = taxiways or []
        terminals = terminals or []
        for st in stands_list:
            if st.get("heading") is not None:
                continue
            slat = st.get("lat")
            slon = st.get("lon")
            if slat is None or slon is None:
                continue
            # 1. Check if a taxilane/taxiway lead-in endpoint terminates at or near the stand (<= 14m)
            best_ep_d = 14.0
            best_ep_hdg = None
            for tw in taxiways:
                pts = tw.get("points") or []
                if len(pts) < 2:
                    continue
                d0 = haversine_m(slat, slon, pts[0][0], pts[0][1])
                if d0 < best_ep_d:
                    best_ep_d = d0
                    best_ep_hdg = bearing_deg(pts[1][0], pts[1][1], pts[0][0], pts[0][1])
                d1 = haversine_m(slat, slon, pts[-1][0], pts[-1][1])
                if d1 < best_ep_d:
                    best_ep_d = d1
                    best_ep_hdg = bearing_deg(pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1])
            if best_ep_hdg is not None:
                st["heading"] = round(best_ep_hdg, 1)
                continue
            # 2. If stand is near a terminal building wall (<= 75m), orient nose perpendicular toward the terminal facade
            best_term_d = 75.0
            best_term_proj = None
            for tm in terminals:
                tpts = tm.get("points") or []
                for i in range(len(tpts) - 1):
                    plat, plon, _, dist = point_to_segment_projection(
                        slat, slon, tpts[i][0], tpts[i][1], tpts[i + 1][0], tpts[i + 1][1]
                    )
                    if dist < best_term_d:
                        best_term_d = dist
                        best_term_proj = (plat, plon)
            if best_term_proj is not None and best_term_d >= 2.0:
                st["heading"] = round(bearing_deg(slat, slon, best_term_proj[0], best_term_proj[1]), 1)
                continue
            # 3. Fallback: project stand onto nearest feeder taxilane/taxiway segment and orient from taxilane toward stand
            best_seg_d = 135.0
            best_proj = None
            for tw in taxiways:
                pts = tw.get("points") or []
                for i in range(len(pts) - 1):
                    plat, plon, _, dist = point_to_segment_projection(
                        slat, slon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]
                    )
                    if dist < best_seg_d:
                        best_seg_d = dist
                        best_proj = (plat, plon)
            if best_proj is not None and best_seg_d >= 3.5:
                st["heading"] = round(bearing_deg(best_proj[0], best_proj[1], slat, slon), 1)
        # 4. Neighbor propagation for any remaining stands without heading
        for st in stands_list:
            if st.get("heading") is not None:
                continue
            slat, slon = st.get("lat"), st.get("lon")
            if slat is None or slon is None:
                continue
            best_nd = 95.0
            best_nhdg = None
            for other in stands_list:
                if other is not st and other.get("heading") is not None and other.get("lat") is not None:
                    nd = haversine_m(slat, slon, other["lat"], other["lon"])
                    if nd < best_nd:
                        best_nd = nd
                        best_nhdg = other["heading"]
            st["heading"] = round(best_nhdg, 1) if best_nhdg is not None else 0.0

    def _merge_extra_stands(self, chart, extra_stands):
        if not chart:
            return
        tws = chart.get("taxiways") or []
        terms = chart.get("terminals") or []
        if "osm_stands" not in chart:
            chart["osm_stands"] = list(chart.get("stands") or [])
        self._enrich_stand_headings(chart["osm_stands"], tws, terms)
        if not extra_stands:
            chart["stands"] = list(chart.get("osm_stands") or [])
            self._enrich_stand_headings(chart["stands"], tws, terms)
            return
        # Build quick lookup of OSM stand headings by normalized and canonical ref
        osm_by_ref = {}
        osm_list = chart.get("osm_stands") or []
        for ost in osm_list:
            oref = str(ost.get("ref") or "").replace(" ", "").upper()
            for p in ("GATE", "STAND", "PARKING", "RAMP", "DOCK"):
                if oref.startswith(p) and len(oref) > len(p):
                    oref = oref[len(p):]
            if oref and ost.get("heading") is not None:
                osm_by_ref[oref] = ost["heading"]
                osm_by_ref[self._canon_stand_ref(oref)] = ost["heading"]
        # When GSX / BGL stands are provided, use them as the authoritative stand list
        # so the map matches the GSX profile 100% without phantom OSM stand collisions
        gsx_stands = []
        seen_items = {}
        for st in extra_stands:
            ref = str(st.get("name") or st.get("ref") or "").strip()
            lat = st.get("lat")
            lon = st.get("lon")
            if not ref or lat is None or lon is None:
                continue
            clean = self._canon_stand_ref(ref)
            raw_als = st.get("airlines") or []
            if isinstance(raw_als, (set, tuple)):
                raw_als = list(raw_als)
            st_als = [str(a).strip().upper() for a in raw_als if a and str(a).strip().upper() not in ("", "ANY", "NONE")]
            if clean in seen_items:
                existing_als = seen_items[clean].setdefault("airlines", [])
                existing_gsx = seen_items[clean].setdefault("gsx_airlines", [])
                for ac in st_als:
                    if ac not in existing_als:
                        existing_als.append(ac)
                    if ac not in existing_gsx:
                        existing_gsx.append(ac)
                continue
            s_lat = round(float(lat), 6)
            s_lon = round(float(lon), 6)
            hdg = st.get("heading")
            if hdg is not None:
                try:
                    hdg = round(float(hdg) % 360.0, 1)
                except Exception:
                    hdg = None
            if hdg is None:
                hdg = osm_by_ref.get(clean)
            if hdg is None and osm_list:
                best_od = 24.0
                for ost in osm_list:
                    if ost.get("heading") is not None and ost.get("lat") is not None and ost.get("lon") is not None:
                        od = haversine_m(s_lat, s_lon, ost["lat"], ost["lon"])
                        if od < best_od:
                            best_od = od
                            hdg = ost["heading"]
            item = {
                "ref": ref,
                "lat": s_lat,
                "lon": s_lon,
                "terminal": st.get("terminal", ""),
                "has_jetway": bool(st.get("has_jetway", False)),
                "wingspan": float(st.get("wingspan", 36.0) or 36.0),
                "is_cargo": bool(st.get("is_cargo", False)),
                "is_ga": bool(st.get("is_ga", False)),
                "is_military": bool(st.get("is_military", False)),
                "gsx_airlines": list(st_als),
                "airlines": list(st_als)
            }
            if hdg is not None:
                item["heading"] = hdg
            seen_items[clean] = item
            gsx_stands.append(item)
        if gsx_stands:
            self._enrich_stand_headings(gsx_stands, tws, terms)
            chart["stands"] = gsx_stands

    def _parse_osm_geometry(self, icao, osm_data, center_lat, center_lon):
        runways = []
        raw_runway_ways = []
        taxiways = []
        aprons = []
        terminals = []
        holding_points = []
        stands = []
        unnamed_stands = []
        gate_nodes = []
        parking_ways = []
        jet_bridges = []
        candidate_buildings = []

        elements = (osm_data or {}).get("elements", [])
        all_lats = []
        all_lons = []

        non_airport_bldg = {
            "hotel", "apartments", "house", "residential", "office", "commercial",
            "retail", "school", "university", "church", "chapel", "greenhouse",
            "train_station", "kiosk", "supermarket", "garage", "garages", "detached"
        }

        stand_by_ref = {}
        seen_osm_el_keys = set()
        seen_rwy_geom = set()

        for el in elements:
            el_id = el.get("id")
            etype = el.get("type")
            if el_id is not None:
                ek = (etype, el_id)
                if ek in seen_osm_el_keys:
                    continue
                seen_osm_el_keys.add(ek)
            tags = el.get("tags", {})
            aeroway = tags.get("aeroway", "")
            bldg = tags.get("building", "")

            if etype == "node":
                lat = el.get("lat")
                lon = el.get("lon")
                if lat is None or lon is None:
                    continue
                if aeroway == "parking_position":
                    ref = (tags.get("ref") or tags.get("name") or "").strip().rstrip(";")
                    dir_tag = tags.get("direction") or tags.get("orientation")
                    node_hdg = None
                    if dir_tag is not None:
                        try:
                            node_hdg = round(float(str(dir_tag).split(";")[0].strip()) % 360.0, 1)
                        except Exception:
                            node_hdg = None
                    if ref:
                        canon_r = self._canon_stand_ref(ref)
                        if canon_r and canon_r not in stand_by_ref:
                            s_item = {
                                "ref": ref,
                                "lat": round(lat, 6),
                                "lon": round(lon, 6)
                            }
                            if node_hdg is not None and node_hdg != 0.0:
                                s_item["heading"] = node_hdg
                            stands.append(s_item)
                            stand_by_ref[canon_r] = s_item
                    else:
                        unnamed_stands.append({
                            "lat": round(lat, 6),
                            "lon": round(lon, 6),
                            "heading": node_hdg if (node_hdg is not None and node_hdg != 0.0) else None
                        })
                elif aeroway == "gate":
                    ref = (tags.get("ref") or tags.get("name") or "").strip().rstrip(";")
                    if ref:
                        gate_nodes.append({
                            "ref": ref,
                            "lat": round(lat, 6),
                            "lon": round(lon, 6),
                            "has_jetway": True
                        })
                elif aeroway == "holding_position":
                    ref = (tags.get("ref") or tags.get("name") or "").strip().upper()
                    holding_points.append({
                        "ref": ref,
                        "lat": round(lat, 6),
                        "lon": round(lon, 6)
                    })

            elif etype == "way":
                geom = el.get("geometry", [])
                pts = [[round(pt["lat"], 6), round(pt["lon"], 6)] for pt in geom if "lat" in pt and "lon" in pt]
                if len(pts) < 2:
                    continue

                if aeroway == "runway":
                    # Ignore helicopter pads or non-linear closed perimeter polygons marked as runway
                    if pts[0] == pts[-1]:
                        continue
                    ref = tags.get("ref", "").strip()
                    pts_t = tuple((p[0], p[1]) for p in pts)
                    rev_t = tuple(reversed(pts_t))
                    g_key = (ref, min(pts_t, rev_t))
                    if g_key in seen_rwy_geom:
                        continue
                    seen_rwy_geom.add(g_key)
                    length_m = 0.0
                    for i in range(len(pts) - 1):
                        length_m += haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                    if length_m < 40.0:
                        continue
                    raw_runway_ways.append({
                        "ref": ref,
                        "points": pts,
                        "length_m": length_m
                    })

                elif aeroway in ("taxiway", "taxilane"):
                    raw_ref = (tags.get("ref") or tags.get("name") or "").strip().rstrip(";")
                    if raw_ref:
                        raw_ref = re.sub(r'^(?:TAXIWAY|TAXILANE|TWY)\s+', '', raw_ref, flags=re.IGNORECASE).strip()
                    tw_type = aeroway
                    if raw_ref:
                        if (
                            re.search(r'(?:\bTO\b|\d+TO\d+)', raw_ref, re.IGNORECASE)
                            or re.match(r'^[A-Z]?\d+\s*-\s*[A-Z]?\d+$', raw_ref, re.IGNORECASE)
                            or raw_ref.upper().startswith(("PRKG", "PARKING", "APRON", "STAND"))
                        ):
                            raw_ref = ""
                            tw_type = "taxilane"
                        else:
                            raw_ref = re.sub(r'\s+', ' ', raw_ref).upper()
                            m_lnk = re.match(r'^LINK([A-Z0-9]+)$', raw_ref)
                            if m_lnk:
                                raw_ref = f"LINK {m_lnk.group(1)}"
                    for p in pts:
                        all_lats.append(p[0])
                        all_lons.append(p[1])
                    taxiways.append({
                        "ref": raw_ref,
                        "type": tw_type,
                        "points": pts
                    })

                elif aeroway == "apron":
                    if len(pts) >= 3:
                        if pts[0] == pts[-1] or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) < 12.0:
                            aprons.append({
                                "name": tags.get("name") or tags.get("ref") or "",
                                "points": pts
                            })

                elif aeroway in ("terminal", "hangar", "tower") or bldg in ("terminal", "hangar"):
                    if len(pts) >= 3:
                        if pts[0] == pts[-1] or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) < 12.0:
                            terminals.append({
                                "name": tags.get("name") or tags.get("ref") or "",
                                "points": pts
                            })

                elif aeroway == "parking_position":
                    ref = (tags.get("ref") or tags.get("name") or "").strip().rstrip(";")
                    parking_ways.append((ref, pts))

                elif aeroway == "jet_bridge":
                    mid = pts[len(pts) // 2]
                    jet_bridges.append((mid[0], mid[1]))

                elif bldg and bldg not in non_airport_bldg and len(pts) >= 3:
                    if pts[0] == pts[-1] or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) < 12.0:
                        candidate_buildings.append((tags.get("name") or "", pts))

            elif etype == "relation":
                is_term_rel = aeroway in ("terminal", "hangar") or bldg in ("terminal", "hangar")
                is_apron_rel = aeroway == "apron"
                if is_term_rel or is_apron_rel:
                    outer_segs = []
                    for m in el.get("members", []):
                        if m.get("role") in ("outer", "") and m.get("geometry"):
                            pts = [[round(pt["lat"], 6), round(pt["lon"], 6)] for pt in m["geometry"] if "lat" in pt and "lon" in pt]
                            if len(pts) >= 2:
                                outer_segs.append(pts)
                    if outer_segs:
                        rel_name = tags.get("name") or tags.get("ref") or ""
                        rings = []
                        segs = [list(s_pts) for s_pts in outer_segs]
                        while segs:
                            cur = segs.pop(0)
                            changed = True
                            while changed and segs:
                                changed = False
                                for idx_s, s_pts in enumerate(segs):
                                    if cur[-1] == s_pts[0] or haversine_m(cur[-1][0], cur[-1][1], s_pts[0][0], s_pts[0][1]) <= 3.0:
                                        cur = cur + s_pts[1:]
                                        segs.pop(idx_s)
                                        changed = True
                                        break
                                    elif cur[-1] == s_pts[-1] or haversine_m(cur[-1][0], cur[-1][1], s_pts[-1][0], s_pts[-1][1]) <= 3.0:
                                        cur = cur + list(reversed(s_pts))[1:]
                                        segs.pop(idx_s)
                                        changed = True
                                        break
                                    elif cur[0] == s_pts[-1] or haversine_m(cur[0][0], cur[0][1], s_pts[-1][0], s_pts[-1][1]) <= 3.0:
                                        cur = s_pts[:-1] + cur
                                        segs.pop(idx_s)
                                        changed = True
                                        break
                                    elif cur[0] == s_pts[0] or haversine_m(cur[0][0], cur[0][1], s_pts[0][0], s_pts[0][1]) <= 3.0:
                                        cur = list(reversed(s_pts))[:-1] + cur
                                        segs.pop(idx_s)
                                        changed = True
                                        break
                            if len(cur) >= 3:
                                rings.append(cur)
                        for idx_r, ring_pts in enumerate(rings):
                            if len(ring_pts) >= 3 and (ring_pts[0] == ring_pts[-1] or haversine_m(ring_pts[0][0], ring_pts[1][1] if len(ring_pts) < 2 else ring_pts[-1][0], ring_pts[-1][1], ring_pts[-1][1]) < 25.0 or haversine_m(ring_pts[0][0], ring_pts[0][1], ring_pts[-1][0], ring_pts[-1][1]) < 25.0):
                                item_obj = {
                                    "name": rel_name if (idx_r == 0 or len(ring_pts) >= 16) else "",
                                    "points": ring_pts
                                }
                                if is_term_rel:
                                    terminals.append(item_obj)
                                else:
                                    aprons.append(item_obj)

        # Stitch collinear connected runway ways (e.g. displaced thresholds mapped as separate ways in OSM like LSGG RWY 04)
        merged_rwy = True
        while merged_rwy and len(raw_runway_ways) > 1:
            merged_rwy = False
            for i in range(len(raw_runway_ways)):
                for j in range(i + 1, len(raw_runway_ways)):
                    r1 = raw_runway_ways[i]
                    r2 = raw_runway_ways[j]
                    if r1["ref"] and r2["ref"] and r1["ref"] != r2["ref"]:
                        continue
                    pts1 = r1["points"]
                    pts2 = r2["points"]
                    b1 = bearing_deg(pts1[0][0], pts1[0][1], pts1[-1][0], pts1[-1][1])
                    b2 = bearing_deg(pts2[0][0], pts2[0][1], pts2[-1][0], pts2[-1][1])
                    same_dir = angle_diff_deg(b1, b2) <= 12.0
                    opp_dir = angle_diff_deg(b1, (b2 + 180.0) % 360.0) <= 12.0
                    if not same_dir and not opp_dir:
                        continue
                    d_ee_ss = haversine_m(pts1[-1][0], pts1[-1][1], pts2[0][0], pts2[0][1])
                    d_ee_ee = haversine_m(pts1[-1][0], pts1[-1][1], pts2[-1][0], pts2[-1][1])
                    d_ss_ee = haversine_m(pts1[0][0], pts1[0][1], pts2[-1][0], pts2[-1][1])
                    d_ss_ss = haversine_m(pts1[0][0], pts1[0][1], pts2[0][0], pts2[0][1])
                    combined_pts = None
                    if d_ee_ss <= 15.0 and same_dir:
                        combined_pts = pts1 + pts2[1:]
                    elif d_ee_ee <= 15.0 and opp_dir:
                        combined_pts = pts1 + list(reversed(pts2))[1:]
                    elif d_ss_ee <= 15.0 and same_dir:
                        combined_pts = pts2 + pts1[1:]
                    elif d_ss_ss <= 15.0 and opp_dir:
                        combined_pts = list(reversed(pts2)) + pts1[1:]
                    if combined_pts is not None:
                        span1 = haversine_m(pts1[0][0], pts1[0][1], pts1[-1][0], pts1[-1][1])
                        span2 = haversine_m(pts2[0][0], pts2[0][1], pts2[-1][0], pts2[-1][1])
                        span_comb = haversine_m(combined_pts[0][0], combined_pts[0][1], combined_pts[-1][0], combined_pts[-1][1])
                        if span_comb <= max(span1, span2) + 5.0:
                            continue
                        raw_runway_ways[i] = {
                            "ref": r1["ref"] or r2["ref"],
                            "points": combined_pts,
                            "length_m": r1["length_m"] + r2["length_m"]
                        }
                        raw_runway_ways.pop(j)
                        merged_rwy = True
                        break
                if merged_rwy:
                    break

        for rwy_item in raw_runway_ways:
            if rwy_item["length_m"] < 400.0:
                continue
            pts = rwy_item["points"]
            ref = rwy_item["ref"]
            for p in pts:
                all_lats.append(p[0])
                all_lons.append(p[1])
            ends = self._compute_runway_ends(ref, pts)
            runways.append({
                "ref": ref or "RWY",
                "points": pts,
                "length_m": round(rwy_item["length_m"], 1),
                "ends": ends
            })

        # Universal Y-fillet propagation: any short connector (< 480m) propagates its ref onto unnamed curved Y-fillets (< 95m)
        # that share an endpoint (<= 5m) and align in tangent direction (<= 58 deg)
        ref_totals = {}
        ref_segments = {}
        for tw in taxiways:
            r = tw.get("ref", "")
            if r and tw.get("type") == "taxiway" and r not in ("INNER", "OUTER"):
                pts = tw.get("points", [])
                w_len = sum(haversine_m(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1]) for k in range(len(pts) - 1))
                ref_totals[r] = ref_totals.get(r, 0.0) + w_len
                for k in range(len(pts) - 1):
                    ref_segments.setdefault(r, []).append((pts[k], pts[k + 1]))

        short_connectors = {r: segs for r, segs in ref_segments.items() if r.startswith("LINK") or ref_totals.get(r, 9999.0) <= 480.0}
        if short_connectors:
            for tw in taxiways:
                if not tw.get("ref") and tw.get("type") == "taxiway":
                    pts = tw.get("points", [])
                    w_len = sum(haversine_m(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1]) for k in range(len(pts) - 1))
                    if w_len <= 95.0 and len(pts) >= 2:
                        best_r = None
                        best_score = 999.0
                        for end_idx in (0, -1):
                            fp = pts[end_idx]
                            f_next = pts[1] if end_idx == 0 else pts[-2]
                            b_fillet = bearing_deg(fp[0], fp[1], f_next[0], f_next[1])
                            for r, segs in short_connectors.items():
                                for s0, s1 in segs:
                                    for sp, s_prev in ((s1, s0), (s0, s1)):
                                        d = haversine_m(fp[0], fp[1], sp[0], sp[1])
                                        if d <= 5.0:
                                            b_seg = bearing_deg(s_prev[0], s_prev[1], sp[0], sp[1])
                                            ang = angle_diff_deg(b_seg, b_fillet)
                                            if ang <= 58.0 and (d + ang * 0.1) < best_score:
                                                best_score = d + ang * 0.1
                                                best_r = r
                        if best_r:
                            tw["ref"] = best_r

        # Resolve way["aeroway"="parking_position"] into oriented stands
        tw_pts = []
        for tw in taxiways:
            for p in tw.get("points", []):
                tw_pts.append(p)

        for ref, pts in parking_ways:
            is_closed_poly = len(pts) >= 4 and (
                pts[0] == pts[-1] or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) < 2.5
            )
            if is_closed_poly:
                canon_r = self._canon_stand_ref(ref) if ref else ""
                if canon_r and canon_r in stand_by_ref:
                    continue
                pts_unique = pts[:-1] if (len(pts) > 3 and pts[0] == pts[-1]) else pts
                s_lat = round(sum(p[0] for p in pts_unique) / len(pts_unique), 6)
                s_lon = round(sum(p[1] for p in pts_unique) / len(pts_unique), 6)
                has_jw = any(haversine_m(s_lat, s_lon, jb[0], jb[1]) <= 80.0 for jb in jet_bridges)
                if not ref:
                    unnamed_stands.append({
                        "lat": s_lat,
                        "lon": s_lon,
                        "heading": None,
                        "length_m": 36.0,
                        "has_jetway": has_jw
                    })
                else:
                    new_st = {
                        "ref": ref,
                        "lat": s_lat,
                        "lon": s_lon,
                        "length_m": 36.0,
                        "has_jetway": has_jw
                    }
                    stands.append(new_st)
                    if canon_r:
                        stand_by_ref[canon_r] = new_st
                continue

            p_first = pts[0]
            p_last = pts[-1]
            if tw_pts:
                d_first = min(haversine_m(p_first[0], p_first[1], tp[0], tp[1]) for tp in tw_pts)
                d_last = min(haversine_m(p_last[0], p_last[1], tp[0], tp[1]) for tp in tw_pts)
                if d_first <= d_last:
                    entry_pt, stop_pt = p_first, p_last
                else:
                    entry_pt, stop_pt = p_last, p_first
            else:
                entry_pt, stop_pt = p_first, p_last

            len_m = 0.0
            for i in range(len(pts) - 1):
                len_m += haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            hdg = bearing_deg(entry_pt[0], entry_pt[1], stop_pt[0], stop_pt[1])
            s_lat = round(entry_pt[0] + 0.82 * (stop_pt[0] - entry_pt[0]), 6)
            s_lon = round(entry_pt[1] + 0.82 * (stop_pt[1] - entry_pt[1]), 6)
            has_jw = any(haversine_m(s_lat, s_lon, jb[0], jb[1]) <= 80.0 for jb in jet_bridges)
            if not ref:
                unnamed_stands.append({
                    "lat": s_lat,
                    "lon": s_lon,
                    "heading": round(hdg, 1),
                    "length_m": round(len_m, 1),
                    "has_jetway": has_jw
                })
                continue
            canon_r = self._canon_stand_ref(ref)
            if canon_r in stand_by_ref:
                ex_st = stand_by_ref[canon_r]
                ex_st["ref"] = ref
                ex_st["lat"] = s_lat
                ex_st["lon"] = s_lon
                ex_st["heading"] = round(hdg, 1)
                ex_st["length_m"] = round(len_m, 1)
                if has_jw:
                    ex_st["has_jetway"] = True
                continue
            new_st = {
                "ref": ref,
                "lat": s_lat,
                "lon": s_lon,
                "heading": round(hdg, 1),
                "length_m": round(len_m, 1),
                "has_jetway": has_jw
            }
            stands.append(new_st)
            if canon_r:
                stand_by_ref[canon_r] = new_st

        # Fallback 1: If no named parking_position exists in OSM (e.g. LOWI Innsbruck), assign sequential numbers to unnamed parking_positions
        if not stands and unnamed_stands:
            unnamed_stands.sort(key=lambda u: (round(u["lat"], 4), round(u["lon"], 4)))
            for idx_u, u_st in enumerate(unnamed_stands, 1):
                u_copy = dict(u_st)
                u_copy["ref"] = str(idx_u)
                if u_copy.get("heading") is None:
                    u_copy.pop("heading", None)
                stands.append(u_copy)

        # Fallback 2: If still no stands, use terminal aeroway=gate nodes if present
        if not stands and gate_nodes:
            for g_nd in gate_nodes:
                c_r = self._canon_stand_ref(g_nd["ref"])
                if c_r and c_r not in stand_by_ref:
                    stands.append(dict(g_nd))
                    stand_by_ref[c_r] = stands[-1]

        # Include apron/stand-adjacent airport buildings (e.g. north apron facilities/hangars tagged building=yes/warehouse)
        apron_boundary_pts = []
        for ap in aprons:
            for p in ap.get("points", [])[::2]:
                apron_boundary_pts.append(p)
        if candidate_buildings and (stands or apron_boundary_pts):
            for b_name, b_pts in candidate_buildings:
                p0 = b_pts[0]
                near_stand = any(haversine_m(p0[0], p0[1], st["lat"], st["lon"]) <= 85.0 for st in stands)
                near_apron = any(haversine_m(p0[0], p0[1], ap_pt[0], ap_pt[1]) <= 35.0 for ap_pt in apron_boundary_pts)
                if near_stand or near_apron:
                    terminals.append({"name": b_name, "points": b_pts})

        for st in stands:
            if "has_jetway" not in st:
                st["has_jetway"] = any(haversine_m(st["lat"], st["lon"], jb[0], jb[1]) <= 80.0 for jb in jet_bridges)

        self._enrich_stand_headings(stands, taxiways, terminals)

        if all_lats and all_lons:
            min_lat, max_lat = min(all_lats), max(all_lats)
            min_lon, max_lon = min(all_lons), max(all_lons)
            c_lat = (min_lat + max_lat) / 2.0
            c_lon = (min_lon + max_lon) / 2.0
        else:
            c_lat = center_lat or 0.0
            c_lon = center_lon or 0.0
            min_lat, max_lat = c_lat - 0.015, c_lat + 0.015
            min_lon, max_lon = c_lon - 0.02, c_lon + 0.02

        # Filter out minor/abandoned runway strips if main commercial runways (>= 1100m) exist
        long_rwys = [r for r in runways if r.get("length_m", 0) >= 1100.0 and "/" in r.get("ref", "")]
        if long_rwys:
            runways = long_rwys

        # Collect available runway designators sorted nicely
        rwy_ids = []
        for rwy in sorted(runways, key=lambda r: -r.get("length_m", 0)):
            for end_id in rwy.get("ends", {}).keys():
                if end_id not in rwy_ids:
                    rwy_ids.append(end_id)

        return {
            "icao": icao,
            "geom_v": 4,
            "full_rwy_extent": True,
            "center_lat": round(c_lat, 6),
            "center_lon": round(c_lon, 6),
            "bbox": [round(min_lat, 6), round(min_lon, 6), round(max_lat, 6), round(max_lon, 6)],
            "runways": runways,
            "available_runways": rwy_ids,
            "taxiways": taxiways,
            "aprons": aprons,
            "terminals": terminals,
            "holding_points": holding_points,
            "stands": stands,
            "osm_stands": [dict(s) for s in stands]
        }

    def _compute_runway_ends(self, ref_str, pts):
        """Maps each runway designator (e.g. '08R', '26L') to its threshold coordinate and takeoff heading."""
        p_start = pts[0]
        p_end = pts[-1]
        brg_fwd = bearing_deg(p_start[0], p_start[1], p_end[0], p_end[1])
        brg_rev = (brg_fwd + 180.0) % 360.0

        raw_parts = [p.strip().upper() for p in str(ref_str or "").replace("-", "/").replace(";", "/").split("/") if p.strip()]
        parts = [re.sub(r'^(\d)([LRC]?)$', r'0\1\2', p) for p in raw_parts]
        ends = {}

        if len(parts) == 2:
            # Match part numbers (01..36) to bearings
            def rwy_num_deg(r_id):
                digits = "".join(c for c in r_id if c.isdigit())
                if digits:
                    return (int(digits) * 10) % 360
                return None

            d0 = rwy_num_deg(parts[0])
            if d0 is not None and angle_diff_deg(d0, brg_fwd) <= angle_diff_deg(d0, brg_rev):
                ends[parts[0]] = {"lat": p_start[0], "lon": p_start[1], "end_lat": p_end[0], "end_lon": p_end[1], "heading": round(brg_fwd, 1)}
                ends[parts[1]] = {"lat": p_end[0], "lon": p_end[1], "end_lat": p_start[0], "end_lon": p_start[1], "heading": round(brg_rev, 1)}
            else:
                ends[parts[0]] = {"lat": p_end[0], "lon": p_end[1], "end_lat": p_start[0], "end_lon": p_start[1], "heading": round(brg_rev, 1)}
                ends[parts[1]] = {"lat": p_start[0], "lon": p_start[1], "end_lat": p_end[0], "end_lon": p_end[1], "heading": round(brg_fwd, 1)}
        elif len(parts) == 1 and parts[0]:
            ends[parts[0]] = {"lat": p_start[0], "lon": p_start[1], "end_lat": p_end[0], "end_lon": p_end[1], "heading": round(brg_fwd, 1)}
        else:
            r1 = f"{int(round(brg_fwd / 10.0)) % 36 or 36:02d}"
            r2 = f"{int(round(brg_rev / 10.0)) % 36 or 36:02d}"
            ends[r1] = {"lat": p_start[0], "lon": p_start[1], "end_lat": p_end[0], "end_lon": p_end[1], "heading": round(brg_fwd, 1)}
            ends[r2] = {"lat": p_end[0], "lon": p_end[1], "end_lat": p_start[0], "end_lon": p_start[1], "heading": round(brg_rev, 1)}

        return ends

    def _detect_hub_link_hierarchy(self, chart):
        """
        Universal topological detection of Inner Apron-Feeder taxiways, Outer Collector taxiways,
        and Cross-Link connector bridges across all hubs (whether named INNER/OUTER + LINK 1..5
        like LSGG, or A/B + LINK 21.. like EGLL, or INNER/OUTER + short alphanumeric bridges).
        """
        rwys = chart.get("runways", [])
        ref_pts = {}
        ref_len = {}
        for tw in chart.get("taxiways", []):
            if tw.get("type") == "taxiway" and tw.get("ref"):
                r = tw["ref"].upper()
                pts = tw.get("points", [])
                ref_pts.setdefault(r, []).extend(pts)
                ref_len[r] = ref_len.get(r, 0.0) + sum(
                    haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                    for i in range(len(pts) - 1)
                )

        def _min_rwy_d(pt):
            best = 99999.0
            for rw in rwys:
                rpts = rw.get("points", [])
                for i in range(len(rpts) - 1):
                    d = point_to_segment_projection(pt[0], pt[1], rpts[i][0], rpts[i][1], rpts[i + 1][0], rpts[i + 1][1])[3]
                    if d < best:
                        best = d
            return best

        feeder_refs = {r for r in ref_pts if r in ("INNER", "INT") or r.startswith("INNER ")}
        collector_refs = {r for r in ref_pts if r in ("OUTER", "EXT") or r.startswith("OUTER ")}
        link_refs = {r for r in ref_pts if r.startswith("LINK") or r.startswith("LK ")}

        # Case A: Hub has LINK bridges -> identify the Inner Feeder & Outer Collector rings they connect (e.g. EGLL A/B)
        if link_refs and (not feeder_refs or not collector_refs):
            long_refs = [r for r, l in ref_len.items() if l >= 950.0 and r not in link_refs]
            avg_rwy = {
                r: (sum(_min_rwy_d(p) for p in ref_pts[r]) / max(1, len(ref_pts[r])) if rwys else 0.0)
                for r in long_refs
            }
            for lr in link_refs:
                lpts = ref_pts[lr]
                touched = [
                    r for r in long_refs
                    if min(haversine_m(lp[0], lp[1], rp[0], rp[1]) for lp in lpts for rp in ref_pts[r]) <= 28.0
                ]
                if len(touched) >= 2:
                    touched.sort(key=lambda r: avg_rwy[r])
                    if avg_rwy[touched[-1]] > avg_rwy[touched[0]] + 25.0:
                        collector_refs.add(touched[0])
                        feeder_refs.add(touched[-1])
            collector_refs -= feeder_refs

        # Case B: Hub has Inner/Outer rings -> identify any short connector bridging them (and not touching a runway) as a Link
        if feeder_refs and collector_refs:
            f_pts = [p for r in feeder_refs for p in ref_pts.get(r, [])]
            c_pts = [p for r in collector_refs for p in ref_pts.get(r, [])]
            for r, pts in ref_pts.items():
                if r in feeder_refs or r in collector_refs or ref_len.get(r, 0.0) > 500.0:
                    continue
                if rwys and min(_min_rwy_d(p) for p in pts) <= 35.0:
                    continue
                df = min(haversine_m(p[0], p[1], fp[0], fp[1]) for p in pts for fp in f_pts)
                dc = min(haversine_m(p[0], p[1], cp[0], cp[1]) for p in pts for cp in c_pts)
                if df <= 28.0 and dc <= 28.0:
                    link_refs.add(r)

        return feeder_refs, collector_refs, link_refs

    def _get_or_build_graph(self, chart):
        icao = chart.get("icao", "")
        if icao in self.graph_cache:
            return self.graph_cache[icao]

        feeder_refs, collector_refs, link_refs = self._detect_hub_link_hierarchy(chart)

        nodes = []       # list of (lat, lon)
        adj = {}         # node_idx -> list of (neighbor_idx, cost, dist_m, ref, edge_type)
        grid = {}        # spatial hash for fast node snapping (~5m cells)

        def get_node_idx(lat, lon, snap_m=4.5):
            gx = int(lat * 20000)
            gy = int(lon * 20000)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for idx in grid.get((gx + dx, gy + dy), ()):
                        nlat, nlon = nodes[idx]
                        if haversine_m(lat, lon, nlat, nlon) <= snap_m:
                            return idx
            idx = len(nodes)
            nodes.append((lat, lon))
            adj[idx] = []
            grid.setdefault((gx, gy), []).append(idx)
            return idx

        def add_edge(u, v, ref, edge_type):
            if u == v:
                return
            lat1, lon1 = nodes[u]
            lat2, lon2 = nodes[v]
            dist = haversine_m(lat1, lon1, lat2, lon2)
            if dist < 0.2:
                return
            mult = 1.0
            ref_u = (ref or "").upper()
            if edge_type == "taxilane":
                mult = 1.18
            elif ref_u in feeder_refs:
                mult = 1.42  # Apron feeder lane: exit onto collector via nearest Link rather than taxiing past all stands
            elif ref_u in collector_refs:
                mult = 0.90  # Primary parallel collector taxiway
            elif edge_type == "taxiway" and not ref:
                mult = 1.12
            elif edge_type == "runway":
                mult = 4.2  # Prefer parallel taxiways over taxiing on the runway
            cost = dist * mult
            adj[u].append((v, cost, dist, ref, edge_type))
            adj[v].append((u, cost, dist, ref, edge_type))

        # 1. Insert all taxiways and taxilanes, subdividing every 12m so LINK fillets and junctions snap cleanly
        for twy in chart.get("taxiways", []):
            pts = twy.get("points", [])
            ref = twy.get("ref", "")
            etype = twy.get("type", "taxiway")
            for i in range(len(pts) - 1):
                lat1, lon1 = pts[i]
                lat2, lon2 = pts[i + 1]
                seg_len = haversine_m(lat1, lon1, lat2, lon2)
                steps = max(1, int(math.ceil(seg_len / 12.0)))
                prev_u = get_node_idx(lat1, lon1)
                for s in range(1, steps + 1):
                    f = s / float(steps)
                    mlat = lat1 + f * (lat2 - lat1)
                    mlon = lon1 + f * (lon2 - lon1)
                    curr_v = get_node_idx(mlat, mlon)
                    add_edge(prev_u, curr_v, ref, etype)
                    prev_u = curr_v

        # 2. Insert all runways (subdivided every 45m so high-speed exit turnoffs connect to runway centerline)
        for rwy in chart.get("runways", []):
            pts = rwy.get("points", [])
            ref = f"RWY {rwy.get('ref', '')}"
            for i in range(len(pts) - 1):
                lat1, lon1 = pts[i]
                lat2, lon2 = pts[i + 1]
                seg_len = haversine_m(lat1, lon1, lat2, lon2)
                steps = max(1, int(seg_len // 40.0))
                prev_u = get_node_idx(lat1, lon1)
                for s in range(1, steps + 1):
                    f = s / float(steps)
                    mlat = lat1 + f * (lat2 - lat1)
                    mlon = lon1 + f * (lon2 - lon1)
                    curr_v = get_node_idx(mlat, mlon)
                    add_edge(prev_u, curr_v, ref, "runway")
                    prev_u = curr_v

        # 3. Bridge T-junctions where a dead-end / fillet tip is within 20m of an intersecting taxiway node
        #    or within 36m of a runway centerline node (when OSM mappers stop a turnoff at the runway edge)
        num_nodes = len(nodes)
        for u in range(num_nodes):
            if len(adj[u]) <= 1:  # Dead-end or turnoff tip
                ulat, ulon = nodes[u]
                gx = int(ulat * 20000)
                gy = int(ulon * 20000)
                best_v = None
                best_score = 36.0
                # Exclude up to 3-hop neighbors along the same way so a fillet never bridges back onto itself
                exclude = {u}
                for _ in range(3):
                    nxt = set()
                    for n_idx in exclude:
                        for nbr, _, _, _, _ in adj.get(n_idx, ()):
                            nxt.add(nbr)
                    exclude |= nxt
                for dx in range(-8, 9):
                    for dy in range(-8, 9):
                        for v in grid.get((gx + dx, gy + dy), ()):
                            if v not in exclude:
                                d = haversine_m(ulat, ulon, nodes[v][0], nodes[v][1])
                                is_v_rwy = any(e[4] == "runway" for e in adj.get(v, ()))
                                max_bridge_d = 36.0 if is_v_rwy else 20.0
                                if d < max_bridge_d and d < best_score:
                                    best_score = d
                                    best_v = v
                if best_v is not None:
                    ref_u = adj[u][0][3] if adj[u] else ""
                    add_edge(u, best_v, ref_u, "taxiway")

        # 4. Penalize mid-runway crossings (> 75m from runway thresholds) so routes prefer perimeter taxiways (e.g. A at LFMN)
        rwys = chart.get("runways", [])
        if rwys:
            mid_rwy_nodes = set()
            for idx, (nlat, nlon) in enumerate(nodes):
                for r in rwys:
                    pts = r.get("points", [])
                    if len(pts) < 2:
                        continue
                    d_ends = min(
                        haversine_m(nlat, nlon, pts[0][0], pts[0][1]),
                        haversine_m(nlat, nlon, pts[-1][0], pts[-1][1])
                    )
                    if d_ends > 75.0:
                        for i in range(len(pts) - 1):
                            if point_to_segment_projection(nlat, nlon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])[3] <= 14.0:
                                mid_rwy_nodes.add(idx)
                                break
            if mid_rwy_nodes:
                for u, edges in adj.items():
                    if u not in mid_rwy_nodes:
                        adj[u] = [
                            (v, cost + (750.0 if (etype != "runway" and v in mid_rwy_nodes) else 0.0), dist, ref, etype)
                            for v, cost, dist, ref, etype in edges
                        ]

        graph = {
            "nodes": nodes,
            "adj": adj,
            "feeder_refs": feeder_refs,
            "collector_refs": collector_refs,
            "link_refs": link_refs
        }
        if icao:
            self.graph_cache[icao] = graph
        return graph

    def _find_best_runway_exit_node(
        self,
        graph,
        target_rwy_obj,
        thresh_lat,
        thresh_lon,
        rwy_hdg,
        target_rollout_m,
        min_rollout_m=950.0,
        preferred_exit_ref=None,
        gate_lat=None,
        gate_lon=None
    ):
        """
        Finds a true physical runway turnoff node located ON the runway centerline
        that connects directly to a taxiway exit.
        Traces each candidate exit branch outward away from the runway centerline (>= 35m)
        to compute the true exit turnoff angle relative to the landing heading `rwy_hdg`
        and checks whether the exit leads toward the terminal/gate side of the runway:
          - Tier 1: High-speed forward turnoffs (<= 72 deg) -> picks the first logical high-speed exit after min_rollout_m.
          - Tier 2: Right-angle / 90-deg turnoffs (72..108 deg) -> if no high-speed exit exists, picks the first right-angle exit after min_rollout_m.
          - Tier 3: Reverse / opposite-QFU turnoffs (> 108 deg) -> heavily penalized and only used as a last resort.
        Also stores `self._last_exit_out_bearing` so `_astar_path` leaves the runway along the chosen exit branch.
        """
        self._last_exit_out_bearing = None
        if not target_rwy_obj:
            return None
        pts = target_rwy_obj.get("points", [])
        if len(pts) < 2:
            return None

        pref_norm = re.sub(r'[\s_\-]+', '', str(preferred_exit_ref)).upper() if preferred_exit_ref else ""

        nodes = graph["nodes"]
        adj = graph["adj"]

        def _dist_to_rwy(lat, lon):
            return min(
                point_to_segment_projection(lat, lon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])[3]
                for i in range(len(pts) - 1)
            )

        # Compute signed side of runway for the destination gate (using landing heading vector)
        rad_hdg = math.radians(rwy_hdg)
        cos_lat = math.cos(math.radians(thresh_lat))
        rwy_vx = math.sin(rad_hdg)
        rwy_vy = math.cos(rad_hdg)
        gate_side_sign = 0
        if gate_lat is not None and gate_lon is not None:
            gx = (gate_lon - thresh_lon) * cos_lat * 111320.0
            gy = (gate_lat - thresh_lat) * 111320.0
            # Cross product z = rwy_vx * gy - rwy_vy * gx
            cz_gate = rwy_vx * gy - rwy_vy * gx
            if abs(cz_gate) > 25.0:
                gate_side_sign = 1 if cz_gate > 0 else -1

        best_node = None
        best_out_brg = None
        best_score = float('inf')

        for u, (nlat, nlon) in enumerate(nodes):
            # Fast bounding box check
            if abs(nlat - thresh_lat) > 0.045 or abs(nlon - thresh_lon) > 0.06:
                continue
            edges_u = adj.get(u, [])
            if not any(e[4] == "runway" for e in edges_u):
                continue
            d_rwy_u = _dist_to_rwy(nlat, nlon)
            if d_rwy_u > 14.0:
                continue

            twy_edges = [e for e in edges_u if e[4] != "runway"]
            if not twy_edges:
                continue

            d_from_thresh = haversine_m(thresh_lat, thresh_lon, nlat, nlon)

            # Evaluate each outward taxiway branch leaving node `u`
            for v, _, _, ref, _ in twy_edges:
                # Trace outward along non-runway edges moving away from the runway centerline
                cur = v
                out_ref = ref
                visited = {u, v}
                first_step_brg = bearing_deg(nlat, nlon, nodes[v][0], nodes[v][1])
                for _ in range(10):
                    clat, clon = nodes[cur]
                    d_cur_rwy = _dist_to_rwy(clat, clon)
                    if d_cur_rwy >= 38.0:
                        break
                    next_cands = []
                    for nb, _, _, nref, net in adj.get(cur, []):
                        if nb not in visited and net != "runway":
                            d_nb = _dist_to_rwy(nodes[nb][0], nodes[nb][1])
                            if d_nb > d_cur_rwy - 1.0:
                                next_cands.append((d_nb, nb, nref))
                    if not next_cands:
                        break
                    next_cands.sort(reverse=True)
                    _, cur, nref = next_cands[0]
                    if not out_ref and nref:
                        out_ref = nref
                    visited.add(cur)

                clat, clon = nodes[cur]
                if _dist_to_rwy(clat, clon) < 22.0:
                    # Branch never leaves the runway strip (e.g. fillet segment curving back onto runway)
                    continue

                matches_pref = False
                if pref_norm:
                    if re.sub(r'[\s_\-]+', '', (out_ref or "")).upper() == pref_norm:
                        matches_pref = True
                    elif re.sub(r'[\s_\-]+', '', (ref or "")).upper() == pref_norm:
                        matches_pref = True

                eff_min_rollout = min(min_rollout_m, 400.0) if matches_pref else min_rollout_m
                if d_from_thresh < eff_min_rollout:
                    continue

                out_brg = bearing_deg(nlat, nlon, clat, clon)
                turn_deg = angle_diff_deg(rwy_hdg, out_brg)

                # Check if exit leads to the same side of the runway as the destination gate
                side_penalty = 0.0
                if gate_side_sign != 0 and not matches_pref:
                    px = (clon - thresh_lon) * cos_lat * 111320.0
                    py = (clat - thresh_lat) * 111320.0
                    cz_exit = rwy_vx * py - rwy_vy * px
                    exit_sign = 1 if cz_exit > 0 else -1
                    if exit_sign != gate_side_sign:
                        side_penalty = 1800.0

                # Tiered turnoff angle classification:
                #   Tier 1 (<= 72 deg): High-speed forward turnoff -> prefer the first logical one after min_rollout_m
                #   Tier 2 (72..108 deg): Right-angle (90 deg) turnoff -> if only 90-deg exits exist, pick the first one after min_rollout_m
                #   Tier 3 (> 108 deg): Reverse / opposite-QFU turnoff -> heavy penalty
                if turn_deg <= 72.0:
                    tier_penalty = turn_deg * 1.5
                    # Prefer the first high-speed exit in the rollout zone
                    rollout_cost = abs(d_from_thresh - target_rollout_m) * 0.55 + (d_from_thresh - eff_min_rollout) * 0.35
                elif turn_deg <= 108.0:
                    tier_penalty = 950.0 + (turn_deg - 72.0) * 2.0
                    # For right-angle exits, strictly prefer the first one after eff_min_rollout
                    rollout_cost = (d_from_thresh - eff_min_rollout) * 0.85
                else:
                    tier_penalty = 3600.0 + turn_deg * 4.0
                    rollout_cost = abs(d_from_thresh - target_rollout_m)

                score = rollout_cost + tier_penalty + side_penalty - (5000.0 if matches_pref else 0.0)
                if score < best_score:
                    best_score = score
                    best_node = u
                    best_out_brg = first_step_brg

        self._last_exit_out_bearing = best_out_brg
        return best_node

    def _find_nearest_node(self, graph, lat, lon, prefer_non_runway=True, max_dist_m=600.0):
        nodes = graph["nodes"]
        adj = graph["adj"]
        best_idx = None
        best_score = float('inf')

        for idx, (nlat, nlon) in enumerate(nodes):
            if abs(nlat - lat) > 0.015 or abs(nlon - lon) > 0.02:
                continue
            d = haversine_m(lat, lon, nlat, nlon)
            if d > max_dist_m:
                continue
            edges = adj.get(idx, [])
            if not edges:
                continue
            is_rwy_only = all(e[4] == "runway" for e in edges)
            score = d + (350.0 if (prefer_non_runway and is_rwy_only) else 0.0)
            if score < best_score:
                best_score = score
                best_idx = idx
        return best_idx

    def _find_atc_departure_holding_node(self, graph, target_rwy_obj, thresh_lat, thresh_lon, atc_taxi_via):
        """
        When ATC issues an explicit departure taxi clearance (e.g. 'taxi via B, hold short of runway 36'
        or 'taxi to holding point W37, runway 07, via LP, LT, W2, L4, W37'), locates the runway holding
        point node where the final ATC-assigned taxiway meets the departure runway.
        This ensures backtrack / mid-field entry taxiways (such as TWY B at LFKC for RWY 36) and
        intersection departures route directly to the ATC-assigned holding point rather than forcing
        the route through unrelated aprons toward the far threshold.
        """
        if not target_rwy_obj or not atc_taxi_via:
            return None
        rpts = target_rwy_obj.get("points") or []
        if len(rpts) < 2:
            return None

        last_via_norm = ""
        for tok in reversed(atc_taxi_via):
            c = re.sub(r'[\s_\-]+', '', str(tok or "")).upper()
            if c and not c.startswith("RWY"):
                last_via_norm = c
                break
        if not last_via_norm:
            return None

        nodes = graph["nodes"]
        adj = graph["adj"]

        # Collect all nodes belonging to `last_via_norm` (and 1-hop unnamed fillet neighbors)
        via_nodes = set()
        for u, edges in adj.items():
            for v, _, _, ref, etype in edges:
                if etype != "runway" and re.sub(r'[\s_\-]+', '', str(ref or "")).upper() == last_via_norm:
                    via_nodes.add(u)
                    via_nodes.add(v)
        if not via_nodes:
            return None

        expanded_nodes = set(via_nodes)
        for u in list(via_nodes):
            for v, _, dist_m, ref, etype in adj.get(u, ()):
                if etype != "runway" and not ref and dist_m <= 45.0:
                    expanded_nodes.add(v)

        best_node = None
        best_score = float('inf')
        for u in expanded_nodes:
            nlat, nlon = nodes[u]
            edges = adj.get(u, ())
            if not edges:
                continue
            is_rwy_node = any(e[4] == "runway" for e in edges)
            d_rwy = min(
                point_to_segment_projection(nlat, nlon, rpts[i][0], rpts[i][1], rpts[i + 1][0], rpts[i + 1][1])[3]
                for i in range(len(rpts) - 1)
            )
            if d_rwy > 85.0:
                continue
            d_thresh = haversine_m(nlat, nlon, thresh_lat, thresh_lon)
            # Prefer the holding-bar position right outside the runway edge (14m..55m from centerline, non-runway node)
            hold_offset_pen = 0.0
            if is_rwy_node or d_rwy < 12.0:
                hold_offset_pen = 180.0
            elif d_rwy > 58.0:
                hold_offset_pen = (d_rwy - 58.0) * 4.0
            else:
                hold_offset_pen = abs(d_rwy - 26.0) * 1.5
            # Direct-on-via bonus over 1-hop unnamed fillet
            hop_pen = 0.0 if u in via_nodes else 35.0
            score = d_thresh + hold_offset_pen + hop_pen
            if score < best_score:
                best_score = score
                best_node = u

        return best_node

    def _find_directional_gate_node(self, graph, gate_lat, gate_lon, gate_hdg=None, mode="arrival", no_pushback=False):
        """
        Finds the best taxilane entry/exit node near (gate_lat, gate_lon) taking into account
        the stand's parking heading (gate_hdg) for directional / drive-through / loop stands.
        """
        fallback = self._find_nearest_node(graph, gate_lat, gate_lon, prefer_non_runway=True, max_dist_m=500.0)
        if gate_hdg is None or fallback is None:
            return fallback

        nodes = graph["nodes"]
        adj = graph["adj"]

        if mode == "arrival":
            # Look for a node within 42m that has an incoming edge aligned with gate_hdg
            # and sits upstream of the stand along gate_hdg so the aircraft rolls straight in.
            best_up_idx = None
            best_up_score = float('inf')
            for idx, (nlat, nlon) in enumerate(nodes):
                if abs(nlat - gate_lat) > 0.001 or abs(nlon - gate_lon) > 0.0015:
                    continue
                d = haversine_m(gate_lat, gate_lon, nlat, nlon)
                if d < 5.0 or d > 42.0:
                    continue
                edges = adj.get(idx, [])
                if not edges:
                    continue
                has_aligned_in = False
                for nb, _, _, _, etype in edges:
                    if etype != "runway":
                        in_b = bearing_deg(nodes[nb][0], nodes[nb][1], nlat, nlon)
                        if angle_diff_deg(in_b, gate_hdg) <= 45.0:
                            has_aligned_in = True
                            break
                if not has_aligned_in:
                    continue
                brg_to_gate = bearing_deg(nlat, nlon, gate_lat, gate_lon)
                diff_to_gate = angle_diff_deg(brg_to_gate, gate_hdg)
                if diff_to_gate <= 52.0:
                    score = d + diff_to_gate * 0.45
                    if score < best_up_score:
                        best_up_score = score
                        best_up_idx = idx
            if best_up_idx is not None:
                return best_up_idx

        elif mode == "departure" and no_pushback:
            # For drive-through stands (pushback=0), pick the node downstream ahead of the nose along gate_hdg
            best_dn_idx = None
            best_dn_score = float('inf')
            for idx, (nlat, nlon) in enumerate(nodes):
                if abs(nlat - gate_lat) > 0.001 or abs(nlon - gate_lon) > 0.0015:
                    continue
                d = haversine_m(gate_lat, gate_lon, nlat, nlon)
                if d < 5.0 or d > 45.0:
                    continue
                edges = adj.get(idx, [])
                if not edges:
                    continue
                brg_from_gate = bearing_deg(gate_lat, gate_lon, nlat, nlon)
                diff_from_gate = angle_diff_deg(brg_from_gate, gate_hdg)
                if diff_from_gate <= 55.0:
                    score = d + diff_from_gate * 0.45
                    if score < best_dn_score:
                        best_dn_score = score
                        best_dn_idx = idx
            if best_dn_idx is not None:
                return best_dn_idx

        return fallback

    def _astar_path(self, graph, start_idx, goal_idx, allow_runway_start=False, goal_in_heading=None, start_out_heading=None, atc_taxi_via=None):
        if start_idx is None or goal_idx is None:
            return [], []
        nodes = graph["nodes"]
        adj = graph["adj"]
        if start_idx == goal_idx:
            return [nodes[start_idx]], []

        feeder_refs = graph.get("feeder_refs", set())
        collector_refs = graph.get("collector_refs", set())
        link_refs = graph.get("link_refs", set())
        link_norms = {re.sub(r'[\s_\-]+', '', r).upper() for r in link_refs}

        via_set = {re.sub(r'[\s_\-]+', '', str(t)).upper() for t in (atc_taxi_via or []) if t}
        has_via_link = any(t.startswith("LINK") or t in link_norms for t in via_set)

        glat, glon = nodes[goal_idx]
        slat, slon = nodes[start_idx]

        # Check if goal_idx has at least one incoming non-runway edge aligned with goal_in_heading
        enforce_goal_hdg = False
        if goal_in_heading is not None:
            for nb, _, _, _, etype in adj.get(goal_idx, []):
                if etype != "runway":
                    in_b = bearing_deg(nodes[nb][0], nodes[nb][1], glat, glon)
                    if angle_diff_deg(in_b, goal_in_heading) <= 48.0:
                        enforce_goal_hdg = True
                        break

        # Check if start_idx has at least one outgoing non-runway edge aligned with start_out_heading
        enforce_start_hdg = False
        if start_out_heading is not None:
            for nb, _, _, _, etype in adj.get(start_idx, []):
                if etype != "runway":
                    out_b = bearing_deg(slat, slon, nodes[nb][0], nodes[nb][1])
                    if angle_diff_deg(out_b, start_out_heading) <= 48.0:
                        enforce_start_hdg = True
                        break

        # State: (cost_f, cost_g, current_node, prev_node, last_named_ref)
        open_heap = [(0.0, 0.0, start_idx, -1, "")]
        best_g = {}
        came_from = {}

        while open_heap:
            f, g, u, prev_u, last_ref = heapq.heappop(open_heap)
            state_key = (u, prev_u, last_ref)
            if g > best_g.get(state_key, float('inf')):
                continue
            if u == goal_idx:
                # Reconstruct path
                path_indices = []
                edge_refs = []
                cur = state_key
                while cur in came_from:
                    path_indices.append(cur[0])
                    prev_state, ref = came_from[cur]
                    edge_refs.append(ref or "")
                    cur = prev_state
                path_indices.append(start_idx)
                path_indices.reverse()
                edge_refs.reverse()
                coords = [[nodes[i][0], nodes[i][1]] for i in path_indices]
                return coords, edge_refs

            ulat, ulon = nodes[u]
            in_bearing = None
            if prev_u != -1:
                plat, plon = nodes[prev_u]
                in_bearing = bearing_deg(plat, plon, ulat, ulon)

            for v, edge_cost, dist_m, ref, etype in adj.get(u, []):
                if v == prev_u:
                    continue
                vlat, vlon = nodes[v]
                out_bearing = bearing_deg(ulat, ulon, vlat, vlon)
                turn_penalty = 0.0
                if in_bearing is not None:
                    turn_deg = angle_diff_deg(in_bearing, out_bearing)
                    if turn_deg > 135.0:
                        turn_penalty = 950.0  # Strong penalty against U-turns
                    elif turn_deg > 98.0:
                        turn_penalty = 180.0
                elif enforce_start_hdg and u == start_idx:
                    if angle_diff_deg(out_bearing, start_out_heading) > 65.0:
                        turn_penalty += 2500.0

                if enforce_goal_hdg and v == goal_idx:
                    if angle_diff_deg(out_bearing, goal_in_heading) > 65.0:
                        turn_penalty += 2500.0

                ref_u = (ref or "").upper()
                last_ref_u = (last_ref or "").upper()
                ref_norm = re.sub(r'[\s_\-]+', '', ref_u)
                last_ref_norm = re.sub(r'[\s_\-]+', '', last_ref_u)
                if ref and last_ref and ref != last_ref:
                    is_cur_link = (ref_u in link_refs or ref_u.startswith("LINK"))
                    is_last_link = (last_ref_u in link_refs or last_ref_u.startswith("LINK"))
                    if via_set and ref_norm in via_set and last_ref_norm in via_set:
                        turn_penalty += 5.0
                    elif (is_cur_link and last_ref_u in feeder_refs) or (is_last_link and ref_u in feeder_refs):
                        pass
                    elif (is_cur_link and last_ref_u in collector_refs) or (is_last_link and ref_u in collector_refs):
                        turn_penalty += 25.0
                    else:
                        turn_penalty += 55.0
                elif not ref and last_ref and etype != "runway" and not last_ref_u.startswith("RWY"):
                    # Avoid leaving an established named taxiway to cut across an unnamed apron taxilane
                    turn_penalty += 260.0
                next_ref = ref if ref else last_ref

                actual_edge_cost = dist_m if (allow_runway_start and etype == "runway" and g < 600.0) else edge_cost
                if not ref and last_ref and etype != "runway" and not last_ref_u.startswith("RWY"):
                    actual_edge_cost *= 2.2
                if via_set and etype != "runway":
                    if ref_norm and ref_norm in via_set:
                        actual_edge_cost *= 0.15
                    elif ref_norm and not ref_u.startswith("RWY"):
                        # Strongly penalize deviating onto a named taxiway not in ATC's 'via' clearance
                        actual_edge_cost *= 5.0
                        if ref != last_ref:
                            turn_penalty += 550.0
                        if has_via_link and (ref_u in link_refs or ref_u.startswith("LINK")):
                            turn_penalty += 450.0

                ng = g + actual_edge_cost + turn_penalty
                next_key = (v, u, next_ref)
                if ng < best_g.get(next_key, float('inf')):
                    best_g[next_key] = ng
                    came_from[next_key] = (state_key, ref)
                    h = haversine_m(vlat, vlon, glat, glon) * (0.45 if via_set else 1.0)
                    heapq.heappush(open_heap, (ng + h, ng, v, u, next_ref))

        return [], []

    def _detect_arrival_state_and_exit(self, chart, graph, selected_rwy_id, user_lat, user_lon, user_hdg, user_gs, user_on_ground):
        """
        Determines whether the aircraft is at the arrival airport, which runway it landed on,
        and dynamically detects which high-speed exit / turnoff the pilot takes in real time!
        """
        icao = chart.get("icao", "")
        if user_lat is None or user_lon is None:
            return None

        dist_to_apt = haversine_m(user_lat, user_lon, chart.get("center_lat", 0), chart.get("center_lon", 0))
        if dist_to_apt > 8500.0:  # More than ~4.5 NM away -> still in flight / approach
            self.locked_arrival_exit.pop(icao, None)
            self.arr_vacated_runway.pop(icao, None)
            return None

        if user_on_ground is False and dist_to_apt > 2500.0:
            self.locked_arrival_exit.pop(icao, None)
            self.arr_vacated_runway.pop(icao, None)
            return None

        # Check distance to all runways to see if the aircraft is currently rolling on a runway
        best_rwy = None
        best_rwy_end_id = selected_rwy_id
        min_rwy_dist = float('inf')
        proj_pt = None

        for rwy in chart.get("runways", []):
            pts = rwy.get("points", [])
            for i in range(len(pts) - 1):
                plat, plon, t, d = point_to_segment_projection(
                    user_lat, user_lon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]
                )
                if d < min_rwy_dist:
                    min_rwy_dist = d
                    best_rwy = rwy
                    proj_pt = (plat, plon)

        best_hdg_diff = 0.0
        if best_rwy is not None and user_hdg is not None:
            best_hdg_diff = 360.0
            for end_id, end_info in best_rwy.get("ends", {}).items():
                diff = angle_diff_deg(user_hdg, end_info["heading"])
                if diff < best_hdg_diff:
                    best_hdg_diff = diff
                    best_rwy_end_id = end_id

        # High speed on runway (> 45 kt) always means active landing roll
        if min_rwy_dist <= 26.0 and (user_gs or 0.0) > 45.0:
            self.arr_vacated_runway.pop(icao, None)

        # If on runway centerline (<= 26m) AND has not yet vacated the landing runway
        # (protects against false LANDING_ROLL when crossing an inner parallel runway during taxi-in)
        if best_rwy is not None and min_rwy_dist <= 26.0 and not self.arr_vacated_runway.get(icao):
            if best_hdg_diff <= 42.0 or (user_gs or 0.0) > 35.0:
                return {
                    "state": "LANDING_ROLL",
                    "active_rwy": best_rwy_end_id,
                    "rwy_obj": best_rwy,
                    "proj_pt": proj_pt,
                    "dist_from_centerline": min_rwy_dist
                }

        # Aircraft is on the ground and > 26m from runway centerline (vacated runway / taxiing in!)
        if user_on_ground is not False and min_rwy_dist > 26.0:
            self.arr_vacated_runway[icao] = True

        if 24.0 < min_rwy_dist <= 95.0 and not self.locked_arrival_exit.get(icao):
            # Find the taxiway exit ref right under the aircraft!
            nearest_idx = self._find_nearest_node(graph, user_lat, user_lon, prefer_non_runway=True, max_dist_m=80.0)
            if nearest_idx is not None:
                for _, _, _, ref, etype in graph["adj"].get(nearest_idx, []):
                    if etype != "runway" and ref and not ref.startswith("RWY"):
                        self.locked_arrival_exit[icao] = ref
                        break

        return {
            "state": "TAXI_IN",
            "active_rwy": best_rwy_end_id,
            "detected_exit": self.locked_arrival_exit.get(icao)
        }

    def compute_taxi_route(
        self,
        chart,
        mode,
        gate_lat,
        gate_lon,
        gate_name,
        runway_id=None,
        user_lat=None,
        user_lon=None,
        user_hdg=None,
        user_gs=None,
        user_on_ground=None,
        gate_hdg=None,
        no_pushback=False,
        atc_taxi_via=None
    ):
        """
        Computes the full geo-referenced taxi route for Departure or Arrival.
        Returns dict with route_points, rollout_points, clearance_text, taxiway_sequence,
        runway_id, available_runways, detected_exit, live_status.
        """
        if not chart or gate_lat is None or gate_lon is None:
            return None

        avail_rwys = chart.get("available_runways", [])
        if not runway_id or runway_id not in avail_rwys:
            # Try matching without leading zero or pick primary runway
            matched = None
            if runway_id:
                r_clean = runway_id.strip().upper()
                for cand in avail_rwys:
                    if cand == r_clean or cand.lstrip("0") == r_clean.lstrip("0"):
                        matched = cand
                        break
            runway_id = matched or (avail_rwys[0] if avail_rwys else "RWY")

        # Locate runway object and threshold info for runway_id
        target_rwy_obj = None
        target_end_info = None
        for rwy in chart.get("runways", []):
            if runway_id in rwy.get("ends", {}):
                target_rwy_obj = rwy
                target_end_info = rwy["ends"][runway_id]
                break

        graph = self._get_or_build_graph(chart)
        if not graph["nodes"] or not target_end_info:
            return {
                "runway_id": runway_id,
                "available_runways": avail_rwys,
                "route_points": [],
                "rollout_points": [],
                "taxiway_sequence": [],
                "clearance_text": f"Stand {gate_name} ➔ RWY {runway_id}",
                "detected_exit": None,
                "live_status": "READY"
            }

        gate_node = self._find_directional_gate_node(
            graph, gate_lat, gate_lon, gate_hdg=gate_hdg, mode=mode, no_pushback=no_pushback
        )

        # Check if user aircraft is currently on the ground at this airport (within 5 km)
        user_at_airport = False
        if user_lat is not None and user_lon is not None:
            if haversine_m(user_lat, user_lon, chart.get("center_lat", gate_lat), chart.get("center_lon", gate_lon)) < 5500.0:
                if user_on_ground is not False:
                    user_at_airport = True

        if mode == "departure":
            icao = chart.get("icao", "")
            thresh_lat = target_end_info["lat"]
            thresh_lon = target_end_info["lon"]
            rwy_hdg = target_end_info.get("heading", 0.0)
            hold_name = self._find_nearest_holding_point_name(chart, thresh_lat, thresh_lon)

            is_crossing_rwy = False
            # Check if aircraft is parked at gate (resets runway-entry latch) or has entered the active departure runway
            if user_lat is not None and user_lon is not None:
                dist_from_gate = haversine_m(user_lat, user_lon, gate_lat, gate_lon)
                if dist_from_gate < 55.0 and (user_gs or 0) < 3.0 and user_on_ground is not False:
                    self.dep_runway_entered.pop(icao, None)
                elif user_at_airport:
                    min_any_rwy_dist = float('inf')
                    dist_to_target_rwy = float('inf')
                    for rwy in chart.get("runways", []):
                        pts = rwy.get("points", [])
                        is_tgt = (rwy is target_rwy_obj) or (runway_id in rwy.get("ends", {}))
                        for i in range(len(pts) - 1):
                            _, _, _, d = point_to_segment_projection(
                                user_lat, user_lon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]
                            )
                            if d < min_any_rwy_dist:
                                min_any_rwy_dist = d
                            if is_tgt and d < dist_to_target_rwy:
                                dist_to_target_rwy = d

                    hdg_diff = angle_diff_deg(user_hdg, rwy_hdg) if user_hdg is not None else 0.0
                    dist_to_thresh = haversine_m(user_lat, user_lon, thresh_lat, thresh_lon)

                    # Distinguish lining up / taking off on active runway vs simply crossing a runway
                    # Require groundspeed >= 2.5 kt so MSFS World Map's default 0 kt runway preview never latches ON_RUNWAY
                    if (user_gs or 0.0) > 42.0 and min_any_rwy_dist <= 30.0:
                        self.dep_runway_entered[icao] = runway_id
                    elif (user_gs or 0.0) >= 2.5 and dist_to_target_rwy <= 26.0 and (
                        hdg_diff <= 38.0
                        or (dist_to_thresh <= 240.0 and hdg_diff <= 72.0)
                    ):
                        self.dep_runway_entered[icao] = runway_id
                    elif min_any_rwy_dist <= 28.0:
                        if (user_gs or 0.0) < 1.5:
                            # Stationary on runway (e.g. MSFS World Map preview before selecting a gate): route from gate
                            user_at_airport = False
                        else:
                            # Aircraft is crossing an inactive runway or crossing mid-field at an angle
                            is_crossing_rwy = True
                elif user_on_ground is False and (user_gs or 0.0) > 45.0 and dist_from_gate > 150.0:
                    self.dep_runway_entered[icao] = runway_id

            if self.dep_runway_entered.get(icao):
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": [],
                    "rollout_points": [[thresh_lat, thresh_lon], [target_end_info["end_lat"], target_end_info["end_lon"]]],
                    "taxiway_sequence": [],
                    "clearance_text": f"RWY {runway_id} Entered -> Taxi Monitoring Stopped",
                    "detected_exit": hold_name,
                    "live_status": "ON_RUNWAY"
                }

            # Target is the ATC-assigned holding point (if atc_taxi_via connects to the runway)
            # or the holding point / taxiway entry near the takeoff threshold of `runway_id`
            rwy_node = None
            if atc_taxi_via:
                rwy_node = self._find_atc_departure_holding_node(
                    graph, target_rwy_obj, thresh_lat, thresh_lon, atc_taxi_via
                )
            if rwy_node is None:
                rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=True, max_dist_m=450.0)
            if rwy_node is None:
                rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=False, max_dist_m=600.0)
            if rwy_node is not None and not hold_name:
                rn_lat, rn_lon = graph["nodes"][rwy_node]
                hold_name = self._find_nearest_holding_point_name(chart, rn_lat, rn_lon)
                if not hold_name and atc_taxi_via:
                    hold_name = str(atc_taxi_via[-1]).strip().upper()

            start_lat, start_lon = (user_lat, user_lon) if user_at_airport else (gate_lat, gate_lon)
            if user_at_airport:
                start_node = self._find_nearest_node(
                    graph, start_lat, start_lon,
                    prefer_non_runway=(not is_crossing_rwy),
                    max_dist_m=500.0
                )
                dep_out_hdg = None
            else:
                start_node = gate_node
                dep_out_hdg = gate_hdg if no_pushback else None

            path_coords, edge_refs = self._astar_path(
                graph, start_node, rwy_node,
                allow_runway_start=is_crossing_rwy,
                start_out_heading=dep_out_hdg,
                atc_taxi_via=atc_taxi_via
            )
            # For backtrack airports (e.g. LPMA, LFKJ RWY 02, LOWI RWY 08) where reaching the threshold
            # requires taxiing along the runway centerline (>= 4 consecutive runway segments), stop the
            # green ground taxi line cleanly at the runway holding point entry rather than painting over the runway.
            if not is_crossing_rwy and len(path_coords) > 2 and len(edge_refs) == len(path_coords) - 1:
                rwy_run_start = None
                consec_rwy = 0
                for idx_e, eref in enumerate(edge_refs):
                    if str(eref or "").startswith("RWY"):
                        if consec_rwy == 0:
                            rwy_run_start = idx_e
                        consec_rwy += 1
                    else:
                        if consec_rwy >= 4:
                            break
                        consec_rwy = 0
                        rwy_run_start = None
                if consec_rwy >= 4 and rwy_run_start is not None and rwy_run_start >= 1:
                    path_coords = path_coords[:rwy_run_start + 1]
                    edge_refs = edge_refs[:rwy_run_start]
            route_pts = [[round(start_lat, 6), round(start_lon, 6)]] + path_coords

            seq = self._compress_taxiway_refs(edge_refs)
            # Check if a named holding point is near the end of the route
            via_str = " -> ".join(seq) if seq else "Direct"
            hold_suffix = f"Hold {hold_name} (RWY {runway_id})" if hold_name else f"Hold Short RWY {runway_id}"
            clearance = f"Stand {gate_name} -> {via_str} -> {hold_suffix}"

            live_status = "TAXI_OUT" if (user_at_airport and (user_gs or 0) > 1.5) else "PARKED"
            return {
                "runway_id": runway_id,
                "available_runways": avail_rwys,
                "threshold": [thresh_lat, thresh_lon],
                "route_points": route_pts,
                "rollout_points": [[thresh_lat, thresh_lon], [target_end_info["end_lat"], target_end_info["end_lon"]]],
                "taxiway_sequence": seq,
                "clearance_text": clearance,
                "detected_exit": hold_name,
                "live_status": live_status
            }

        else:
            # ARRIVAL MODE:
            # 1. Check live aircraft state at arrival airport
            live_arr = self._detect_arrival_state_and_exit(
                chart, graph, runway_id, user_lat, user_lon, user_hdg, user_gs, user_on_ground
            )

            thresh_lat = target_end_info["lat"]
            thresh_lon = target_end_info["lon"]
            end_lat = target_end_info["end_lat"]
            end_lon = target_end_info["end_lon"]

            if live_arr and live_arr["state"] == "TAXI_IN":
                # Aircraft has already exited the runway! Route directly from live aircraft position to assigned gate!
                dist_gate = haversine_m(user_lat, user_lon, gate_lat, gate_lon)
                if (
                    dist_gate < 42.0
                    and gate_hdg is not None
                    and user_hdg is not None
                    and angle_diff_deg(user_hdg, gate_hdg) <= 55.0
                ):
                    route_pts = [[round(user_lat, 6), round(user_lon, 6)], [round(gate_lat, 6), round(gate_lon, 6)]]
                    seq = []
                else:
                    start_node = self._find_nearest_node(graph, user_lat, user_lon, prefer_non_runway=True, max_dist_m=300.0)
                    path_coords, edge_refs = self._astar_path(
                        graph, start_node, gate_node, allow_runway_start=False, goal_in_heading=gate_hdg,
                        atc_taxi_via=atc_taxi_via
                    )
                    route_pts = [[round(user_lat, 6), round(user_lon, 6)]] + path_coords + [[round(gate_lat, 6), round(gate_lon, 6)]]
                    seq = self._compress_taxiway_refs(edge_refs)
                det_exit = live_arr.get("detected_exit") or (seq[0] if seq else None)
                rem_seq = seq[1:] if (det_exit and seq and seq[0] == det_exit) else seq
                via_str = " -> ".join(rem_seq) if rem_seq else "Apron"
                exit_badge = f"Exit {det_exit}" if det_exit else f"Vacated RWY {runway_id}"
                clearance = f"{exit_badge} -> {via_str} -> Stand {gate_name}"
                status = "ARRIVED_AT_GATE" if dist_gate < 28.0 and (user_gs or 0) < 1.0 else "TAXI_IN"
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": route_pts,
                    "rollout_points": [],
                    "taxiway_sequence": seq,
                    "clearance_text": clearance,
                    "detected_exit": det_exit,
                    "live_status": status
                }

            elif live_arr and live_arr["state"] == "LANDING_ROLL":
                # Aircraft is currently rolling out on the runway! Find the next true turnoff node ahead on the runway centerline
                roll_lat, roll_lon = live_arr["proj_pt"]
                d_cur = haversine_m(thresh_lat, thresh_lon, roll_lat, roll_lon)
                rwy_hdg = target_end_info.get("heading", 0.0)
                pref_exit = atc_taxi_via[0] if atc_taxi_via else None
                exit_node = self._find_best_runway_exit_node(
                    graph, target_rwy_obj, thresh_lat, thresh_lon, rwy_hdg,
                    target_rollout_m=d_cur + 350.0,
                    min_rollout_m=max(200.0, d_cur + 60.0),
                    preferred_exit_ref=pref_exit,
                    gate_lat=gate_lat,
                    gate_lon=gate_lon
                )
                exit_out_hdg = getattr(self, "_last_exit_out_bearing", None)
                if exit_node is None:
                    exit_node = self._find_nearest_node(graph, roll_lat, roll_lon, prefer_non_runway=False, max_dist_m=250.0)
                path_coords, edge_refs = self._astar_path(
                    graph, exit_node, gate_node, allow_runway_start=False, goal_in_heading=gate_hdg,
                    start_out_heading=exit_out_hdg,
                    atc_taxi_via=atc_taxi_via
                )
                route_pts = path_coords + [[round(gate_lat, 6), round(gate_lon, 6)]]
                exit_start = [ list(graph["nodes"][exit_node]) ][0] if exit_node is not None else (route_pts[0] if route_pts else [roll_lat, roll_lon])
                rollout_pts = [[round(roll_lat, 6), round(roll_lon, 6)], exit_start]
                seq = self._compress_taxiway_refs(edge_refs)
                det_exit = seq[0] if seq else None
                rem_seq = seq[1:] if (det_exit and seq and seq[0] == det_exit) else seq
                via_str = " -> ".join(rem_seq) if rem_seq else "Apron"
                exit_label = f"Next Exit {det_exit}" if det_exit else f"RWY {runway_id}"
                clearance = f"{exit_label} -> {via_str} -> Stand {gate_name}"
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": route_pts,
                    "rollout_points": rollout_pts,
                    "taxiway_sequence": seq,
                    "clearance_text": clearance,
                    "detected_exit": det_exit,
                    "live_status": "LANDING_ROLL"
                }

            else:
                # Planned Arrival Route: Touchdown -> rollout along runway centerline -> true runway exit node -> Gate
                rwy_len = haversine_m(thresh_lat, thresh_lon, end_lat, end_lon)
                rollout_dist = min(max(1450.0, rwy_len * 0.62), max(1000.0, rwy_len - 300.0))
                rwy_hdg = target_end_info.get("heading", 0.0)
                pref_exit = atc_taxi_via[0] if atc_taxi_via else None

                exit_node = self._find_best_runway_exit_node(
                    graph, target_rwy_obj, thresh_lat, thresh_lon, rwy_hdg,
                    target_rollout_m=rollout_dist,
                    min_rollout_m=min(1150.0, rwy_len * 0.42),
                    preferred_exit_ref=pref_exit,
                    gate_lat=gate_lat,
                    gate_lon=gate_lon
                )
                exit_out_hdg = getattr(self, "_last_exit_out_bearing", None)
                if exit_node is None:
                    frac = min(0.82, max(0.45, rollout_dist / max(1.0, rwy_len)))
                    turnoff_lat = thresh_lat + frac * (end_lat - thresh_lat)
                    turnoff_lon = thresh_lon + frac * (end_lon - thresh_lon)
                    exit_node = self._find_nearest_node(graph, turnoff_lat, turnoff_lon, prefer_non_runway=False, max_dist_m=350.0)

                path_coords, edge_refs = self._astar_path(
                    graph, exit_node, gate_node, allow_runway_start=False, goal_in_heading=gate_hdg,
                    start_out_heading=exit_out_hdg,
                    atc_taxi_via=atc_taxi_via
                )
                route_pts = path_coords + [[round(gate_lat, 6), round(gate_lon, 6)]]
                exit_start = list(graph["nodes"][exit_node]) if exit_node is not None else (route_pts[0] if route_pts else [end_lat, end_lon])
                rollout_pts = [[thresh_lat, thresh_lon], exit_start]

                seq = self._compress_taxiway_refs(edge_refs)
                det_exit = seq[0] if seq else None
                rem_seq = seq[1:] if (det_exit and seq and seq[0] == det_exit) else seq
                via_str = " -> ".join(rem_seq) if rem_seq else "Apron"
                exit_str = f"RWY {runway_id} (Exit {det_exit})" if det_exit else f"RWY {runway_id}"
                clearance = f"{exit_str} -> {via_str} -> Stand {gate_name}"
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": route_pts,
                    "rollout_points": rollout_pts,
                    "taxiway_sequence": seq,
                    "clearance_text": clearance,
                    "detected_exit": det_exit,
                    "live_status": "PLANNED"
                }

    def _compress_taxiway_refs(self, edge_refs):
        seq = []
        for r in edge_refs:
            r_clean = (r or "").strip()
            if not r_clean or r_clean.startswith("RWY"):
                continue
            if not seq or seq[-1] != r_clean:
                if len(seq) >= 2 and seq[-2] == r_clean:
                    seq.pop()
                else:
                    seq.append(r_clean)
        return seq

    def _find_nearest_holding_point_name(self, chart, lat, lon):
        best_ref = None
        best_d = 140.0
        for hp in chart.get("holding_points", []):
            ref = hp.get("ref")
            if ref:
                d = haversine_m(lat, lon, hp["lat"], hp["lon"])
                if d < best_d:
                    best_d = d
                    best_ref = ref
        return best_ref
