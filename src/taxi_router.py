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
        self._active_taxi_route_state = {}  # {(icao, mode): {"key": ..., "coords": ..., "refs": ..., "last_seg_idx": 0}}
        self._failed_overpass_ts = {}  # {icao: timestamp} cooldown to avoid re-querying Overpass 3x on timeout
        self._fetch_lock = threading.Lock()
        self._osm_api06_lock = threading.Lock()
        self._cache_load_lock = threading.Lock()
        self._disk_cache_loaded = False
        self._icao_locks = {}
        self._mirror_idx = 0
        self.bgl_geometry_provider = None
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

        # 3. Synthesize apron/taxilane stands if cached chart had 0 OSM stands (or only 1 synthetic stand on an apron)
        cur_stands = chart.get("stands") or []
        cur_osm_stands = chart.get("osm_stands") or []
        is_single_synth = (
            len(cur_osm_stands) <= 1
            and all(bool(s.get("is_ga")) and str(s.get("ref") or "").upper() in ("1", "GA RAMP") for s in cur_osm_stands)
            and bool(chart.get("aprons"))
        )
        if (not cur_osm_stands or is_single_synth) and (
            not cur_stands
            or len(cur_stands) <= 1
        ):
            synth_stands = self._synthesize_apron_stands(
                chart.get("aprons") or [],
                chart.get("taxiways") or [],
                chart.get("terminals") or [],
                chart.get("runways") or [],
            )
            if len(synth_stands) > len(cur_osm_stands):
                chart["osm_stands"] = [dict(s) for s in synth_stands]
                chart["stands"] = [dict(s) for s in synth_stands]
                modified = True

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
            transient_keys = {"_render_cache", "_apron_hull_sig"}
            subset = {
                k: {rk: rv for rk, rv in self.memory_cache[k].items() if rk not in transient_keys}
                for k in valid_keys
            }
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

    def _fetch_via_osm_api06(self, center_lat, center_lon, extra_stands=None, icao=None):
        """
        Reliable fallback using the official OpenStreetMap Core API v0.6 (Fastly CDN)
        when public Overpass API mirrors are down (502/504), rate-limited (429), or time out.
        Automatically expands and tiles across the full extent of all runways and aerodrome
        boundaries so long runways offset from the terminal (e.g. LPPR RWY 17, LFPG 26L, LSZH 14)
        never have their far-end taxiways clipped.
        """
        if center_lat is None or center_lon is None:
            return None
        icao_u = (icao or "").strip().upper()
        if icao_u == "OMDW":
            # SimBrief's ARP for OMDW (24.9183, 55.1756) sits in the unbuilt northern desert masterplan;
            # anchor on the active runway/terminal complex so initial discovery hits the existing airport.
            center_lat, center_lon = 24.896356, 55.161389
        import requests
        with self._osm_api06_lock:
            sess = requests.Session()
            headers = {
                'User-Agent': 'GateFinder/2.0 (https://github.com/wildbill75/gsx-gatefinder)',
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate'
            }
            sess.headers.update(headers)

            def _fetch_tile(w_b, s_b, e_b, n_b, depth=0):
                w_r, s_r, e_r, n_r = round(w_b, 5), round(s_b, 5), round(e_b, 5), round(n_b, 5)
                if e_r <= w_r or n_r <= s_r:
                    return []
                url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={w_r},{s_r},{e_r},{n_r}"
                for attempt in range(3):
                    try:
                        r = sess.get(url, timeout=8.5)
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
                        elif r.status_code == 429 and attempt < 2:
                            m_wait = re.search(r'in\s+(\d+)\s+second', r.text or "", re.IGNORECASE)
                            wait_s = min(35.0, float(m_wait.group(1)) + 1.0) if m_wait else 4.0
                            time.sleep(wait_s)
                            continue
                        break
                    except Exception:
                        if attempt == 0:
                            time.sleep(0.4)
                            continue
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

            mega_aerodromes = {
                "OEDF": ("way", 230207380),
                "OMDW": ("way", 214188740),
                "KDEN": ("way", 851424893),
                "OEJN": ("relation", 4049921),
                "WMKK": ("relation", 11579113),
                "KATL": ("way", 208889095),
                "LTFM": ("way", 812730062),
                "KDFW": ("relation", 1870401),
                "OERK": ("way", 471667957),
                "KMCO": ("way", 589215792),
                "KIAD": ("relation", 949847),
                "ZBAD": ("relation", 9260711),
                "KIAH": ("way", 228729338),
                "KMCI": ("way", 209241979),
                "ZSPD": ("relation", 19842271),
                "HECA": ("way", 135896473),
                "VTBS": ("relation", 6641648),
                "LFPG": ("way", 294032205),
                "KSLC": ("way", 33005585),
                "LEMD": ("way", 167025457),
                "OMDB": ("way", 1429712446),
                "KORD": ("relation", 13423944),
                "LIRF": ("relation", 16054538),
                "EHAM": ("relation", 12470437),
                "CYMX": ("way", 1071641911),
                "KMEM": ("relation", 11810372),
                "UUDD": ("relation", 2855902),
                "OTHH": ("relation", 18055231),
                "EDDF": ("relation", 5813621),
                "RJTT": ("relation", 17864987),
                "ESSA": ("way", 81298309),
                "KMSP": ("way", 155465349),
                "CYYZ": ("way", 148396221),
                "YSSY": ("way", 211818374),
                "YBBN": ("relation", 17378993),
                "VIDP": ("relation", 19597141),
                "KDTW": ("relation", 9371952),
                "KSFO": ("way", 545819287),
                "ZBAA": ("way", 292809708),
                "KCLT": ("relation", 21083417),
                "KJFK": ("way", 158042008),
                "WSSS": ("way", 174037464),
                "WMKP": ("relation", 11581513),
                "LEBL": ("way", 314726876),
                "EDDM": ("relation", 20786018),
                "FAOR": ("way", 27657491),
                "RCTP": ("relation", 19784610),
                "RPLL": ("relation", 12733706),
                "VHHH": ("relation", 16105017),
                "LOWW": ("way", 75732093),
                "LSZH": ("relation", 13368029),
                "LFPO": ("relation", 10867719),
                "RKSI": ("way", 316419197),
            }

            # Inspect runway, taxiway & aerodrome ways AND aerodrome boundary relations in the initial tile
            # so distant satellite runways (e.g. EHAM 18R/36L Polderbaan, EDDF 07L/25R & 18, KDEN 16R/34L, LFPG)
            # are 100% discovered without fetching surrounding non-airport residential suburbs.
            init_nodes = {
                el["id"]: (el["lat"], el["lon"])
                for el in raw_elements
                if el.get("type") == "node" and "lat" in el and "lon" in el
            }
            aero_pts = []
            aero_segs = []
            aero_full_objs = []
            if icao_u in mega_aerodromes:
                aero_full_objs.append(mega_aerodromes[icao_u])

            for el in raw_elements:
                t_el = el.get("type")
                tags_el = el.get("tags") or {}
                aw = tags_el.get("aeroway", "")
                if t_el == "way" and aw in ("runway", "aerodrome", "taxiway", "apron"):
                    way_pts = []
                    for nid in el.get("nodes", ()):
                        pt = init_nodes.get(nid)
                        if pt:
                            if icao_u == "OMDW" and pt[0] > 24.912:
                                continue
                            aero_pts.append(pt)
                            way_pts.append(pt)
                    if aw == "aerodrome" and len(way_pts) >= 3:
                        for i_p in range(len(way_pts) - 1):
                            aero_segs.append((way_pts[i_p], way_pts[i_p + 1]))
                elif t_el == "relation" and aw == "aerodrome" and el.get("id"):
                    obj_k = ("relation", el["id"])
                    if obj_k not in aero_full_objs:
                        aero_full_objs.append(obj_k)

            # If no aerodrome boundary was found in the central tile, probe a thin N-S strip across the airport
            # (by Jordan's curve theorem, a N-S ray through the airport center must cross the outer perimeter fence)
            if not aero_segs and not aero_full_objs:
                try:
                    strip_els = _fetch_tile(c_lon - 0.0018, c_lat - 0.075, c_lon + 0.0018, c_lat + 0.075)
                    for s_el in strip_els:
                        s_t = s_el.get("type")
                        s_aw = (s_el.get("tags") or {}).get("aeroway", "")
                        if s_aw == "aerodrome" and s_t in ("way", "relation") and s_el.get("id"):
                            obj_k = (s_t, s_el["id"])
                            if obj_k not in aero_full_objs:
                                aero_full_objs.append(obj_k)
                except Exception:
                    pass

            for otype, oid in aero_full_objs[:2]:
                for attempt_f in range(3):
                    try:
                        rf_resp = sess.get(f"https://api.openstreetmap.org/api/0.6/{otype}/{oid}/full.json", timeout=6.0)
                        if rf_resp.status_code == 429 and attempt_f < 2:
                            m_wf = re.search(r"(\d+(?:\.\d+)?)\s*seconds", rf_resp.text or "")
                            time.sleep(min(35.0, float(m_wf.group(1)) + 1.0) if m_wf else 4.0)
                            continue
                        if rf_resp.status_code == 200:
                            rf_els = rf_resp.json().get("elements", [])
                            rf_nodes = {
                                e["id"]: (e["lat"], e["lon"])
                                for e in rf_els
                                if e.get("type") == "node" and "lat" in e and "lon" in e
                            }
                            for e in rf_els:
                                if e.get("type") == "way":
                                    w_pts = [rf_nodes[nid] for nid in e.get("nodes", ()) if nid in rf_nodes]
                                    for i_p in range(len(w_pts) - 1):
                                        p1, p2 = w_pts[i_p], w_pts[i_p + 1]
                                        if icao_u == "OMDW" and (p1[0] > 24.912 or p2[0] > 24.912):
                                            p1 = (min(p1[0], 24.912), p1[1])
                                            p2 = (min(p2[0], 24.912), p2[1])
                                        if abs(p1[0] - c_lat) <= 0.110 and abs(p1[1] - c_lon) <= 0.145:
                                            aero_segs.append((p1, p2))
                                            for k_f in range(5):
                                                f_v = k_f / 4.0
                                                aero_pts.append((p1[0] + f_v * (p2[0] - p1[0]), p1[1] + f_v * (p2[1] - p1[1])))
                        break
                    except Exception:
                        break

            if extra_stands:
                for st in extra_stands:
                    if st.get("lat") is not None and st.get("lon") is not None:
                        aero_pts.append((float(st["lat"]), float(st["lon"])))

            if aero_pts:
                if aero_segs:
                    # Sample interior points of the aerodrome perimeter polygon using Jordan curve ray-casting
                    # and build polygon-tightened center-outward grid cells so distant runways (like EHAM 18R/36L)
                    # are captured completely while non-airport urban residential blocks are skipped.
                    min_lat_p = max(c_lat - 0.105, min(p[0] for p in aero_pts))
                    max_lat_p = min(c_lat + 0.105, max(p[0] for p in aero_pts))
                    min_lon_p = max(c_lon - 0.145, min(p[1] for p in aero_pts))
                    max_lon_p = min(c_lon + 0.145, max(p[1] for p in aero_pts))
                    lat_v = min_lat_p
                    while lat_v <= max_lat_p:
                        lon_v = min_lon_p
                        while lon_v <= max_lon_p:
                            inside = False
                            for (y1, x1), (y2, x2) in aero_segs:
                                if (y1 > lat_v) != (y2 > lat_v):
                                    if lon_v < x1 + (lat_v - y1) * (x2 - x1) / (y2 - y1):
                                        inside = not inside
                            if inside:
                                aero_pts.append((lat_v, lon_v))
                            lon_v += 0.0025
                        lat_v += 0.0020

                    req_s = max(c_lat - 0.105, min(p[0] for p in aero_pts) - 0.0020)
                    req_n = min(c_lat + 0.105, max(p[0] for p in aero_pts) + 0.0020)
                    req_w = max(c_lon - 0.145, min(p[1] for p in aero_pts) - 0.0025)
                    req_e = min(c_lon + 0.145, max(p[1] for p in aero_pts) + 0.0025)

                    def _make_spans_from_center(lo_v, c0_v, c1_v, hi_v, step_v):
                        left_s = []
                        cur_v = c0_v
                        while cur_v > lo_v + 0.0005:
                            prv_v = max(lo_v, cur_v - step_v)
                            left_s.append((prv_v, cur_v, False))
                            cur_v = prv_v
                        left_s.reverse()
                        right_s = []
                        cur_v = c1_v
                        while cur_v < hi_v - 0.0005:
                            nxt_v = min(hi_v, cur_v + step_v)
                            right_s.append((cur_v, nxt_v, False))
                            cur_v = nxt_v
                        return left_s + [(c0_v, c1_v, True)] + right_s

                    x_spans = _make_spans_from_center(req_w, w0, e0, req_e, 0.045)
                    y_spans = _make_spans_from_center(req_s, s0, n0, req_n, 0.024)
                    extra_tiles = []
                    for bx0, bx1, is_cx in x_spans:
                        col_tiles = []
                        for by0, by1, is_cy in y_spans:
                            if is_cx and is_cy:
                                continue
                            s_pts = [p for p in aero_pts if by0 <= p[0] <= by1 and bx0 <= p[1] <= bx1]
                            if not s_pts:
                                continue
                            tw = max(bx0 - 0.0005, min(p[1] for p in s_pts) - 0.0020)
                            ts = max(by0 - 0.0005, min(p[0] for p in s_pts) - 0.0015)
                            te = min(bx1 + 0.0005, max(p[1] for p in s_pts) + 0.0020)
                            tn = min(by1 + 0.0005, max(p[0] for p in s_pts) + 0.0015)
                            col_tiles.append([tw, ts, te, tn, is_cx])
                        merged_col = []
                        for ct in col_tiles:
                            if (
                                merged_col
                                and not ct[4]
                                and ((ct[3] - ct[1]) < 0.011 or (merged_col[-1][3] - merged_col[-1][1]) < 0.011)
                                and abs(ct[1] - merged_col[-1][3]) < 0.002
                                and (max(ct[3], merged_col[-1][3]) - min(ct[1], merged_col[-1][1])) <= 0.036
                            ):
                                merged_col[-1][0] = min(merged_col[-1][0], ct[0])
                                merged_col[-1][1] = min(merged_col[-1][1], ct[1])
                                merged_col[-1][2] = max(merged_col[-1][2], ct[2])
                                merged_col[-1][3] = max(merged_col[-1][3], ct[3])
                            else:
                                merged_col.append(ct)
                        for tw, ts, te, tn, _ in merged_col:
                            extra_tiles.append((tw, ts, te, tn))
                else:
                    margin_lat = 0.0045  # ~500m margin beyond runway thresholds for turnaround pads / holding points
                    margin_lon = 0.0055
                    req_s = max(c_lat - 0.075, min(p[0] for p in aero_pts) - margin_lat)
                    req_n = min(c_lat + 0.075, max(p[0] for p in aero_pts) + margin_lat)
                    req_w = max(c_lon - 0.100, min(p[1] for p in aero_pts) - margin_lon)
                    req_e = min(c_lon + 0.100, max(p[1] for p in aero_pts) + margin_lon)

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
                    if (
                        tags.get("aeroway") in ("terminal", "apron", "hangar", "aerodrome")
                        or tags.get("building") in ("terminal", "hangar", "airport_terminal")
                    ):
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

        mega_default_coords = {
            "OEDF": (26.471111, 49.797778),
            "OMDW": (24.896356, 55.161389),
            "KDEN": (39.861667, -104.673056),
            "OEJN": (21.679564, 39.156536),
            "WMKK": (2.745578, 101.709917),
            "KATL": (33.636700, -84.428101),
            "LTFM": (41.275278, 28.751944),
            "KDFW": (32.896801, -97.038002),
            "OERK": (24.957600, 46.698799),
            "KMCO": (28.429399, -81.308998),
            "KIAD": (38.944500, -77.455803),
            "ZBAD": (39.509167, 116.410556),
            "KIAH": (29.984400, -95.341400),
            "KMCI": (39.297600, -94.713898),
            "ZSPD": (31.143378, 121.805214),
            "HECA": (30.121901, 31.405600),
            "VTBS": (13.681100, 100.747002),
            "LFPG": (49.009722, 2.547778),
            "KSLC": (40.788399, -111.977997),
            "LEMD": (40.471926, -3.562640),
            "OMDB": (25.252778, 55.364444),
            "KORD": (41.978611, -87.904722),
            "LIRF": (41.800278, 12.238889),
            "EHAM": (52.308613, 4.763889),
            "CYMX": (45.679500, -74.038696),
            "KMEM": (35.042400, -89.976700),
            "UUDD": (55.408800, 37.906300),
            "OTHH": (25.273100, 51.608100),
            "EDDF": (50.033300, 8.570600),
            "RJTT": (35.552300, 139.779800),
            "ESSA": (59.651900, 17.918600),
            "KMSP": (44.882000, -93.221800),
            "CYYZ": (43.677200, -79.630600),
            "YSSY": (-33.946100, 151.177200),
            "YBBN": (-27.384200, 153.117500),
            "VIDP": (28.566500, 77.103100),
            "KDTW": (42.212400, -83.353400),
            "KSFO": (37.619000, -122.374900),
            "ZBAA": (40.080100, 116.584600),
            "KCLT": (35.214000, -80.943100),
            "KJFK": (40.639800, -73.778900),
            "WSSS": (1.350200, 103.994000),
            "WMKP": (5.297100, 100.276900),
            "LEBL": (41.297100, 2.078500),
            "EDDM": (48.353800, 11.786100),
            "FAOR": (-26.139200, 28.246000),
            "RCTP": (25.077700, 121.232800),
            "RPLL": (14.508600, 121.019400),
            "VHHH": (22.308900, 113.914600),
            "LOWW": (48.110300, 16.569700),
            "LSZH": (47.464700, 8.549200),
            "LFPO": (48.725300, 2.359400),
            "RKSI": (37.469100, 126.450500),
        }
        if (center_lat is None or center_lon is None) and icao in mega_default_coords:
            center_lat, center_lon = mega_default_coords[icao]
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

        mega_min_runways = {
            "OEDF": 2, "OMDW": 1, "KDEN": 6, "OEJN": 3, "WMKK": 3,
            "KATL": 5, "LTFM": 5, "KDFW": 7, "OERK": 2, "KMCO": 4,
            "KIAD": 4, "ZBAD": 4, "KIAH": 5, "KMCI": 3, "ZSPD": 4,
            "HECA": 3, "VTBS": 3, "LFPG": 4, "KSLC": 3, "LEMD": 4,
            "OMDB": 2, "KORD": 7, "LIRF": 3, "EHAM": 6, "CYMX": 2,
            "KMEM": 4, "UUDD": 2, "OTHH": 2, "EDDF": 4, "RJTT": 4,
            "ESSA": 3, "KMSP": 4, "CYYZ": 5, "YSSY": 3, "YBBN": 2,
            "VIDP": 4, "KDTW": 6, "KSFO": 4, "ZBAA": 3, "KCLT": 3,
            "KJFK": 4, "WSSS": 3, "WMKP": 1, "LEBL": 3, "EDDM": 2,
            "FAOR": 2, "RCTP": 2, "RPLL": 2, "VHHH": 3, "LOWW": 2,
            "LSZH": 3, "LFPO": 3, "RKSI": 4,
            "KLAS": 4, "KLAX": 4, "KBOS": 5,
        }

        def _is_chart_complete(c_dict):
            if not c_dict or not c_dict.get("runways") or c_dict.get("geom_v") != 4:
                return False
            if len(c_dict.get("runways", [])) < mega_min_runways.get(icao, 1):
                return False
            tw_pts = [p for t in c_dict.get("taxiways", []) for p in t.get("points", [])]
            if not tw_pts:
                return False
            full_ext = bool(c_dict.get("full_rwy_extent"))
            is_mega = icao in mega_min_runways
            for rwy in c_dict.get("runways", []):
                end_dists = []
                for end_info in rwy.get("ends", {}).values():
                    elat, elon = end_info.get("lat"), end_info.get("lon")
                    if elat is not None and elon is not None:
                        end_dists.append(min(haversine_m(elat, elon, tp[0], tp[1]) for tp in tw_pts))
                if end_dists:
                    if is_mega:
                        if full_ext:
                            if min(end_dists) > 320.0 or max(end_dists) > 650.0:
                                return False
                        else:
                            if max(end_dists) > 320.0:
                                return False
                    else:
                        if min(end_dists) > 350.0:
                            rpts = rwy.get("points") or []
                            touches_rwy = False
                            for k_r in range(len(rpts) - 1):
                                ra, rb = rpts[k_r], rpts[k_r + 1]
                                if any(point_to_segment_projection(tp[0], tp[1], ra[0], ra[1], rb[0], rb[1])[3] <= 130.0 for tp in tw_pts[::max(1, len(tw_pts) // 80)]):
                                    touches_rwy = True
                                    break
                            if not touches_rwy:
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

        if center_lat is not None and center_lon is not None and icao not in mega_min_runways:
            s = round(float(center_lat) - 0.055, 5)
            w = round(float(center_lon) - 0.075, 5)
            n = round(float(center_lat) + 0.055, 5)
            e = round(float(center_lon) + 0.075, 5)
            s_w = round(float(center_lat) - 0.088, 5)
            w_w = round(float(center_lon) - 0.125, 5)
            n_w = round(float(center_lat) + 0.088, 5)
            e_w = round(float(center_lon) + 0.125, 5)
            bbox_str = f"({s},{w},{n},{e})"
            wide_str = f"({s_w},{w_w},{n_w},{e_w})"
            query = (
                f'[out:json][timeout:6];('
                f'way["aeroway"="runway"]{wide_str};'
                f'way["aeroway"="taxiway"]{wide_str};'
                f'node["aeroway"="holding_position"]{wide_str};'
                f'way["aeroway"]{bbox_str};'
                f'node["aeroway"="parking_position"]{bbox_str};'
                f'node["aeroway"="gate"]{bbox_str};'
                f'way["building"="terminal"]{bbox_str};'
                f'way["building"="airport_terminal"]{bbox_str};'
                f'relation["aeroway"="terminal"]{bbox_str};'
                f'relation["building"="terminal"]{bbox_str};'
                f'relation["building"="airport_terminal"]{bbox_str};'
                f'relation["aeroway"="apron"]{bbox_str};'
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
                f'way(area.a)["building"="airport_terminal"];'
                f'relation(area.a)["aeroway"="terminal"];'
                f'relation(area.a)["building"="terminal"];'
                f'relation(area.a)["building"="airport_terminal"];'
                f'relation(area.a)["aeroway"="apron"];'
                f'way(area.a)["aeroway"="hangar"];'
                f'way(area.a)["aeroway"="tower"];'
                f'way(area.a)["aeroway"="jet_bridge"];'
                f'node(area.a)["aeroway"="parking_position"];'
                f'node(area.a)["aeroway"="gate"];'
                f'way(area.a)["aeroway"="parking_position"];'
                f'node(area.a)["holding_position"];'
                f'node(area.a)["aeroway"="holding_position"];'
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
        chart = None
        with icao_lock:
            # Re-check cache inside per-ICAO lock in case another thread just fetched it
            cur_c = self.memory_cache.get(icao)
            if cur_c and _is_coords_valid(cur_c) and _is_chart_complete(cur_c):
                self._merge_extra_stands(cur_c, extra_stands)
                return cur_c
            if time.time() - self._failed_overpass_ts.get(icao, 0.0) < 5.0:
                empty_c = self._parse_osm_geometry(icao, None, center_lat, center_lon)
                extra_stands = self._apply_bgl_geometry_fallback(icao, empty_c, extra_stands)
                self._merge_extra_stands(empty_c, extra_stands)
                return empty_c

            for ep in ordered_endpoints[:2]:
                try:
                    import requests
                    r = requests.post(ep, data={'data': query}, headers=headers, timeout=4.5)
                    if r.status_code == 200:
                        d = r.json()
                        if isinstance(d, dict) and d.get('elements') and any(el.get("type") == "way" for el in d.get("elements", [])):
                            cand_c = self._parse_osm_geometry(icao, d, center_lat, center_lon)
                            if _is_chart_complete(cand_c):
                                osm_data = d
                                chart = cand_c
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
                osm_data = self._fetch_via_osm_api06(center_lat, center_lon, extra_stands=extra_stands, icao=icao)

        if (not osm_data or not osm_data.get("elements")) and cached and cached.get("runways"):
            self._merge_extra_stands(cached, extra_stands)
            return cached

        if chart is None:
            chart = self._parse_osm_geometry(icao, osm_data, center_lat, center_lon)

        if (
            cached
            and cached.get("runways")
            and len(cached.get("runways", [])) > len(chart.get("runways", []))
        ):
            self._merge_extra_stands(cached, extra_stands)
            return cached

        needs_bgl_fb = bool(
            not chart.get("runways")
            or not chart.get("taxiways")
            or (not chart.get("stands") and not extra_stands)
        )
        if not needs_bgl_fb and callable(self.bgl_geometry_provider):
            tw_pts_chk = [p for t in (chart.get("taxiways") or []) for p in (t.get("points") or [])]
            st_chk = [
                (float(s["lat"]), float(s["lon"]))
                for s in (extra_stands or chart.get("stands") or [])
                if s.get("lat") is not None and s.get("lon") is not None
            ]
            if tw_pts_chk and st_chk:
                sample_tw = tw_pts_chk[::max(1, len(tw_pts_chk) // 160)]
                if any(min(haversine_m(sla, slo, tp[0], tp[1]) for tp in sample_tw) > 185.0 for sla, slo in st_chk):
                    needs_bgl_fb = True
        if needs_bgl_fb:
            extra_stands = self._apply_bgl_geometry_fallback(icao, chart, extra_stands)

        self._merge_extra_stands(chart, extra_stands)

        if chart.get("runways") or chart.get("taxiways"):
            self._failed_overpass_ts.pop(icao, None)
            self.memory_cache[icao] = chart
            self.graph_cache.pop(icao, None)
            self._save_disk_cache()
        else:
            self._failed_overpass_ts[icao] = time.time()

        return chart

    def _synthesize_apron_stands(self, aprons, taxiways, terminals, runways):
        """
        Synthesizes well-spaced, properly oriented parking stands across all aprons and
        taxilane spurs when an airport in OpenStreetMap (e.g. LFMD Cannes-Mandelieu,
        LFPN Toussus-le-Noble, LFPZ Saint-Cyr) has mapped aprons/taxiways/hangars
        but no individual `aeroway=parking_position` nodes.
        """
        aprons = aprons or []
        taxiways = taxiways or []
        terminals = terminals or []
        runways = runways or []
        if not aprons and not taxiways:
            return []

        def _pt_in_poly(lat, lon, poly):
            inside = False
            n = len(poly)
            if n < 3:
                return False
            j = n - 1
            for i in range(n):
                yi, xi = poly[i][0], poly[i][1]
                yj, xj = poly[j][0], poly[j][1]
                if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi):
                    inside = not inside
                j = i
            return inside

        rwy_segs = [
            (pts[i], pts[i + 1])
            for r in runways
            for pts in [r.get("points") or []]
            for i in range(len(pts) - 1)
        ]
        named_tw_segs = [
            (pts[i], pts[i + 1])
            for t in taxiways
            if t.get("ref")
            for pts in [t.get("points") or []]
            for i in range(len(pts) - 1)
        ]

        def _min_seg_dist(lat, lon, segs):
            if not segs:
                return 9999.0
            return min(point_to_segment_projection(lat, lon, a[0], a[1], b[0], b[1])[3] for a, b in segs)

        phonetic_map = [
            ("NOVEMBER ECHO", "NE"), ("LIMA OUEST", "LW"), ("LIMA WEST", "LW"), ("LIMA EST", "LE"),
            ("ALPHA", "A"), ("BRAVO", "B"), ("CHARLIE", "C"), ("DELTA", "D"), ("ECHO", "E"),
            ("FOXTROT", "F"), ("GOLF", "G"), ("HOTEL", "H"), ("JULIET", "J"), ("KILO", "K"),
            ("LIMA", "L"), ("MIKE", "M"), ("NOVEMBER", "N"), ("OSCAR", "O"), ("PAPA", "P"),
            ("QUEBEC", "Q"), ("ROMEO", "R"), ("SIERRA", "S"), ("TANGO", "T"), ("UNIFORM", "U"),
            ("VICTOR", "V"), ("WHISKEY", "W"), ("YANKEE", "Y"), ("ZULU", "Z"),
        ]

        max_rwy_len = max((float(r.get("length_m") or 0.0) for r in runways), default=0.0)
        is_small_ga_field = bool(len(aprons) <= 2 and (max_rwy_len == 0.0 or max_rwy_len < 1500.0))
        min_edge_m = 14.5 if is_small_ga_field else 20.0
        step_m = 19.0 if is_small_ga_field else 34.0
        min_stand_sep = 17.5 if is_small_ga_field else 30.0
        inward_offsets = (8.5, 13.0) if is_small_ga_field else (13.5, 9.5)

        synth = []
        prefix_counts = {}
        for ap in aprons:
            pts = ap.get("points") or []
            if len(pts) < 3:
                continue
            raw_nm = (ap.get("name") or "").strip().upper()
            pfx = ""
            for k_ph, v_ph in phonetic_map:
                if k_ph in raw_nm:
                    pfx = v_ph
                    break
            if not pfx and raw_nm:
                pfx = re.sub(r"[^A-Z0-9]", "", raw_nm)[:3]

            ap_cands = []
            # 1. Sample inset parking positions along apron perimeter edges
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                elen = haversine_m(p0[0], p0[1], p1[0], p1[1])
                if elen < min_edge_m:
                    continue
                steps = max(1, int(elen // step_m))
                brg = bearing_deg(p0[0], p0[1], p1[0], p1[1])
                cos_lat = math.cos(math.radians((p0[0] + p1[0]) / 2.0))
                for s_i in range(1, steps + 1):
                    frac = s_i / (steps + 1.0)
                    mlat = p0[0] + frac * (p1[0] - p0[0])
                    mlon = p0[1] + frac * (p1[1] - p0[1])
                    placed_pt = False
                    for in_dist in inward_offsets:
                        if placed_pt:
                            break
                        for side in (90.0, -90.0):
                            in_brg = math.radians((brg + side) % 360.0)
                            ilat = mlat + (in_dist / 111320.0) * math.cos(in_brg)
                            ilon = mlon + (in_dist / (111320.0 * max(0.2, cos_lat))) * math.sin(in_brg)
                            if _pt_in_poly(ilat, ilon, pts):
                                if _min_seg_dist(ilat, ilon, rwy_segs) >= 38.0 and _min_seg_dist(ilat, ilon, named_tw_segs) >= 11.5:
                                    if not any(_pt_in_poly(ilat, ilon, tm.get("points") or []) for tm in terminals if len(tm.get("points") or []) >= 3):
                                        ap_cands.append((ilat, ilon))
                                        placed_pt = True
                                break

            # 2. Fallback to apron centroid if small apron had no edge candidates
            if not ap_cands:
                pts_u = pts[:-1] if (len(pts) > 3 and pts[0] == pts[-1]) else pts
                clat = sum(p[0] for p in pts_u) / len(pts_u)
                clon = sum(p[1] for p in pts_u) / len(pts_u)
                if _pt_in_poly(clat, clon, pts) and _min_seg_dist(clat, clon, rwy_segs) >= 38.0:
                    ap_cands.append((clat, clon))

            added_ap = 0
            for clat, clon in ap_cands:
                if added_ap >= 4 or len(synth) >= 36:
                    break
                if all(haversine_m(clat, clon, ex["lat"], ex["lon"]) >= min_stand_sep for ex in synth):
                    cnt = prefix_counts.get(pfx, 0) + 1
                    prefix_counts[pfx] = cnt
                    ref_s = f"{pfx}{cnt}" if pfx else str(cnt)
                    synth.append({
                        "ref": ref_s,
                        "lat": round(clat, 6),
                        "lon": round(clon, 6),
                        "terminal": ap.get("name") or "General Aviation Apron",
                        "has_jetway": False,
                        "is_ga": True,
                        "Synthesized": True,
                        "synthesized": True,
                        "wingspan": 18.0 if is_small_ga_field else 24.0,
                        "length_m": 12.0 if is_small_ga_field else 13.5,
                    })
                    added_ap += 1

        # 3. If airport had no apron polygons in OSM, synthesize stands at taxiway spurs away from the runway
        if not synth and taxiways:
            for tw in taxiways:
                pts = tw.get("points") or []
                if len(pts) < 2:
                    continue
                for ep, prev_p in ((pts[0], pts[1]), (pts[-1], pts[-2])):
                    if _min_seg_dist(ep[0], ep[1], rwy_segs) >= 48.0:
                        if all(haversine_m(ep[0], ep[1], ex["lat"], ex["lon"]) >= 35.0 for ex in synth):
                            idx_s = len(synth) + 1
                            synth.append({
                                "ref": str(idx_s),
                                "lat": round(ep[0], 6),
                                "lon": round(ep[1], 6),
                                "heading": round(bearing_deg(prev_p[0], prev_p[1], ep[0], ep[1]), 1),
                                "terminal": "General Aviation Apron",
                                "has_jetway": False,
                                "is_ga": True,
                                "wingspan": 24.0,
                                "length_m": 13.5,
                            })
                            if len(synth) >= 12:
                                break
                if len(synth) >= 12:
                    break

        if synth:
            self._enrich_stand_headings(synth, taxiways, terminals)
        return synth

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
            self._ensure_complete_apron_surfaces(chart)
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
        self._ensure_complete_apron_surfaces(chart)

    def _apply_bgl_geometry_fallback(self, icao, chart, extra_stands=None):
        """
        Global fallback when OpenStreetMap lacks runways, taxiways, or stands for an airport.
        Merges native MSFS BGL / default database runways and parking stands, and synthesizes
        a connected parallel collector taxiway + exit/apron links if OSM has zero taxiways.
        """
        if not isinstance(chart, dict):
            return extra_stands

        bgl_info = None
        if callable(self.bgl_geometry_provider) and (
            not chart.get("runways")
            or not chart.get("taxiways")
            or (not chart.get("stands") and not extra_stands)
        ):
            try:
                bgl_info = self.bgl_geometry_provider(icao)
            except Exception:
                bgl_info = None

        if isinstance(bgl_info, dict):
            if not extra_stands and bgl_info.get("stands"):
                extra_stands = list(bgl_info["stands"])
            if not chart.get("runways") and bgl_info.get("runways"):
                bgl_rwys = []
                rwy_ids = []
                for br in bgl_info["runways"]:
                    pts = br.get("points") or []
                    if len(pts) < 2:
                        continue
                    ref = str(br.get("ref") or "RWY").strip().upper()
                    length_m = float(br.get("length_m") or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]))
                    if length_m < 250.0:
                        continue
                    ends = self._compute_runway_ends(ref, pts)
                    bgl_rwys.append({
                        "ref": ref,
                        "points": [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in pts],
                        "length_m": round(length_m, 1),
                        "ends": ends,
                    })
                for rwy in sorted(bgl_rwys, key=lambda r: -r.get("length_m", 0.0)):
                    for end_id in rwy.get("ends", {}).keys():
                        if end_id not in rwy_ids:
                            rwy_ids.append(end_id)
                if bgl_rwys:
                    chart["runways"] = bgl_rwys
                    chart["available_runways"] = rwy_ids

        # Synthesize connected taxiway spine + stand feeders if airport has runways but 0 OSM taxiways
        rwys = chart.get("runways") or []
        if rwys and not chart.get("taxiways"):
            cand_stands = []
            for s in (extra_stands or chart.get("stands") or []):
                if s.get("lat") is not None and s.get("lon") is not None:
                    cand_stands.append((float(s["lat"]), float(s["lon"])))

            primary = max(rwys, key=lambda r: float(r.get("length_m") or 0.0))
            p0, p1 = primary["points"][0], primary["points"][-1]
            c_lat = 0.5 * (p0[0] + p1[0])
            c_lon = 0.5 * (p0[1] + p1[1])
            cos_lat = max(0.15, math.cos(math.radians(c_lat)))
            sx = 111320.0 * cos_lat
            sy = 111320.0

            def _to_m(la, lo):
                return ((lo - c_lon) * sx, (la - c_lat) * sy)

            def _to_ll(mx, my):
                return [round(c_lat + my / sy, 6), round(c_lon + mx / sx, 6)]

            r0x, r0y = _to_m(p0[0], p0[1])
            r1x, r1y = _to_m(p1[0], p1[1])
            rdx, rdy = r1x - r0x, r1y - r0y
            rlen = max(1.0, math.hypot(rdx, rdy))
            ux, uy = rdx / rlen, rdy / rlen
            nx, ny = -uy, ux

            if cand_stands:
                mean_sx = sum(_to_m(la, lo)[0] for la, lo in cand_stands) / len(cand_stands)
                mean_sy = sum(_to_m(la, lo)[1] for la, lo in cand_stands) / len(cand_stands)
                if ((mean_sx - r0x) * nx + (mean_sy - r0y) * ny) < 0.0:
                    nx, ny = -nx, -ny

            lat_off = 95.0
            synth_twys = []
            exit_fracs = (0.0, 0.5, 1.0) if rlen >= 1200.0 else (0.0, 1.0)
            spine_pts = []
            for idx_e, frac in enumerate(exit_fracs):
                rx = r0x + frac * rdx
                ry = r0y + frac * rdy
                tx = rx + lat_off * nx
                ty = ry + lat_off * ny
                spine_pts.append(_to_ll(tx, ty))
                synth_twys.append({
                    "ref": f"A{idx_e + 1}",
                    "type": "taxiway",
                    "points": [_to_ll(rx, ry), _to_ll(tx, ty)],
                    "_synth_bgl": True,
                })
            synth_twys.insert(0, {
                "ref": "A",
                "type": "taxiway",
                "points": spine_pts,
                "_synth_bgl": True,
            })

            if cand_stands:
                stand_m = [_to_m(la, lo) for la, lo in cand_stands]
                vis_s = [False] * len(stand_m)
                for i_s in range(len(stand_m)):
                    if vis_s[i_s]:
                        continue
                    vis_s[i_s] = True
                    q_s = [i_s]
                    grp = []
                    while q_s:
                        cur_s = q_s.pop()
                        grp.append(stand_m[cur_s])
                        for j_s in range(len(stand_m)):
                            if not vis_s[j_s]:
                                if (stand_m[j_s][0] - stand_m[cur_s][0]) ** 2 + (stand_m[j_s][1] - stand_m[cur_s][1]) ** 2 <= 95.0 ** 2:
                                    vis_s[j_s] = True
                                    q_s.append(j_s)
                    # Project cluster onto parallel spine and add taxilane feeder + row lane
                    grp_sorted = sorted(grp, key=lambda g: g[0] * ux + g[1] * uy)
                    lane_ll = [_to_ll(gx - 18.0 * nx if ((gx - (r0x + lat_off * nx)) * nx + (gy - (r0y + lat_off * ny)) * ny) > 25.0 else gx,
                                      gy - 18.0 * ny if ((gx - (r0x + lat_off * nx)) * nx + (gy - (r0y + lat_off * ny)) * ny) > 25.0 else gy)
                               for gx, gy in grp_sorted]
                    if len(lane_ll) >= 2:
                        synth_twys.append({"ref": "", "type": "taxilane", "points": lane_ll, "_synth_bgl": True})
                    mid_g = grp_sorted[len(grp_sorted) // 2]
                    t_proj = max(0.0, min(1.0, ((mid_g[0] - (r0x + lat_off * nx)) * rdx + (mid_g[1] - (r0y + lat_off * ny)) * rdy) / (rlen * rlen)))
                    sx_p = r0x + t_proj * rdx + lat_off * nx
                    sy_p = r0y + t_proj * rdy + lat_off * ny
                    synth_twys.append({
                        "ref": "",
                        "type": "taxilane",
                        "points": [_to_ll(sx_p, sy_p), lane_ll[len(lane_ll) // 2] if lane_ll else _to_ll(mid_g[0], mid_g[1])],
                        "_synth_bgl": True,
                    })

            chart["taxiways"] = synth_twys
            if not extra_stands and not chart.get("stands"):
                synth_st = self._synthesize_apron_stands([], synth_twys, [], rwys)
                if synth_st:
                    chart["osm_stands"] = [dict(s) for s in synth_st]
                    chart["stands"] = [dict(s) for s in synth_st]
        elif chart.get("taxiways"):
            # Bridge any stand clusters (>185m from all OSM taxiway vertices) to the nearest taxiway node
            tw_existing = chart.get("taxiways") or []
            tw_verts = [p for t in tw_existing for p in (t.get("points") or [])]
            orphan_stands = []
            for s in (extra_stands or chart.get("stands") or []):
                if s.get("lat") is not None and s.get("lon") is not None:
                    sla, slo = float(s["lat"]), float(s["lon"])
                    if tw_verts and min(haversine_m(sla, slo, tp[0], tp[1]) for tp in tw_verts[::max(1, len(tw_verts) // 200)]) > 185.0:
                        orphan_stands.append((sla, slo))
            if orphan_stands and tw_verts:
                vis_o = [False] * len(orphan_stands)
                for i_o in range(len(orphan_stands)):
                    if vis_o[i_o]:
                        continue
                    vis_o[i_o] = True
                    q_o = [i_o]
                    grp_o = []
                    while q_o:
                        cur_o = q_o.pop()
                        grp_o.append(orphan_stands[cur_o])
                        for j_o in range(len(orphan_stands)):
                            if not vis_o[j_o] and haversine_m(orphan_stands[cur_o][0], orphan_stands[cur_o][1], orphan_stands[j_o][0], orphan_stands[j_o][1]) <= 110.0:
                                vis_o[j_o] = True
                                q_o.append(j_o)
                    grp_o.sort(key=lambda pt: (pt[0], pt[1]))
                    if len(grp_o) >= 2:
                        tw_existing.append({
                            "ref": "",
                            "type": "taxilane",
                            "points": [[round(la, 6), round(lo, 6)] for la, lo in grp_o],
                            "_synth_bgl": True,
                        })
                    mid_o = grp_o[len(grp_o) // 2]
                    nearest_tp = min(tw_verts, key=lambda tp: haversine_m(mid_o[0], mid_o[1], tp[0], tp[1]))
                    if haversine_m(mid_o[0], mid_o[1], nearest_tp[0], nearest_tp[1]) <= 1200.0:
                        tw_existing.append({
                            "ref": "",
                            "type": "taxilane",
                            "points": [[round(nearest_tp[0], 6), round(nearest_tp[1], 6)], [round(mid_o[0], 6), round(mid_o[1], 6)]],
                            "_synth_bgl": True,
                        })
                chart.pop("_render_cache", None)
                if icao:
                    self.graph_cache.pop(str(icao).strip().upper(), None)

        if chart.get("runways") or chart.get("taxiways"):
            all_la = [p[0] for r in (chart.get("runways") or []) for p in (r.get("points") or [])] + [p[0] for t in (chart.get("taxiways") or []) for p in (t.get("points") or [])]
            all_lo = [p[1] for r in (chart.get("runways") or []) for p in (r.get("points") or [])] + [p[1] for t in (chart.get("taxiways") or []) for p in (t.get("points") or [])]
            for s in (extra_stands or chart.get("stands") or []):
                if s.get("lat") is not None and s.get("lon") is not None:
                    all_la.append(float(s["lat"]))
                    all_lo.append(float(s["lon"]))
            if all_la and all_lo:
                min_la, max_la = min(all_la), max(all_la)
                min_lo, max_lo = min(all_lo), max(all_lo)
                chart["center_lat"] = round(0.5 * (min_la + max_la), 6)
                chart["center_lon"] = round(0.5 * (min_lo + max_lo), 6)
                chart["bbox"] = [round(min_la, 6), round(min_lo, 6), round(max_la, 6), round(max_lo, 6)]
                chart["geom_v"] = 4
                chart["full_rwy_extent"] = True

        return extra_stands

    def _ensure_complete_apron_surfaces(self, chart):
        """
        Globally repairs incomplete, truncated, or missing OSM apron polygons for any airport:
        1. Prunes completely detached off-airport outlier helipads/loops (>420m from all main
           airport runways, stands, and connected taxiways) and tightens the chart bbox.
        2. Synthesizes PCA-windowed 2D convex hull apron polygons (clamped >=50m clear of
           runways) around uncovered stands and stand-serving apron taxilanes.
        """
        if not isinstance(chart, dict):
            return
        stands = chart.get("stands") or []
        twys_in = chart.get("taxiways") or []
        rwys = chart.get("runways") or []
        hull_sig = (2, len(stands), len(twys_in), len(rwys))
        if chart.get("_apron_hull_sig") == hull_sig:
            return

        c_lat = float(chart.get("center_lat") or 0.0)
        c_lon = float(chart.get("center_lon") or 0.0)
        sx = 111320.0 * max(0.15, math.cos(math.radians(c_lat)))
        sy = 111320.0

        def _to_m(la, lo):
            return ((lo - c_lon) * sx, (la - c_lat) * sy)

        def _to_ll(mx, my):
            return [round(c_lat + my / sy, 6), round(c_lon + mx / sx, 6)]

        def _seg_dist_m(px, py, a, b):
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            l2 = dx * dx + dy * dy
            if l2 < 1e-6:
                return math.hypot(px - a[0], py - a[1]), a[0], a[1]
            t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / l2))
            cx = a[0] + t * dx
            cy = a[1] + t * dy
            return math.hypot(px - cx, py - cy), cx, cy

        def _pt_in_polys(lat, lon, boxes):
            for poly, min_la, max_la, min_lo, max_lo in boxes:
                if min_la <= lat <= max_la and min_lo <= lon <= max_lo:
                    inside = False
                    n_p = len(poly)
                    j_p = n_p - 1
                    for i_p in range(n_p):
                        yi, xi = poly[i_p][0], poly[i_p][1]
                        yj, xj = poly[j_p][0], poly[j_p][1]
                        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi):
                            inside = not inside
                        j_p = i_p
                    if inside:
                        return True
            return False

        def _convex_hull_xy(pts_xy):
            pts_u = sorted(set((round(x, 2), round(y, 2)) for x, y in pts_xy))
            if len(pts_u) <= 2:
                return pts_u

            def _cross(o, a, b):
                return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

            lower = []
            for p in pts_u:
                while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
                    lower.pop()
                lower.append(p)
            upper = []
            for p in reversed(pts_u):
                while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
                    upper.pop()
                upper.append(p)
            return lower[:-1] + upper[:-1]

        rwy_segs_m = [
            (_to_m(rpts[i][0], rpts[i][1]), _to_m(rpts[i + 1][0], rpts[i + 1][1]))
            for r in rwys for rpts in [r.get("points") or []] for i in range(len(rpts) - 1)
        ]

        def _min_rwy_dist(px, py):
            best = 1e9
            for a, b in rwy_segs_m:
                d = _seg_dist_m(px, py, a, b)[0]
                if d < best:
                    best = d
            return best

        stand_m = [_to_m(float(s["lat"]), float(s["lon"])) for s in stands if s.get("lat") is not None and s.get("lon") is not None]
        stand_grid = {}
        for sx0, sy0 in stand_m:
            stand_grid.setdefault((int(sx0 // 100.0), int(sy0 // 100.0)), []).append((sx0, sy0))

        def _near_stand_m(px, py, max_d):
            if not stand_m:
                return False
            rad = int(math.ceil(max_d / 100.0))
            gx, gy = int(px // 100.0), int(py // 100.0)
            d2_lim = max_d * max_d
            for dx in range(-rad, rad + 1):
                for dy in range(-rad, rad + 1):
                    for sx0, sy0 in stand_grid.get((gx + dx, gy + dy), ()):
                        if (px - sx0) ** 2 + (py - sy0) ** 2 <= d2_lim:
                            return True
            return False

        twys = [t for t in twys_in if len(t.get("points") or []) >= 2]
        n_tw = len(twys)
        tw_pts_m = [[_to_m(p[0], p[1]) for p in t["points"]] for t in twys]
        prev_aprons = chart.get("aprons") or []
        had_prev_synth = any(ap.get("_synth_hull") for ap in prev_aprons)
        orig_aprons = [ap for ap in prev_aprons if not ap.get("_synth_hull")]
        pruned_ap = 0
        pruned_tw = 0

        # 1. Prune detached off-airport outlier helipad islands (>420m from all main airport features)
        if rwys and n_tw > 0:
            parent = list(range(n_tw))

            def _find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def _union(a, b):
                ra, rb = _find(a), _find(b)
                if ra != rb:
                    parent[rb] = ra

            v_grid = {}
            for idx_t, pts_m in enumerate(tw_pts_m):
                for vx, vy in pts_m:
                    gx, gy = int(vx // 45.0), int(vy // 45.0)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            for o_idx, ox, oy in v_grid.get((gx + dx, gy + dy), ()):
                                if o_idx != idx_t and (vx - ox) ** 2 + (vy - oy) ** 2 <= 42.0 ** 2:
                                    _union(idx_t, o_idx)
                    v_grid.setdefault((gx, gy), []).append((idx_t, vx, vy))

            main_roots = set()
            for idx_t, pts_m in enumerate(tw_pts_m):
                if any(_min_rwy_dist(vx, vy) <= 160.0 or _near_stand_m(vx, vy, 160.0) for vx, vy in (pts_m[0], pts_m[-1], pts_m[len(pts_m) // 2])):
                    main_roots.add(_find(idx_t))

            if main_roots:
                main_v_grid = {}
                for idx_t, pts_m in enumerate(tw_pts_m):
                    if _find(idx_t) in main_roots:
                        for vx, vy in pts_m:
                            main_v_grid.setdefault((int(vx // 220.0), int(vy // 220.0)), []).append((vx, vy))

                def _near_main_twy(px, py, max_d=420.0):
                    gx, gy = int(px // 220.0), int(py // 220.0)
                    d2 = max_d * max_d
                    for dx in (-2, -1, 0, 1, 2):
                        for dy in (-2, -1, 0, 1, 2):
                            for vx, vy in main_v_grid.get((gx + dx, gy + dy), ()):
                                if (px - vx) ** 2 + (py - vy) ** 2 <= d2:
                                    return True
                    return False

                kept_twys = []
                kept_tw_pts_m = []
                for idx_t, t in enumerate(twys):
                    pts_m = tw_pts_m[idx_t]
                    if (
                        _find(idx_t) in main_roots
                        or _min_rwy_dist(pts_m[0][0], pts_m[0][1]) <= 420.0
                        or _near_stand_m(pts_m[0][0], pts_m[0][1], 420.0)
                        or _near_main_twy(pts_m[0][0], pts_m[0][1], 420.0)
                    ):
                        kept_twys.append(t)
                        kept_tw_pts_m.append(pts_m)
                    else:
                        pruned_tw += 1
                if pruned_tw > 0 and kept_twys:
                    twys = kept_twys
                    tw_pts_m = kept_tw_pts_m

                if len(orig_aprons) > 1:
                    kept_aps = []
                    for ap in orig_aprons:
                        ap_pts = ap.get("points") or []
                        ap_m = [_to_m(p[0], p[1]) for p in ap_pts]
                        if any(
                            _min_rwy_dist(ax, ay) <= 420.0
                            or _near_stand_m(ax, ay, 420.0)
                            or _near_main_twy(ax, ay, 420.0)
                            for ax, ay in ap_m
                        ):
                            kept_aps.append(ap)
                        else:
                            pruned_ap += 1
                    if kept_aps:
                        orig_aprons = kept_aps

        # 2. Spatial hashes for named main taxiways and existing apron edges
        named_segs = []
        named_grid = {}
        for idx_t, t in enumerate(twys):
            if t.get("type") == "taxiway" and t.get("ref"):
                pts_m = tw_pts_m[idx_t]
                for i in range(len(pts_m) - 1):
                    a, b = pts_m[i], pts_m[i + 1]
                    s_id = len(named_segs)
                    named_segs.append((a, b))
                    for gx in range(int((min(a[0], b[0]) - 24.0) // 60.0), int((max(a[0], b[0]) + 24.0) // 60.0) + 1):
                        for gy in range(int((min(a[1], b[1]) - 24.0) // 60.0), int((max(a[1], b[1]) + 24.0) // 60.0) + 1):
                            named_grid.setdefault((gx, gy), []).append(s_id)

        def _near_named_twy(px, py, lim=9.0):
            for s_id in named_grid.get((int(px // 60.0), int(py // 60.0)), ()):
                if _seg_dist_m(px, py, named_segs[s_id][0], named_segs[s_id][1])[0] <= lim:
                    return True
            return False

        ap_boxes = []
        ap_edges = []
        ap_edge_grid = {}
        for ap in orig_aprons:
            pts = ap.get("points") or []
            if len(pts) >= 3:
                las = [p[0] for p in pts]
                los = [p[1] for p in pts]
                ap_boxes.append((pts, min(las), max(las), min(los), max(los)))
                for i in range(len(pts) - 1):
                    a = _to_m(pts[i][0], pts[i][1])
                    b = _to_m(pts[i + 1][0], pts[i + 1][1])
                    e_id = len(ap_edges)
                    ap_edges.append((a, b))
                    for gx in range(int((min(a[0], b[0]) - 15.0) // 60.0), int((max(a[0], b[0]) + 15.0) // 60.0) + 1):
                        for gy in range(int((min(a[1], b[1]) - 15.0) // 60.0), int((max(a[1], b[1]) + 15.0) // 60.0) + 1):
                            ap_edge_grid.setdefault((gx, gy), []).append(e_id)

        def _is_covered_pt(la, lo, mx, my, edge_tol=10.0):
            if _pt_in_polys(la, lo, ap_boxes):
                return True
            for e_id in ap_edge_grid.get((int(mx // 60.0), int(my // 60.0)), ()):
                if _seg_dist_m(px=mx, py=my, a=ap_edges[e_id][0], b=ap_edges[e_id][1])[0] <= edge_tol:
                    return True
            return False

        # 3. Collect covered and uncovered stand + densified stand-lead-in apron points
        uncovered = []
        covered = []
        for s in stands:
            if s.get("lat") is not None and s.get("lon") is not None:
                sla, slo = float(s["lat"]), float(s["lon"])
                mx, my = _to_m(sla, slo)
                if _min_rwy_dist(mx, my) > 48.0:
                    item = (sla, slo, mx, my, 30.0, True, -1)
                    if _is_covered_pt(sla, slo, mx, my, 12.0):
                        covered.append(item)
                    else:
                        uncovered.append(item)

        for idx_t, t in enumerate(twys):
            is_lane = (t.get("type") == "taxilane") or (t.get("type") == "taxiway" and not t.get("ref"))
            if not is_lane:
                continue
            pts_m = tw_pts_m[idx_t]
            if stand_m and not any(_near_stand_m(mx, my, 45.0) for mx, my in pts_m):
                continue
            dense_m = []
            for k in range(len(pts_m) - 1):
                ax, ay = pts_m[k]
                bx, by = pts_m[k + 1]
                slen = math.hypot(bx - ax, by - ay)
                n_sub = max(1, int(slen // 24.0))
                for s_i in range(n_sub):
                    f = s_i / float(n_sub)
                    dense_m.append((ax + f * (bx - ax), ay + f * (by - ay)))
            dense_m.append(pts_m[-1])

            for mx, my in dense_m:
                if _min_rwy_dist(mx, my) <= 64.0:
                    continue
                if stand_m and not _near_stand_m(mx, my, 235.0):
                    continue
                if _near_named_twy(mx, my, 9.0):
                    continue
                la, lo = c_lat + my / sy, c_lon + mx / sx
                item = (la, lo, mx, my, 20.0, False, idx_t)
                if _is_covered_pt(la, lo, mx, my, 8.0):
                    covered.append(item)
                else:
                    uncovered.append(item)

        if not ap_boxes and not uncovered and twys:
            # Airport has runways/taxiways in OSM/BGL but zero aprons and zero stands:
            # synthesize a bounding apron hull around ramp/spur taxiway endpoints clear of runways.
            ep_counts = {}
            for pts_m in tw_pts_m:
                for ep_m in (pts_m[0], pts_m[-1]):
                    ek = (round(ep_m[0] / 8.0), round(ep_m[1] / 8.0))
                    ep_counts[ek] = ep_counts.get(ek, 0) + 1
            for idx_t, pts_m in enumerate(tw_pts_m):
                for ep_m in (pts_m[0], pts_m[-1]):
                    ek = (round(ep_m[0] / 8.0), round(ep_m[1] / 8.0))
                    if ep_counts.get(ek, 0) == 1 and _min_rwy_dist(ep_m[0], ep_m[1]) > 62.0:
                        la, lo = c_lat + ep_m[1] / sy, c_lon + ep_m[0] / sx
                        uncovered.append((la, lo, ep_m[0], ep_m[1], 24.0, False, idx_t))

        cov_grid = {}
        for cov in covered:
            cov_grid.setdefault((int(cov[2] // 90.0), int(cov[3] // 90.0)), []).append(cov)

        unc_grid = {}
        for idx_u, u in enumerate(uncovered):
            unc_grid.setdefault((int(u[2] // 125.0), int(u[3] // 125.0)), []).append(idx_u)

        vis = [False] * len(uncovered)
        synth_aprons = []
        for i in range(len(uncovered)):
            if vis[i]:
                continue
            comp = []
            q = [i]
            vis[i] = True
            while q:
                cur = q.pop()
                comp.append(uncovered[cur])
                cx, cy = uncovered[cur][2], uncovered[cur][3]
                gx, gy = int(cx // 125.0), int(cy // 125.0)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for j in unc_grid.get((gx + dx, gy + dy), ()):
                            if not vis[j]:
                                nx, ny = uncovered[j][2], uncovered[j][3]
                                if (nx - cx) ** 2 + (ny - cy) ** 2 <= 125.0 ** 2:
                                    if _min_rwy_dist(0.5 * (cx + nx), 0.5 * (cy + ny)) > 55.0:
                                        vis[j] = True
                                        q.append(j)

            c_stands = sum(1 for it in comp if it[5])
            c_ways = len({it[6] for it in comp if it[6] >= 0})
            should_build = (
                (not ap_boxes and (c_stands >= 1 or len(comp) >= 2))
                or c_stands >= 2
                or c_ways >= 3
                or (c_stands >= 1 and c_ways >= 2)
            )
            if not should_build:
                continue

            support_pts = list(comp)
            seen_cov = set()
            for u in comp:
                gx, gy = int(u[2] // 90.0), int(u[3] // 90.0)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for cov in cov_grid.get((gx + dx, gy + dy), ()):
                            cid = id(cov)
                            if cid not in seen_cov and (cov[2] - u[2]) ** 2 + (cov[3] - u[3]) ** 2 <= 90.0 ** 2:
                                seen_cov.add(cid)
                                support_pts.append(cov)

            xs = [p[2] for p in support_pts]
            ys = [p[3] for p in support_pts]
            if max(max(xs) - min(xs), max(ys) - min(ys)) > 240.0:
                mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
                cxx = sum((x - mean_x) ** 2 for x in xs)
                cyy = sum((y - mean_y) ** 2 for y in ys)
                cxy = sum((xs[k] - mean_x) * (ys[k] - mean_y) for k in range(len(xs)))
                theta = 0.5 * math.atan2(2.0 * cxy, cxx - cyy)
                ux, uy = math.cos(theta), math.sin(theta)
                proj_vals = [(p[2] * ux + p[3] * uy, p) for p in support_pts]
                p_min = min(v for v, _ in proj_vals)
                p_max = max(v for v, _ in proj_vals)
                win_w, step_w = 240.0, 130.0
                slices = []
                cur_p = p_min
                while cur_p < p_max + 1e-3:
                    sub = [p for v, p in proj_vals if (cur_p - 20.0) <= v <= (cur_p + win_w + 20.0)]
                    if len(sub) >= 2:
                        slices.append(sub)
                    if cur_p + win_w >= p_max:
                        break
                    cur_p += step_w
            else:
                slices = [support_pts]

            for sl in slices:
                sample_xy = []
                for _, _, px, py, rbuf, _, _ in sl:
                    for k_ang in range(8):
                        ang = k_ang * (math.pi / 4.0)
                        bx = px + rbuf * math.cos(ang)
                        by = py + rbuf * math.sin(ang)
                        ok = True
                        for a, b in rwy_segs_m:
                            d, rx, ry = _seg_dist_m(bx, by, a, b)
                            if d < 50.0:
                                if d > 1.0:
                                    bx = rx + (bx - rx) * (50.0 / d)
                                    by = ry + (by - ry) * (50.0 / d)
                                else:
                                    ok = False
                                    break
                        if ok:
                            sample_xy.append((bx, by))
                hull = _convex_hull_xy(sample_xy)
                if len(hull) >= 3:
                    hull_ll = [_to_ll(hx, hy) for hx, hy in hull]
                    hull_ll.append(hull_ll[0])
                    synth_aprons.append({"name": "", "points": hull_ll, "_synth_hull": True})

        changed = bool(pruned_ap > 0 or pruned_tw > 0 or len(synth_aprons) > 0 or had_prev_synth)
        if changed:
            chart["aprons"] = synth_aprons + orig_aprons
            if pruned_tw > 0:
                chart["taxiways"] = twys
            if pruned_ap > 0 or pruned_tw > 0:
                all_la = [p[0] for r in rwys for p in (r.get("points") or [])] + [p[0] for t in twys for p in (t.get("points") or [])]
                all_lo = [p[1] for r in rwys for p in (r.get("points") or [])] + [p[1] for t in twys for p in (t.get("points") or [])]
                for s in stands:
                    if s.get("lat") is not None and s.get("lon") is not None:
                        all_la.append(float(s["lat"]))
                        all_lo.append(float(s["lon"]))
                if all_la and all_lo:
                    min_la, max_la = min(all_la), max(all_la)
                    min_lo, max_lo = min(all_lo), max(all_lo)
                    chart["center_lat"] = round(0.5 * (min_la + max_la), 6)
                    chart["center_lon"] = round(0.5 * (min_lo + max_lo), 6)
                    chart["bbox"] = [round(min_la, 6), round(min_lo, 6), round(max_la, 6), round(max_lo, 6)]
            chart.pop("_render_cache", None)
            icao_k = str(chart.get("icao") or "").strip().upper()
            if icao_k:
                self.graph_cache.pop(icao_k, None)

        chart["_apron_hull_sig"] = (2, len(chart.get("stands") or ()), len(chart.get("taxiways") or ()), len(chart.get("runways") or ()))

    def _parse_osm_geometry(self, icao, osm_data, center_lat, center_lon):
        runways = []
        raw_runway_ways = []
        taxiways = []
        aprons = []
        raw_open_aprons = []
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
                    ref = (tags.get("ref") or tags.get("name") or "").strip().upper()
                    ref = re.sub(r"^(?:RUNWAY|RWY)\s+", "", ref, flags=re.IGNORECASE).strip()
                    ref = re.sub(r"\s*[-;]\s*", "/", ref)
                    if ref:
                        ref = "/".join(re.sub(r"^(\d)([LRC]?)$", r"0\1\2", p.strip()) for p in ref.split("/") if p.strip())
                    if icao == "KCLT" and ref in ("01L/19R", "01R/19L", "18/36"):
                        avg_lon = sum(p[1] for p in pts) / len(pts)
                        if avg_lon < -80.960:
                            ref = "18R/36L"
                        elif avg_lon < -80.943:
                            ref = "18C/36C"
                        else:
                            ref = "18L/36R"
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
                    ap_name = tags.get("name:en") or tags.get("int_name") or tags.get("name") or tags.get("ref") or ""
                    if len(pts) >= 3:
                        gap_m = 0.0 if pts[0] == pts[-1] else haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
                        if gap_m < 12.0:
                            closed_pts = pts if pts[0] == pts[-1] else (pts + [pts[0]])
                            aprons.append({
                                "name": ap_name,
                                "points": closed_pts
                            })
                        else:
                            raw_open_aprons.append((ap_name, pts))
                    elif len(pts) == 2:
                        raw_open_aprons.append((ap_name, pts))

                elif aeroway in ("terminal", "hangar", "tower") or bldg in ("terminal", "hangar", "airport_terminal"):
                    if len(pts) >= 3:
                        if pts[0] == pts[-1] or haversine_m(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) < 12.0:
                            terminals.append({
                                "name": tags.get("name:en") or tags.get("int_name") or tags.get("name") or tags.get("ref") or "",
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
                        candidate_buildings.append((tags.get("name:en") or tags.get("int_name") or tags.get("name") or "", pts))

            elif etype == "relation":
                is_term_rel = aeroway in ("terminal", "hangar") or bldg in ("terminal", "hangar", "airport_terminal")
                is_apron_rel = aeroway == "apron"
                if is_term_rel or is_apron_rel:
                    outer_segs = []
                    for m in el.get("members", []):
                        if m.get("role") in ("outer", "") and m.get("geometry"):
                            pts = [[round(pt["lat"], 6), round(pt["lon"], 6)] for pt in m["geometry"] if "lat" in pt and "lon" in pt]
                            if len(pts) >= 2:
                                outer_segs.append(pts)
                    if outer_segs:
                        rel_name = tags.get("name:en") or tags.get("int_name") or tags.get("name") or tags.get("ref") or ""
                        rings = []
                        segs = [list(s_pts) for s_pts in outer_segs]
                        while segs:
                            cur = segs.pop(0)
                            changed = True
                            while changed and segs:
                                changed = False
                                best_m = None
                                best_d = 25.0
                                for idx_s, s_pts in enumerate(segs):
                                    d_es = 0.0 if cur[-1] == s_pts[0] else haversine_m(cur[-1][0], cur[-1][1], s_pts[0][0], s_pts[0][1])
                                    if d_es <= best_d:
                                        best_d, best_m = d_es, (idx_s, 0)
                                    d_ee = 0.0 if cur[-1] == s_pts[-1] else haversine_m(cur[-1][0], cur[-1][1], s_pts[-1][0], s_pts[-1][1])
                                    if d_ee <= best_d:
                                        best_d, best_m = d_ee, (idx_s, 1)
                                    d_se = 0.0 if cur[0] == s_pts[-1] else haversine_m(cur[0][0], cur[0][1], s_pts[-1][0], s_pts[-1][1])
                                    if d_se <= best_d:
                                        best_d, best_m = d_se, (idx_s, 2)
                                    d_ss = 0.0 if cur[0] == s_pts[0] else haversine_m(cur[0][0], cur[0][1], s_pts[0][0], s_pts[0][1])
                                    if d_ss <= best_d:
                                        best_d, best_m = d_ss, (idx_s, 3)
                                if best_m is not None:
                                    idx_s, mode = best_m
                                    s_pts = segs.pop(idx_s)
                                    if mode == 0:
                                        cur = cur + (s_pts[1:] if best_d <= 1.0 else s_pts)
                                    elif mode == 1:
                                        rev_s = list(reversed(s_pts))
                                        cur = cur + (rev_s[1:] if best_d <= 1.0 else rev_s)
                                    elif mode == 2:
                                        cur = (s_pts[:-1] if best_d <= 1.0 else s_pts) + cur
                                    else:
                                        rev_s = list(reversed(s_pts))
                                        cur = (rev_s[:-1] if best_d <= 1.0 else rev_s) + cur
                                    changed = True
                            if len(cur) >= 3:
                                rings.append(cur)
                        max_close_m = 180.0 if is_apron_rel else 35.0
                        for idx_r, ring_pts in enumerate(rings):
                            if len(ring_pts) >= 3:
                                gap_r = 0.0 if ring_pts[0] == ring_pts[-1] else haversine_m(ring_pts[0][0], ring_pts[0][1], ring_pts[-1][0], ring_pts[-1][1])
                                if gap_r <= max_close_m:
                                    closed_ring = ring_pts if ring_pts[0] == ring_pts[-1] else (ring_pts + [ring_pts[0]])
                                    item_obj = {
                                        "name": rel_name if (idx_r == 0 or len(closed_ring) >= 16) else "",
                                        "points": closed_ring
                                    }
                                    if is_term_rel:
                                        terminals.append(item_obj)
                                    else:
                                        aprons.append(item_obj)

        # Stitch and auto-close open aeroway=apron ways (when mappers split apron perimeters or left terminal-facing gaps)
        if raw_open_aprons:
            open_segs = [[nm, list(s_pts)] for nm, s_pts in raw_open_aprons]
            while open_segs:
                cur_nm, cur = open_segs.pop(0)
                changed = True
                while changed and open_segs:
                    changed = False
                    best_m = None
                    best_d = 25.0
                    for idx_o, (o_nm, o_pts) in enumerate(open_segs):
                        d_es = haversine_m(cur[-1][0], cur[-1][1], o_pts[0][0], o_pts[0][1])
                        if d_es <= best_d:
                            best_d, best_m = d_es, (idx_o, 0)
                        d_ee = haversine_m(cur[-1][0], cur[-1][1], o_pts[-1][0], o_pts[-1][1])
                        if d_ee <= best_d:
                            best_d, best_m = d_ee, (idx_o, 1)
                        d_se = haversine_m(cur[0][0], cur[0][1], o_pts[-1][0], o_pts[-1][1])
                        if d_se <= best_d:
                            best_d, best_m = d_se, (idx_o, 2)
                        d_ss = haversine_m(cur[0][0], cur[0][1], o_pts[0][0], o_pts[0][1])
                        if d_ss <= best_d:
                            best_d, best_m = d_ss, (idx_o, 3)
                    if best_m is not None:
                        idx_o, mode = best_m
                        o_nm, o_pts = open_segs.pop(idx_o)
                        if not cur_nm and o_nm:
                            cur_nm = o_nm
                        if mode == 0:
                            cur = cur + (o_pts[1:] if best_d <= 1.0 else o_pts)
                        elif mode == 1:
                            rev_o = list(reversed(o_pts))
                            cur = cur + (rev_o[1:] if best_d <= 1.0 else rev_o)
                        elif mode == 2:
                            cur = (o_pts[:-1] if best_d <= 1.0 else o_pts) + cur
                        else:
                            rev_o = list(reversed(o_pts))
                            cur = (rev_o[:-1] if best_d <= 1.0 else rev_o) + cur
                        changed = True
                if len(cur) >= 3:
                    gap_o = 0.0 if cur[0] == cur[-1] else haversine_m(cur[0][0], cur[0][1], cur[-1][0], cur[-1][1])
                    can_close_wide = False
                    if 260.0 < gap_o <= 850.0 and len(cur) >= 4:
                        chord_clear = True
                        for frac_c in (0.25, 0.5, 0.75):
                            clat_c = cur[-1][0] + frac_c * (cur[0][0] - cur[-1][0])
                            clon_c = cur[-1][1] + frac_c * (cur[0][1] - cur[-1][1])
                            for rw_chk in raw_runway_ways:
                                rpts_chk = rw_chk.get("points") or []
                                for kr_c in range(len(rpts_chk) - 1):
                                    if point_to_segment_projection(clat_c, clon_c, rpts_chk[kr_c][0], rpts_chk[kr_c][1], rpts_chk[kr_c + 1][0], rpts_chk[kr_c + 1][1])[3] < 48.0:
                                        chord_clear = False
                                        break
                                if not chord_clear:
                                    break
                            if not chord_clear:
                                break
                        can_close_wide = chord_clear
                    if gap_o <= 260.0 or can_close_wide:
                        closed_o = cur if cur[0] == cur[-1] else (cur + [cur[0]])
                        ref_lat = closed_o[0][0]
                        sx_a = 111320.0 * max(0.15, math.cos(math.radians(ref_lat)))
                        area2 = 0.0
                        for k_a in range(len(closed_o) - 1):
                            x1_a = (closed_o[k_a][1] - closed_o[0][1]) * sx_a
                            y1_a = (closed_o[k_a][0] - ref_lat) * 111320.0
                            x2_a = (closed_o[k_a + 1][1] - closed_o[0][1]) * sx_a
                            y2_a = (closed_o[k_a + 1][0] - ref_lat) * 111320.0
                            area2 += (x1_a * y2_a - x2_a * y1_a)
                        if 0.5 * abs(area2) >= 350.0:
                            aprons.append({"name": cur_nm, "points": closed_o})

        # Stitch collinear connected runway ways (e.g. displaced thresholds mapped as separate ways in OSM like LSGG RWY 04)
        merged_rwy = True
        while merged_rwy and len(raw_runway_ways) > 1:
            merged_rwy = False
            for i in range(len(raw_runway_ways)):
                for j in range(i + 1, len(raw_runway_ways)):
                    r1 = raw_runway_ways[i]
                    r2 = raw_runway_ways[j]
                    ref1 = (r1["ref"] or "").strip().upper()
                    ref2 = (r2["ref"] or "").strip().upper()
                    if ref1 and ref2 and ref1 != ref2:
                        p1_set = {p.strip() for p in ref1.replace("-", "/").split("/") if p.strip()}
                        p2_set = {p.strip() for p in ref2.replace("-", "/").split("/") if p.strip()}
                        if not (p1_set & p2_set):
                            continue
                    pts1 = r1["points"]
                    pts2 = r2["points"]
                    b1 = bearing_deg(pts1[0][0], pts1[0][1], pts1[-1][0], pts1[-1][1])
                    b2 = bearing_deg(pts2[0][0], pts2[0][1], pts2[-1][0], pts2[-1][1])
                    same_dir = angle_diff_deg(b1, b2) <= 12.0
                    opp_dir = angle_diff_deg(b1, (b2 + 180.0) % 360.0) <= 12.0
                    if not same_dir and not opp_dir:
                        continue
                    max_stitch_d = 85.0 if (ref1 and ref1 == ref2) else 15.0
                    d_ee_ss = haversine_m(pts1[-1][0], pts1[-1][1], pts2[0][0], pts2[0][1])
                    d_ee_ee = haversine_m(pts1[-1][0], pts1[-1][1], pts2[-1][0], pts2[-1][1])
                    d_ss_ee = haversine_m(pts1[0][0], pts1[0][1], pts2[-1][0], pts2[-1][1])
                    d_ss_ss = haversine_m(pts1[0][0], pts1[0][1], pts2[0][0], pts2[0][1])
                    combined_pts = None
                    if d_ee_ss <= max_stitch_d and same_dir:
                        combined_pts = pts1 + (pts2[1:] if d_ee_ss <= 2.0 else pts2)
                    elif d_ee_ee <= max_stitch_d and opp_dir:
                        combined_pts = pts1 + (list(reversed(pts2))[1:] if d_ee_ee <= 2.0 else list(reversed(pts2)))
                    elif d_ss_ee <= max_stitch_d and same_dir:
                        combined_pts = pts2 + (pts1[1:] if d_ss_ee <= 2.0 else pts1)
                    elif d_ss_ss <= max_stitch_d and opp_dir:
                        combined_pts = list(reversed(pts2)) + (pts1[1:] if d_ss_ss <= 2.0 else pts1)
                    if combined_pts is not None:
                        span1 = haversine_m(pts1[0][0], pts1[0][1], pts1[-1][0], pts1[-1][1])
                        span2 = haversine_m(pts2[0][0], pts2[0][1], pts2[-1][0], pts2[-1][1])
                        span_comb = haversine_m(combined_pts[0][0], combined_pts[0][1], combined_pts[-1][0], combined_pts[-1][1])
                        if span_comb <= max(span1, span2) + 5.0:
                            continue
                        best_ref = r1["ref"] if len(ref1) >= len(ref2) else r2["ref"]
                        raw_runway_ways[i] = {
                            "ref": best_ref or r1["ref"] or r2["ref"],
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

        # Fallback 3: If airport still has 0 parking_position/gate nodes in OSM (e.g. LFMD Cannes-Mandelieu,
        # LFPN Toussus-le-Noble, LFPZ Saint-Cyr), synthesize well-spaced stands across its aprons and taxilanes.
        if not stands:
            stands = self._synthesize_apron_stands(aprons, taxiways, terminals, runways)

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
        long_rwys = [
            r for r in runways
            if r.get("length_m", 0) >= 1100.0
            and ("/" in r.get("ref", "") or re.match(r"^(?:0?[1-9]|[12]\d|3[0-6])[LRC]?$", r.get("ref", "")))
        ]
        if long_rwys:
            runways = long_rwys

        # Collect available runway designators sorted nicely
        rwy_ids = []
        for rwy in sorted(runways, key=lambda r: -r.get("length_m", 0)):
            for end_id in rwy.get("ends", {}).keys():
                if end_id not in rwy_ids:
                    rwy_ids.append(end_id)

        res_chart = {
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
        self._ensure_complete_apron_surfaces(res_chart)
        return res_chart

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
            rwy_bboxes = []
            for r in rwys:
                pts = r.get("points", [])
                if len(pts) >= 2:
                    lats_r = [p[0] for p in pts]
                    lons_r = [p[1] for p in pts]
                    rwy_bboxes.append((pts, min(lats_r) - 0.0005, max(lats_r) + 0.0005, min(lons_r) - 0.0008, max(lons_r) + 0.0008))
            mid_rwy_nodes = set()
            for idx, (nlat, nlon) in enumerate(nodes):
                for pts, min_la, max_la, min_lo, max_lo in rwy_bboxes:
                    if nlat < min_la or nlat > max_la or nlon < min_lo or nlon > max_lo:
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

        twy_edges_by_norm = {}
        spatial_grid = {}
        for u_idx, (nlat, nlon) in enumerate(nodes):
            edges = adj.get(u_idx)
            if not edges:
                continue
            is_rwy_only = all(e[4] == "runway" for e in edges)
            cell_k = (int(math.floor(nlat / 0.002)), int(math.floor(nlon / 0.002)))
            spatial_grid.setdefault(cell_k, []).append((u_idx, nlat, nlon, is_rwy_only))
            for v_idx, _, _, ref, etype in edges:
                if etype != "runway" and ref:
                    rn = re.sub(r'[\s_\-]+', '', str(ref)).upper()
                    if rn and not rn.startswith("RWY"):
                        twy_edges_by_norm.setdefault(rn, []).append((u_idx, v_idx, ref))

        graph = {
            "nodes": nodes,
            "adj": adj,
            "feeder_refs": feeder_refs,
            "collector_refs": collector_refs,
            "link_refs": link_refs,
            "twy_edges_by_norm": twy_edges_by_norm,
            "spatial_grid": spatial_grid,
            "_rwy_exit_refs_cache": {},
        }
        if icao:
            self.graph_cache[icao] = graph
        return graph

    def _get_runway_exit_refs(self, graph, target_rwy_obj):
        """
        Returns the set of normalized taxiway refs (e.g. {'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'P9'})
        that act as dedicated runway turnoff exits for `target_rwy_obj` (connected to the runway
        centerline within 14m and extending <= 315m from the runway centerline).
        """
        if not target_rwy_obj:
            return set()
        rwy_cache = graph.get("_rwy_exit_refs_cache")
        rwy_cache_key = id(target_rwy_obj)
        if rwy_cache is not None and rwy_cache_key in rwy_cache:
            return rwy_cache[rwy_cache_key]
        pts = target_rwy_obj.get("points") or []
        if len(pts) < 2:
            return set()
        nodes = graph["nodes"]
        adj = graph["adj"]

        def _d_rwy(lat, lon):
            return min(
                point_to_segment_projection(lat, lon, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])[3]
                for i in range(len(pts) - 1)
            )

        cand_refs = set()
        for u, (nlat, nlon) in enumerate(nodes):
            edges_u = adj.get(u, ())
            if not any(e[4] == "runway" for e in edges_u):
                continue
            if _d_rwy(nlat, nlon) <= 14.0:
                for _, _, _, ref, et in edges_u:
                    if et != "runway" and ref and not str(ref).upper().startswith("RWY"):
                        cand_refs.add(ref)
        if not cand_refs:
            return set()

        max_d_by_ref = {}
        for u, edges_u in adj.items():
            nlat, nlon = nodes[u]
            d_u = None
            for _, _, _, ref, et in edges_u:
                if et != "runway" and ref in cand_refs:
                    if d_u is None:
                        d_u = _d_rwy(nlat, nlon)
                    if d_u > max_d_by_ref.get(ref, 0.0):
                        max_d_by_ref[ref] = d_u

        res_refs = {
            re.sub(r'[\s_\-]+', '', str(r)).upper()
            for r, max_d in max_d_by_ref.items()
            if max_d <= 315.0
        }
        if rwy_cache is not None:
            rwy_cache[rwy_cache_key] = res_refs
        return res_refs

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
        gate_lon=None,
        is_live_rollout=False
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
        Also stores `self._last_exit_out_bearing` and `self._last_exit_ref` so `_astar_path` leaves the runway along the chosen exit branch.
        """
        self._last_exit_out_bearing = None
        self._last_exit_ref = None
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
        best_out_ref = None
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
                for _ in range(18):
                    clat, clon = nodes[cur]
                    d_cur_rwy = _dist_to_rwy(clat, clon)
                    if d_cur_rwy >= 58.0:
                        break
                    next_cands = []
                    for nb, _, _, nref, net in adj.get(cur, []):
                        if nb not in visited and net != "runway":
                            d_nb = _dist_to_rwy(nodes[nb][0], nodes[nb][1])
                            same_ref = 1 if (out_ref and nref == out_ref) else 0
                            min_allow_d = (d_cur_rwy - 4.0) if same_ref else (d_cur_rwy - 1.0)
                            if d_nb > min_allow_d:
                                next_cands.append((same_ref, d_nb, nb, nref))
                    if not next_cands:
                        break
                    next_cands.sort(reverse=True)
                    _, _, cur, nref = next_cands[0]
                    if not out_ref and nref:
                        out_ref = nref
                    visited.add(cur)

                clat, clon = nodes[cur]
                if _dist_to_rwy(clat, clon) < 22.0:
                    # Branch never leaves the runway strip (e.g. fillet segment curving back onto runway)
                    continue

                out_brg = bearing_deg(nlat, nlon, clat, clon)
                turn_deg = angle_diff_deg(rwy_hdg, out_brg)

                matches_pref = False
                if pref_norm and turn_deg <= 105.0:
                    if re.sub(r'[\s_\-]+', '', (out_ref or "")).upper() == pref_norm:
                        matches_pref = True
                    elif re.sub(r'[\s_\-]+', '', (ref or "")).upper() == pref_norm:
                        matches_pref = True

                eff_min_rollout = min_rollout_m if is_live_rollout else (min(min_rollout_m, 400.0) if matches_pref else min_rollout_m)
                if d_from_thresh < eff_min_rollout:
                    continue

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
                    if is_live_rollout:
                        # During live landing rollout, stay locked onto the immediate upcoming high-speed exit
                        # until the aircraft actually passes it
                        rollout_cost = (d_from_thresh - eff_min_rollout) * 0.90
                    else:
                        # Prefer the first high-speed exit in the planned rollout zone
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
                    best_out_ref = out_ref or ref

        self._last_exit_out_bearing = best_out_brg
        self._last_exit_ref = best_out_ref
        return best_node

    def _find_nearest_node(self, graph, lat, lon, prefer_non_runway=True, max_dist_m=600.0):
        sp_grid = graph.get("spatial_grid")
        best_idx = None
        best_score = float('inf')

        if sp_grid is not None:
            dlat = min(0.015, (max_dist_m / 110500.0) + 0.0002)
            cos_l = max(0.15, math.cos(math.radians(lat)))
            dlon = min(0.02, (max_dist_m / (110500.0 * cos_l)) + 0.0003)
            r0 = int(math.floor((lat - dlat) / 0.002))
            r1 = int(math.floor((lat + dlat) / 0.002))
            c0 = int(math.floor((lon - dlon) / 0.002))
            c1 = int(math.floor((lon + dlon) / 0.002))
            for r_c in range(r0, r1 + 1):
                for c_c in range(c0, c1 + 1):
                    bucket = sp_grid.get((r_c, c_c))
                    if not bucket:
                        continue
                    for idx, nlat, nlon, is_rwy_only in bucket:
                        if abs(nlat - lat) > 0.015 or abs(nlon - lon) > 0.02:
                            continue
                        d = haversine_m(lat, lon, nlat, nlon)
                        if d > max_dist_m:
                            continue
                        score = d + (350.0 if (prefer_non_runway and is_rwy_only) else 0.0)
                        if score < best_score or (score == best_score and (best_idx is None or idx < best_idx)):
                            best_score = score
                            best_idx = idx
            return best_idx

        nodes = graph["nodes"]
        adj = graph["adj"]
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
        twy_by_norm = graph.get("twy_edges_by_norm")
        via_nodes = set()
        if twy_by_norm is not None:
            for u, v, _ in twy_by_norm.get(last_via_norm, ()):
                via_nodes.add(u)
                via_nodes.add(v)
        else:
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

        # If atc_taxi_via has a preceding taxiway (e.g. W44 -> W45 on LFPO RWY 06), verify that best_node
        # is not on the backwards stub behind the junction when the taxiway continues forward toward the threshold
        if best_node is not None and len(atc_taxi_via) >= 2:
            prev_via_norm = ""
            found_last = False
            for tok in reversed(atc_taxi_via):
                c = re.sub(r'[\s_\-]+', '', str(tok or "")).upper()
                if not c or c.startswith("RWY"):
                    continue
                if not found_last and c == last_via_norm:
                    found_last = True
                    continue
                if c != last_via_norm:
                    prev_via_norm = c
                    break
            if prev_via_norm:
                prev_nodes = set()
                if twy_by_norm is not None:
                    for u_p, v_p, _ in twy_by_norm.get(prev_via_norm, ()):
                        prev_nodes.add(u_p)
                        prev_nodes.add(v_p)
                else:
                    for u_p, edges_p in adj.items():
                        for v_p, _, _, ref_p, et_p in edges_p:
                            if et_p != "runway" and re.sub(r'[\s_\-]+', '', str(ref_p or "")).upper() == prev_via_norm:
                                prev_nodes.add(u_p)
                                prev_nodes.add(v_p)
                junc_nodes = via_nodes & prev_nodes
                if junc_nodes:
                    junc_d_th = min(haversine_m(nodes[j][0], nodes[j][1], thresh_lat, thresh_lon) for j in junc_nodes)
                    best_d_th = haversine_m(nodes[best_node][0], nodes[best_node][1], thresh_lat, thresh_lon)
                    min_via_d_th = min(haversine_m(nodes[vn][0], nodes[vn][1], thresh_lat, thresh_lon) for vn in via_nodes)
                    if best_d_th > junc_d_th + 15.0 and min_via_d_th < junc_d_th - 25.0:
                        return None

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
        sp_grid = graph.get("spatial_grid")
        if sp_grid is not None:
            gr0 = int(math.floor(gate_lat / 0.002))
            gc0 = int(math.floor(gate_lon / 0.002))
            cand_nodes = [
                (idx, nlat, nlon)
                for dr in (-1, 0, 1)
                for dc in (-1, 0, 1)
                for idx, nlat, nlon, _ in sp_grid.get((gr0 + dr, gc0 + dc), ())
            ]
        else:
            cand_nodes = list(enumerate(nodes))
            cand_nodes = [(idx, pt[0], pt[1]) for idx, pt in cand_nodes]

        if mode == "arrival":
            # Look for a node within 42m that has an incoming edge aligned with gate_hdg
            # and sits upstream of the stand along gate_hdg so the aircraft rolls straight in.
            best_up_idx = None
            best_up_score = float('inf')
            for idx, nlat, nlon in cand_nodes:
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
                    if score < best_up_score or (score == best_up_score and (best_up_idx is None or idx < best_up_idx)):
                        best_up_score = score
                        best_up_idx = idx
            if best_up_idx is not None:
                return best_up_idx

        elif mode == "departure" and no_pushback:
            # For drive-through stands (pushback=0), pick the node downstream ahead of the nose along gate_hdg
            best_dn_idx = None
            best_dn_score = float('inf')
            for idx, nlat, nlon in cand_nodes:
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
                    if score < best_dn_score or (score == best_dn_score and (best_dn_idx is None or idx < best_dn_idx)):
                        best_dn_score = score
                        best_dn_idx = idx
            if best_dn_idx is not None:
                return best_dn_idx

        return fallback

    def _astar_single_leg(self, graph, start_idx, goal_idx, allow_runway_start=False, goal_in_heading=None, start_out_heading=None, atc_taxi_via=None, strict_start_heading=True):
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
        if start_out_heading is not None and strict_start_heading:
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
                        turn_penalty = 2600.0  # Strong penalty against U-turns / hairpin turns
                    elif turn_deg > 98.0:
                        turn_penalty = 180.0
                elif u == start_idx and start_out_heading is not None:
                    diff_start = angle_diff_deg(out_bearing, start_out_heading)
                    if diff_start > 130.0:
                        turn_penalty += 2500.0
                    elif enforce_start_hdg and diff_start > 65.0:
                        turn_penalty += 2500.0
                    elif diff_start > 98.0:
                        turn_penalty += 180.0

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
                next_ref = ref if ref else last_ref

                actual_edge_cost = dist_m if (allow_runway_start and etype == "runway" and g < 600.0) else edge_cost
                if not ref and last_ref and etype != "runway" and not last_ref_u.startswith("RWY"):
                    actual_edge_cost *= 2.0
                if via_set and etype == "runway" and not (allow_runway_start and g < 600.0):
                    actual_edge_cost *= 8.0
                elif via_set and etype != "runway":
                    if ref_norm and ref_norm in via_set:
                        actual_edge_cost *= 0.12
                    elif ref_norm and not ref_u.startswith("RWY"):
                        # Strongly penalize deviating onto a named taxiway not in ATC's 'via' clearance
                        actual_edge_cost *= 5.5
                        if ref != last_ref:
                            turn_penalty += 550.0
                        if has_via_link and (ref_u in link_refs or ref_u.startswith("LINK")):
                            turn_penalty += 450.0

                ng = g + actual_edge_cost + turn_penalty
                next_key = (v, u, next_ref)
                if ng < best_g.get(next_key, float('inf')):
                    best_g[next_key] = ng
                    came_from[next_key] = (state_key, ref)
                    h = haversine_m(vlat, vlon, glat, glon) * (0.40 if via_set else 1.0)
                    heapq.heappush(open_heap, (ng + h, ng, v, u, next_ref))

        return [], []

    def _astar_path(self, graph, start_idx, goal_idx, allow_runway_start=False, goal_in_heading=None, start_out_heading=None, atc_taxi_via=None):
        coords, edge_refs = self._astar_single_leg(
            graph, start_idx, goal_idx,
            allow_runway_start=allow_runway_start,
            goal_in_heading=goal_in_heading,
            start_out_heading=start_out_heading,
            atc_taxi_via=atc_taxi_via
        )
        if not atc_taxi_via or start_idx is None or goal_idx is None or start_idx == goal_idx:
            return coords, edge_refs

        # Check if all requested taxiways in `atc_taxi_via` that exist in the airport graph were visited in order
        req_norms = []
        for t in atc_taxi_via:
            tn = re.sub(r'[\s_\-]+', '', str(t or "")).upper()
            if tn and (not req_norms or req_norms[-1] != tn):
                req_norms.append(tn)
        if not req_norms:
            return coords, edge_refs

        nodes = graph["nodes"]
        adj = graph["adj"]
        twy_edges = graph.get("twy_edges_by_norm")
        if twy_edges is None:
            twy_edges = {}
            for u_idx, edges in adj.items():
                for v_idx, _, _, ref, etype in edges:
                    if etype != "runway" and ref:
                        rn = re.sub(r'[\s_\-]+', '', str(ref)).upper()
                        if rn and not rn.startswith("RWY"):
                            twy_edges.setdefault(rn, []).append((u_idx, v_idx, ref))

        valid_req = [rn for rn in req_norms if rn in twy_edges]
        if not valid_req:
            return coords, edge_refs

        seq_idx = 0
        compressed_single = self._compress_taxiway_refs(edge_refs)
        for er in compressed_single:
            er_n = re.sub(r'[\s_\-]+', '', str(er or "")).upper()
            if seq_idx < len(valid_req) and er_n == valid_req[seq_idx]:
                seq_idx += 1
        if seq_idx == len(valid_req) and len(coords) >= 2:
            return coords, edge_refs

        # Multi-waypoint sequential A* routing through each requested taxiway in `valid_req`
        glat, glon = nodes[goal_idx]
        cur_node = start_idx
        cur_out_hdg = start_out_heading
        all_coords = [[nodes[start_idx][0], nodes[start_idx][1]]]
        all_refs = []

        for idx_w, rn in enumerate(valid_req):
            if idx_w > 0 and cur_node != goal_idx:
                rem_req = valid_req[idx_w:]
                rem_coords, rem_refs = self._astar_single_leg(
                    graph, cur_node, goal_idx,
                    allow_runway_start=False,
                    start_out_heading=cur_out_hdg,
                    goal_in_heading=goal_in_heading,
                    atc_taxi_via=rem_req,
                    strict_start_heading=(cur_node == start_idx)
                )
                if len(rem_coords) >= 2:
                    rem_comp = self._compress_taxiway_refs(rem_refs)
                    r_idx = 0
                    for er in rem_comp:
                        er_n = re.sub(r'[\s_\-]+', '', str(er or "")).upper()
                        if r_idx < len(rem_req) and er_n == rem_req[r_idx]:
                            r_idx += 1
                    if r_idx == len(rem_req):
                        all_coords.extend(rem_coords[1:])
                        all_refs.extend(rem_refs)
                        cur_node = goal_idx
                        break

            c_lat, c_lon = nodes[cur_node]
            prev_rn = valid_req[idx_w - 1] if idx_w > 0 else None
            prev_nodes_set = {u_p for u_p, v_p, _ in twy_edges.get(prev_rn, ())} | {v_p for u_p, v_p, _ in twy_edges.get(prev_rn, ())} if prev_rn else set()

            # Target after this taxiway (junction/entry node of next requested taxiway, or final goal_idx)
            if idx_w + 1 < len(valid_req):
                nxt_edges = twy_edges[valid_req[idx_w + 1]]
                cur_rn_nodes = {u_c for u_c, v_c, _ in twy_edges[rn]} | {v_c for u_c, v_c, _ in twy_edges[rn]}
                nxt_rn_nodes = {u_n for u_n, v_n, _ in nxt_edges} | {v_n for u_n, v_n, _ in nxt_edges}
                junc_nodes = cur_rn_nodes & nxt_rn_nodes
                if junc_nodes:
                    best_j = min(
                        junc_nodes,
                        key=lambda n_i: 0.70 * haversine_m(c_lat, c_lon, nodes[n_i][0], nodes[n_i][1]) + 0.50 * haversine_m(nodes[n_i][0], nodes[n_i][1], glat, glon)
                    )
                    n_lat, n_lon = nodes[best_j]
                else:
                    best_nxt = min(
                        nxt_edges,
                        key=lambda e: 0.75 * haversine_m(c_lat, c_lon, nodes[e[0]][0], nodes[e[0]][1]) + 0.45 * haversine_m(nodes[e[0]][0], nodes[e[0]][1], glat, glon)
                    )
                    n_lat, n_lon = nodes[best_nxt[0]]
            else:
                n_lat, n_lon = glat, glon

            d_cur_goal = haversine_m(c_lat, c_lon, n_lat, n_lon)
            best_edge = None
            best_score = float('inf')
            for u_cand, v_cand, raw_ref in twy_edges[rn]:
                if u_cand == cur_node and v_cand == cur_node:
                    continue
                ulat, ulon = nodes[u_cand]
                vlat, vlon = nodes[v_cand]
                d_u_goal = haversine_m(ulat, ulon, n_lat, n_lon)
                d_v_goal = haversine_m(vlat, vlon, n_lat, n_lon)
                sc = 0.50 * haversine_m(c_lat, c_lon, ulat, ulon) + 1.0 * d_v_goal
                if prev_nodes_set and u_cand in prev_nodes_set and v_cand in prev_nodes_set:
                    sc += 550.0
                # Penalize edges oriented away from the target direction
                if d_v_goal > d_u_goal + 2.0:
                    sc += 1200.0 + (d_v_goal - d_u_goal)
                # Penalize taxiway segments situated in the opposite direction behind cur_node
                if d_u_goal > d_cur_goal + 90.0:
                    sc += 2.2 * (d_u_goal - d_cur_goal)
                if sc < best_score:
                    best_score = sc
                    best_edge = (u_cand, v_cand, raw_ref)

            if not best_edge:
                continue
            u_best, v_best, raw_ref = best_edge
            local_via = [ prev_rn, rn ] if prev_rn else [ rn ]
            leg_coords, leg_refs = self._astar_single_leg(
                graph, cur_node, v_best,
                allow_runway_start=(allow_runway_start and cur_node == start_idx),
                start_out_heading=cur_out_hdg,
                atc_taxi_via=local_via,
                strict_start_heading=(cur_node == start_idx)
            )
            visited_rn = any(re.sub(r'[\s_\-]+', '', str(r or "")).upper() == rn for r in leg_refs)
            if not visited_rn and u_best != cur_node:
                leg_coords_u, leg_refs_u = self._astar_single_leg(
                    graph, cur_node, u_best,
                    allow_runway_start=(allow_runway_start and cur_node == start_idx),
                    start_out_heading=cur_out_hdg,
                    atc_taxi_via=local_via,
                    strict_start_heading=(cur_node == start_idx)
                )
                if len(leg_coords_u) >= 2:
                    leg_coords = leg_coords_u + [[nodes[v_best][0], nodes[v_best][1]]]
                    leg_refs = leg_refs_u + [raw_ref]

            if len(leg_coords) >= 2:
                all_coords.extend(leg_coords[1:])
                all_refs.extend(leg_refs)
                cur_node = v_best
                cur_out_hdg = bearing_deg(leg_coords[-2][0], leg_coords[-2][1], leg_coords[-1][0], leg_coords[-1][1])

        if cur_node != goal_idx:
            last_rn = valid_req[-1]
            c_lat, c_lon = nodes[cur_node]
            d_c_goal = haversine_m(c_lat, c_lon, glat, glon)
            has_fwd_last_rn = False
            for nb, _, _, ref, etype in adj.get(cur_node, []):
                if etype != "runway" and re.sub(r'[\s_\-]+', '', str(ref or "")).upper() == last_rn:
                    if haversine_m(nodes[nb][0], nodes[nb][1], glat, glon) < d_c_goal:
                        has_fwd_last_rn = True
                        break
            fin_coords, fin_refs = self._astar_single_leg(
                graph, cur_node, goal_idx,
                allow_runway_start=False,
                start_out_heading=cur_out_hdg,
                goal_in_heading=goal_in_heading,
                atc_taxi_via=[last_rn] if has_fwd_last_rn else None,
                strict_start_heading=(cur_node == start_idx)
            )
            if len(fin_coords) >= 2:
                all_coords.extend(fin_coords[1:])
                all_refs.extend(fin_refs)

        if len(all_coords) >= 2 and len(all_refs) == len(all_coords) - 1:
            return all_coords, all_refs
        return coords, edge_refs

    def prune_conflicting_taxi_via(
        self,
        chart,
        mode,
        gate_lat,
        gate_lon,
        runway_id,
        prev_via_list,
        new_twy,
        user_lat=None,
        user_lon=None,
        user_on_ground=None,
        gate_hdg=None,
        no_pushback=False
    ):
        """
        Ensures mutually exclusive runway holding points / entries (e.g. W33 vs W31 at LFPO)
        and competing parallel taxiway branches (e.g. L4 vs L3, LC vs LF) automatically
        replace each other when clicked by the user, preventing impossible U-turns or
        simultaneous dual-entry selections. Also orders the resulting sequence topologically
        along the route direction.
        """
        new_u = str(new_twy or "").strip().upper()
        new_norm = re.sub(r'[\s_\-]+', '', new_u)
        if not new_norm:
            return list(prev_via_list or [])
        if not prev_via_list or not chart or gate_lat is None or gate_lon is None:
            return [new_u]

        avail_rwys = chart.get("available_runways", [])
        if not runway_id or runway_id not in avail_rwys:
            matched = None
            if runway_id:
                r_clean = runway_id.strip().upper()
                for cand in avail_rwys:
                    if cand == r_clean or cand.lstrip("0") == r_clean.lstrip("0"):
                        matched = cand
                        break
            runway_id = matched or (avail_rwys[0] if avail_rwys else "RWY")

        target_rwy_obj = None
        target_end_info = None
        for rwy in chart.get("runways", []):
            if runway_id in rwy.get("ends", {}):
                target_rwy_obj = rwy
                target_end_info = rwy["ends"][runway_id]
                break

        graph = self._get_or_build_graph(chart)
        if not graph["nodes"] or not target_end_info:
            return [t for t in prev_via_list if re.sub(r'[\s_\-]+', '', str(t).upper()) != new_norm] + [new_u]

        thresh_lat = target_end_info["lat"]
        thresh_lon = target_end_info["lon"]
        if mode == "arrival":
            end_lat = target_end_info.get("end_lat", thresh_lat)
            end_lon = target_end_info.get("end_lon", thresh_lon)
            rwy_len = haversine_m(thresh_lat, thresh_lon, end_lat, end_lon)
            rollout_dist = min(max(1450.0, rwy_len * 0.62), max(1000.0, rwy_len - 300.0))
            rwy_hdg = target_end_info.get("heading", 0.0)
            default_rwy_node = self._find_best_runway_exit_node(
                graph, target_rwy_obj, thresh_lat, thresh_lon, rwy_hdg,
                target_rollout_m=rollout_dist,
                min_rollout_m=min(1150.0, rwy_len * 0.42),
                preferred_exit_ref=None,
                gate_lat=gate_lat,
                gate_lon=gate_lon
            )
        else:
            default_rwy_node = None
        if default_rwy_node is None:
            default_rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=True, max_dist_m=450.0)
        if default_rwy_node is None:
            default_rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=False, max_dist_m=600.0)

        gate_node = self._find_directional_gate_node(
            graph, gate_lat, gate_lon, gate_hdg=gate_hdg, mode=mode, no_pushback=no_pushback
        )
        user_at_airport = False
        if user_lat is not None and user_lon is not None:
            if haversine_m(user_lat, user_lon, chart.get("center_lat", gate_lat), chart.get("center_lon", gate_lon)) < 10500.0:
                if user_on_ground is not False:
                    user_at_airport = True

        if mode == "departure":
            start_node = self._find_nearest_node(graph, user_lat, user_lon, prefer_non_runway=True, max_dist_m=500.0) if user_at_airport else gate_node
            dep_out_hdg = None if user_at_airport else (gate_hdg if no_pushback else None)
        else:
            start_node = default_rwy_node
            dep_out_hdg = None

        if start_node is None or default_rwy_node is None:
            return [t for t in prev_via_list if re.sub(r'[\s_\-]+', '', str(t).upper()) != new_norm] + [new_u]

        nodes = graph["nodes"]
        adj = graph["adj"]

        def _is_rwy_touching_node(n_idx):
            return any(e[4] == "runway" for e in adj.get(n_idx, ()))

        def _non_rwy_neighbors(twy_norm):
            t_nodes = set()
            rwy_cross_nodes = set()
            for u_i, edges in adj.items():
                for v_i, _, _, r_e, et in edges:
                    if et != "runway" and re.sub(r'[\s_\-]+', '', str(r_e or "")).upper() == twy_norm:
                        if not _is_rwy_touching_node(u_i):
                            t_nodes.add(u_i)
                        else:
                            rwy_cross_nodes.add(u_i)
                        if not _is_rwy_touching_node(v_i):
                            t_nodes.add(v_i)
                        else:
                            rwy_cross_nodes.add(v_i)
            # Expand across unnamed fillet chains (up to 12 hops) off the runway
            frontier = set(t_nodes)
            visited_un = set(t_nodes)
            for _ in range(12):
                nxt_f = set()
                for u_i in frontier:
                    for v_i, _, _, r_e, et in adj.get(u_i, ()):
                        if et != "runway" and not r_e and v_i not in visited_un and not _is_rwy_touching_node(v_i):
                            visited_un.add(v_i)
                            nxt_f.add(v_i)
                if not nxt_f:
                    break
                frontier = nxt_f
            nbrs = set()
            for u_i in visited_un:
                for v_i, _, _, r_e, et in adj.get(u_i, ()):
                    if et != "runway" and r_e:
                        rn_e = re.sub(r'[\s_\-]+', '', str(r_e)).upper()
                        if rn_e and not rn_e.startswith("RWY") and rn_e != twy_norm:
                            nbrs.add(rn_e)
            # Also include direct straight-across runway-crossing continuations (e.g. R7 -> E6 at LSZH)
            # while excluding acute same-side high-speed exit merges on the centerline (e.g. W43/W45 at LFPO)
            for rc_node in rwy_cross_nodes:
                rwy_brgs = [
                    bearing_deg(nodes[rc_node][0], nodes[rc_node][1], nodes[rv][0], nodes[rv][1])
                    for rv, _, _, _, et in adj.get(rc_node, ()) if et == "runway"
                ]
                for v1, _, _, r1, et1 in adj.get(rc_node, ()):
                    if et1 == "runway" or re.sub(r'[\s_\-]+', '', str(r1 or "")).upper() != twy_norm:
                        continue
                    b_in = bearing_deg(nodes[v1][0], nodes[v1][1], nodes[rc_node][0], nodes[rc_node][1])
                    if rwy_brgs and min(angle_diff_deg(b_in, rb) for rb in rwy_brgs) < 25.0:
                        continue
                    for v2, _, _, r2, et2 in adj.get(rc_node, ()):
                        if et2 == "runway" or not r2:
                            continue
                        rn2 = re.sub(r'[\s_\-]+', '', str(r2)).upper()
                        if not rn2 or rn2.startswith("RWY") or rn2 == twy_norm:
                            continue
                        b_out = bearing_deg(nodes[rc_node][0], nodes[rc_node][1], nodes[v2][0], nodes[v2][1])
                        if rwy_brgs and min(angle_diff_deg(b_out, rb) for rb in rwy_brgs) < 25.0:
                            continue
                        if angle_diff_deg(b_in, b_out) <= 25.0:
                            nbrs.add(rn2)
            return nbrs

        def _has_sharp_reversal(pts, refs):
            seg_brgs = []
            for i in range(len(pts) - 1):
                d_s = haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                if d_s > 2.0:
                    seg_brgs.append((i, pts[i][0], pts[i][1], bearing_deg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])))
            for k in range(1, len(seg_brgs)):
                if angle_diff_deg(seg_brgs[k - 1][3], seg_brgs[k][3]) > 135.0:
                    return True
            for k in range(len(seg_brgs)):
                _, lat_k, lon_k, brg_k = seg_brgs[k]
                for m in range(max(0, k - 90), k - 4):
                    _, lat_m, lon_m, brg_m = seg_brgs[m]
                    if haversine_m(lat_k, lon_k, lat_m, lon_m) < 25.0 and angle_diff_deg(brg_k, brg_m) > 125.0:
                        return True
            return False

        raw_new_hold = self._find_atc_departure_holding_node(graph, target_rwy_obj, thresh_lat, thresh_lon, [new_norm])
        new_hold = self._find_atc_departure_holding_node(graph, target_rwy_obj, thresh_lat, thresh_lon, list(prev_via_list) + [new_norm])
        active_rwy_node = new_hold
        if active_rwy_node is None and raw_new_hold is None:
            new_min_th = 99999.0
            for u_i, edges_i in adj.items():
                for _, _, _, r_e, et_e in edges_i:
                    if et_e != "runway" and re.sub(r'[\s_\-]+', '', str(r_e or "")).upper() == new_norm:
                        d_th = haversine_m(nodes[u_i][0], nodes[u_i][1], thresh_lat, thresh_lon)
                        if d_th < new_min_th:
                            new_min_th = d_th
            for ot in reversed(prev_via_list):
                oh = self._find_atc_departure_holding_node(graph, target_rwy_obj, thresh_lat, thresh_lon, [ot])
                if oh is not None:
                    d_oh_th = haversine_m(nodes[oh][0], nodes[oh][1], thresh_lat, thresh_lon)
                    if d_oh_th < new_min_th - 20.0:
                        active_rwy_node = oh
                        break
        if active_rwy_node is None:
            active_rwy_node = default_rwy_node

        leg_start = start_node if mode == "departure" else active_rwy_node
        leg_goal = active_rwy_node if mode == "departure" else gate_node

        def _path_len(pts):
            if len(pts) < 2:
                return 0.0
            return sum(haversine_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1))

        c_new, r_new = self._astar_path(
            graph, leg_start, leg_goal,
            start_out_heading=dep_out_hdg,
            atc_taxi_via=[new_u]
        )
        seq_new = [re.sub(r'[\s_\-]+', '', x).upper() for x in self._compress_taxiway_refs(r_new) if x]
        len_new = _path_len(c_new)

        # First check if new_u extends the existing custom sequence `prev_via_list` as a valid forward chain
        # (e.g. W2 -> LS -> W44 -> W45 -> W47 on LFPO RWY 06)
        chain_prev = []
        for idx_p, old_twy in enumerate(prev_via_list):
            old_u = str(old_twy or "").strip().upper()
            old_norm = re.sub(r'[\s_\-]+', '', old_u)
            if not old_norm or old_norm == new_norm:
                continue
            if old_norm in seq_new:
                chain_prev.append(old_u)
                continue
            old_hold = self._find_atc_departure_holding_node(graph, target_rwy_obj, thresh_lat, thresh_lon, [old_norm])
            if old_hold is not None and raw_new_hold is not None:
                # Both touch the active runway: allow chaining only if old_norm is a through-taxiway (>= 2 non-runway neighbors)
                # connected to the next taxiway in the chain, and the next taxiway is also a through-taxiway or closer to threshold
                old_nbrs = _non_rwy_neighbors(old_norm)
                nxt_norm = re.sub(r'[\s_\-]+', '', str(prev_via_list[idx_p + 1]).upper()) if idx_p + 1 < len(prev_via_list) else new_norm
                nxt_nbrs = _non_rwy_neighbors(nxt_norm)
                d_old_th = haversine_m(nodes[old_hold][0], nodes[old_hold][1], thresh_lat, thresh_lon)
                d_new_th = haversine_m(nodes[raw_new_hold][0], nodes[raw_new_hold][1], thresh_lat, thresh_lon)
                if len(old_nbrs) >= 2 and nxt_norm in old_nbrs and (len(nxt_nbrs) >= 2 or d_new_th < d_old_th - 60.0):
                    chain_prev.append(old_u)
                continue
            chain_prev.append(old_u)

        if chain_prev:
            last_prev_norm = re.sub(r'[\s_\-]+', '', chain_prev[-1]).upper()
            last_prev_nbrs = _non_rwy_neighbors(last_prev_norm)
            # Check if last_prev and new_norm are competing parallel connectors between the same taxiways (e.g. L4 vs L3, LC vs LF)
            is_parallel_competitor = False
            if new_norm not in last_prev_nbrs and last_prev_norm not in seq_new:
                c_lp, r_lp = self._astar_path(
                    graph, leg_start, leg_goal,
                    start_out_heading=dep_out_hdg,
                    atc_taxi_via=[chain_prev[-1]]
                )
                seq_lp = [re.sub(r'[\s_\-]+', '', x).upper() for x in self._compress_taxiway_refs(r_lp) if x]
                if new_norm not in seq_lp and last_prev_norm in seq_lp and new_norm in seq_new:
                    i_lp = seq_lp.index(last_prev_norm)
                    i_nw = seq_new.index(new_norm)
                    prev_lp = seq_lp[i_lp - 1] if i_lp > 0 else "START"
                    prev_nw = seq_new[i_nw - 1] if i_nw > 0 else "START"
                    next_lp = seq_lp[i_lp + 1] if i_lp + 1 < len(seq_lp) else "GOAL"
                    next_nw = seq_new[i_nw + 1] if i_nw + 1 < len(seq_new) else "GOAL"
                    if prev_lp == prev_nw or next_lp == next_nw:
                        is_parallel_competitor = True

            if not is_parallel_competitor:
                cand_chain = chain_prev + [new_u]
                c_ch, r_ch = self._astar_path(
                    graph, leg_start, leg_goal,
                    start_out_heading=dep_out_hdg,
                    atc_taxi_via=cand_chain
                )
                if len(c_ch) >= 2 and not _has_sharp_reversal(c_ch, r_ch):
                    return cand_chain

        kept = []
        for old_twy in chain_prev:
            old_u = str(old_twy or "").strip().upper()
            old_norm = re.sub(r'[\s_\-]+', '', old_u)
            if not old_norm or old_norm == new_norm:
                continue

            # If old_twy is naturally traversed on the direct route through new_twy, keep it
            if old_norm in seq_new:
                kept.append(old_u)
                continue

            # Check if new_twy is naturally traversed on the direct route through old_twy without a large detour
            c_old, r_old = self._astar_path(
                graph, leg_start, leg_goal,
                start_out_heading=dep_out_hdg,
                atc_taxi_via=[old_u]
            )
            seq_old = [re.sub(r'[\s_\-]+', '', x).upper() for x in self._compress_taxiway_refs(r_old) if x]
            len_old = _path_len(c_old)
            if new_norm in seq_old and len_old <= len_new + 260.0:
                kept.append(old_u)
                continue

        kept.append(new_u)

        # Sort surviving taxiways in topological progression order along the route
        if len(kept) >= 2:
            c_ref, r_ref = self._astar_path(
                graph, leg_start, leg_goal,
                start_out_heading=dep_out_hdg,
                atc_taxi_via=kept
            )
            seq_ref = [re.sub(r'[\s_\-]+', '', x).upper() for x in self._compress_taxiway_refs(r_ref) if x]
            s_lat, s_lon = graph["nodes"][leg_start]

            def _topo_key(twy_str):
                tn = re.sub(r'[\s_\-]+', '', twy_str).upper()
                if tn in seq_new:
                    return (1, float(seq_new.index(tn)))
                if tn in seq_ref:
                    return (1, float(seq_ref.index(tn)))
                th = self._find_atc_departure_holding_node(graph, target_rwy_obj, thresh_lat, thresh_lon, [tn])
                if th is not None:
                    d_th = haversine_m(nodes[th][0], nodes[th][1], thresh_lat, thresh_lon)
                    if mode == "departure":
                        return (2, -d_th)
                    return (0, d_th)
                # Fallback: minimum distance from leg_start to any node on this taxiway
                min_d = 99999.0
                for u_i, edges in adj.items():
                    for _, _, _, r_e, _ in edges:
                        if re.sub(r'[\s_\-]+', '', str(r_e or "")).upper() == tn:
                            d = haversine_m(s_lat, s_lon, nodes[u_i][0], nodes[u_i][1])
                            if d < min_d:
                                min_d = d
                return (1, min_d)

            kept.sort(key=_topo_key)

        return kept

    def _detect_arrival_state_and_exit(self, chart, graph, selected_rwy_id, user_lat, user_lon, user_hdg, user_gs, user_on_ground):
        """
        Determines whether the aircraft is at the arrival airport, which runway it landed on,
        and dynamically detects which high-speed exit / turnoff the pilot takes in real time!
        """
        icao = chart.get("icao", "")
        if user_lat is None or user_lon is None:
            return None

        dist_to_apt = haversine_m(user_lat, user_lon, chart.get("center_lat", 0), chart.get("center_lon", 0))
        if dist_to_apt > 12500.0:  # More than ~6.7 NM away -> still in flight / approach
            self.locked_arrival_exit.pop(icao, None)
            self.arr_vacated_runway.pop(icao, None)
            self._active_taxi_route_state.pop((icao, "arrival"), None)
            return None

        if user_on_ground is False and dist_to_apt > 2500.0:
            self.locked_arrival_exit.pop(icao, None)
            self.arr_vacated_runway.pop(icao, None)
            self._active_taxi_route_state.pop((icao, "arrival"), None)
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

        # Detect active turnoff onto a high-speed runway exit (diverging away from runway centerline)
        is_turning_off = (
            min_rwy_dist >= 1.2
            and (user_gs or 0.0) <= 45.0
            and user_hdg is not None
            and best_hdg_diff >= 11.0
        )
        if user_on_ground is not False and is_turning_off:
            self.arr_vacated_runway[icao] = True

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

        if 1.0 < min_rwy_dist <= 95.0 and not self.locked_arrival_exit.get(icao):
            # Find the taxiway exit ref right under the aircraft, weighted by heading alignment
            # so crossing opposite-QFU exits (e.g. C3 crossing C4 within 5m at EBBR) are never mis-locked
            nodes = graph["nodes"]
            adj = graph["adj"]
            best_exit_ref = None
            best_exit_sc = float('inf')
            for u_i, (ulat, ulon) in enumerate(nodes):
                if abs(ulat - user_lat) > 0.0012 or abs(ulon - user_lon) > 0.0018:
                    continue
                for v_i, _, _, ref, etype in adj.get(u_i, ()):
                    if u_i > v_i or etype == "runway" or not ref or str(ref).upper().startswith("RWY"):
                        continue
                    vlat, vlon = nodes[v_i]
                    _, _, _, d_seg = point_to_segment_projection(user_lat, user_lon, ulat, ulon, vlat, vlon)
                    if d_seg > 28.0:
                        continue
                    hdg_pen = 0.0
                    if user_hdg is not None:
                        ebrg = bearing_deg(ulat, ulon, vlat, vlon)
                        diff_e = min(
                            angle_diff_deg(user_hdg, ebrg),
                            angle_diff_deg(user_hdg, (ebrg + 180.0) % 360.0)
                        )
                        hdg_pen = diff_e * 0.35
                    sc = d_seg + hdg_pen
                    if sc < best_exit_sc:
                        best_exit_sc = sc
                        best_exit_ref = ref
            if best_exit_ref:
                self.locked_arrival_exit[icao] = best_exit_ref

        return {
            "state": "TAXI_IN",
            "active_rwy": best_rwy_end_id,
            "detected_exit": self.locked_arrival_exit.get(icao)
        }

    def _prune_passed_atc_taxi_via(self, graph, user_lat, user_lon, user_hdg, goal_node, atc_taxi_via):
        """
        Drops already-passed taxiways from the front of `atc_taxi_via` when the aircraft is
        actively taxiing so `_astar_path` never routes backwards to re-visit passed taxiways.
        """
        if not atc_taxi_via or user_lat is None or user_lon is None:
            return atc_taxi_via
        via_list = list(atc_taxi_via)
        if len(via_list) <= 1:
            return via_list

        nodes = graph["nodes"]
        adj = graph["adj"]
        via_norms = [re.sub(r'[\s_\-]+', '', str(x or "")).upper() for x in via_list]

        # 1. Find the taxiway edge directly under / beside the aircraft (within 32m)
        best_ref_norm = None
        best_sc = 32.0
        for u_i, (ulat, ulon) in enumerate(nodes):
            if abs(ulat - user_lat) > 0.0008 or abs(ulon - user_lon) > 0.0012:
                continue
            for v_i, _, _, ref, etype in adj.get(u_i, ()):
                if u_i > v_i or etype == "runway" or not ref:
                    continue
                rn = re.sub(r'[\s_\-]+', '', str(ref)).upper()
                if not rn or rn.startswith("RWY"):
                    continue
                vlat, vlon = nodes[v_i]
                _, _, _, d_seg = point_to_segment_projection(user_lat, user_lon, ulat, ulon, vlat, vlon)
                if d_seg > 32.0:
                    continue
                hdg_pen = 0.0
                if user_hdg is not None:
                    ebrg = bearing_deg(ulat, ulon, vlat, vlon)
                    diff_e = min(angle_diff_deg(user_hdg, ebrg), angle_diff_deg(user_hdg, (ebrg + 180.0) % 360.0))
                    hdg_pen = diff_e * 0.25
                sc = d_seg + hdg_pen
                if sc < best_sc:
                    best_sc = sc
                    best_ref_norm = rn

        if best_ref_norm and best_ref_norm in via_norms:
            match_indices = [idx for idx, vn in enumerate(via_norms) if vn == best_ref_norm]
            if len(match_indices) == 1:
                return via_list[match_indices[0]:]
            # Disambiguate repeated taxiway name (e.g. ['B', 'A29', 'Q', 'A', 'B']) by checking proximity to neighbor taxiways
            twy_edges_map = graph.get("twy_edges_by_norm") or {}
            best_idx = match_indices[0]
            best_nbr_dist = float('inf')
            for idx_m in match_indices:
                nbr_norms = set()
                if idx_m > 0:
                    nbr_norms.add(via_norms[idx_m - 1])
                if idx_m + 1 < len(via_norms):
                    nbr_norms.add(via_norms[idx_m + 1])
                min_d_nbr = float('inf')
                for nb_norm in nbr_norms:
                    for u_i, _, _ in twy_edges_map.get(nb_norm, ()):
                        ulat, ulon = nodes[u_i]
                        d_n = haversine_m(user_lat, user_lon, ulat, ulon)
                        if d_n < min_d_nbr:
                            min_d_nbr = d_n
                if min_d_nbr < best_nbr_dist:
                    best_nbr_dist = min_d_nbr
                    best_idx = idx_m
            return via_list[best_idx:]

        # 2. If on an unnamed intersection connector, drop prefix taxiways whose closest edges lie behind the aircraft
        twy_edges_map = graph.get("twy_edges_by_norm") or {}
        glat, glon = nodes[goal_node] if goal_node is not None and goal_node < len(nodes) else (user_lat, user_lon)
        d_user_goal = haversine_m(user_lat, user_lon, glat, glon)
        start_cut = 0
        while start_cut < len(via_list) - 1:
            rn0 = via_norms[start_cut]
            rn1 = via_norms[start_cut + 1]
            min_d0 = float('inf')
            min_d1 = float('inf')
            has_ahead_0 = False
            for u_i, v_i, _ in twy_edges_map.get(rn0, ()):
                if u_i > v_i:
                    continue
                ulat, ulon = nodes[u_i]
                vlat, vlon = nodes[v_i]
                plat, plon, _, d_s = point_to_segment_projection(user_lat, user_lon, ulat, ulon, vlat, vlon)
                if d_s < min_d0:
                    min_d0 = d_s
                if d_s <= 260.0:
                    if user_hdg is not None:
                        if angle_diff_deg(user_hdg, bearing_deg(user_lat, user_lon, plat, plon)) <= 85.0:
                            has_ahead_0 = True
                    elif haversine_m(plat, plon, glat, glon) < d_user_goal:
                        has_ahead_0 = True
            for u_i, v_i, _ in twy_edges_map.get(rn1, ()):
                if u_i > v_i:
                    continue
                ulat, ulon = nodes[u_i]
                vlat, vlon = nodes[v_i]
                _, _, _, d_s = point_to_segment_projection(user_lat, user_lon, ulat, ulon, vlat, vlon)
                if d_s < min_d1:
                    min_d1 = d_s
            if min_d1 <= 45.0 or (min_d1 < min_d0 and not has_ahead_0):
                start_cut += 1
            else:
                break
        return via_list[start_cut:]

    def _trim_passed_taxi_route(
        self,
        icao,
        mode,
        route_key,
        user_lat,
        user_lon,
        user_hdg,
        user_gs,
        compute_fresh_fn
    ):
        """
        Maintains monotonic forward progress along the active taxi route and trims all passed
        segments and intersections behind the aircraft so the track behind the aircraft disappears
        immediately as each intersection is crossed. Recomputes cleanly if the aircraft deviates > 40m.
        """
        state_key = (str(icao or "").upper(), str(mode or ""))
        st = self._active_taxi_route_state.get(state_key)

        def _project_onto_route(coords, min_idx=0):
            if not coords or len(coords) < 2:
                return None
            best_i = None
            best_sc = float('inf')
            best_info = None
            start_i = max(0, min(min_idx, len(coords) - 2))
            for i in range(start_i, len(coords) - 1):
                p0, p1 = coords[i], coords[i + 1]
                plat, plon, t, d_m = point_to_segment_projection(
                    user_lat, user_lon, p0[0], p0[1], p1[0], p1[1]
                )
                if d_m > 42.0:
                    continue
                seg_len = haversine_m(p0[0], p0[1], p1[0], p1[1])
                hdg_pen = 0.0
                hdg_diff = 0.0
                if user_hdg is not None and seg_len > 2.5:
                    s_brg = bearing_deg(p0[0], p0[1], p1[0], p1[1])
                    hdg_diff = angle_diff_deg(user_hdg, s_brg)
                    hdg_pen = hdg_diff * 0.18
                # Slight forward bias for the outgoing leg right after an intersection
                fwd_bonus = -3.0 if (d_m <= 20.0 and hdg_diff <= 45.0 and start_i < i <= start_i + 4) else 0.0
                sc = d_m + hdg_pen + fwd_bonus
                if sc < best_sc:
                    best_sc = sc
                    best_i = i
                    best_info = (i, plat, plon, t, d_m, hdg_diff)
            return best_info

        proj = None
        if st and st.get("key") == route_key and len(st.get("coords") or []) >= 2:
            proj = _project_onto_route(st["coords"], min_idx=max(0, st.get("last_seg_idx", 0) - 1))

        if proj is None:
            # Avoid running expensive multi-waypoint A* every 4m when taxiing across a wide unmapped apron (>42m from nearest OSM node)
            reuse_apron_fresh = False
            if (
                st
                and st.get("key") == route_key
                and len(st.get("coords") or []) >= 2
                and st.get("last_seg_idx", 0) == 0
                and st.get("last_fresh_pos") is not None
            ):
                lf_lat, lf_lon = st["last_fresh_pos"]
                if haversine_m(user_lat, user_lon, lf_lat, lf_lon) < 28.0:
                    reuse_apron_fresh = True
            if not reuse_apron_fresh:
                fresh_coords, fresh_refs = compute_fresh_fn()
                st = {
                    "key": route_key,
                    "coords": list(fresh_coords or []),
                    "refs": list(fresh_refs or []),
                    "last_seg_idx": 0,
                    "last_fresh_pos": (user_lat, user_lon),
                }
                self._active_taxi_route_state[state_key] = st
                proj = _project_onto_route(st["coords"], min_idx=0)

        coords = st["coords"]
        refs = st["refs"]
        if not coords:
            return [[round(user_lat, 6), round(user_lon, 6)]], []

        if proj is not None:
            i_best, plat, plon, t_val, d_best, _ = proj
            if i_best > st.get("last_seg_idx", 0):
                st["last_seg_idx"] = i_best
            else:
                i_best = st.get("last_seg_idx", i_best)
            rem_coords = [list(p) for p in coords[i_best + 1:]]
            rem_refs = list(refs[i_best:]) if i_best < len(refs) else []
        else:
            rem_coords = [list(p) for p in coords]
            rem_refs = list(refs)

        # Strip any leading intersection vertices that are within 9m of the aircraft
        # or physically behind the aircraft's 3-9 o'clock line (> 92 deg off user_hdg within 65m)
        while len(rem_coords) >= 2:
            p_nxt = rem_coords[0]
            d_nxt = haversine_m(user_lat, user_lon, p_nxt[0], p_nxt[1])
            if d_nxt < 9.0:
                rem_coords.pop(0)
                if len(rem_refs) > len(rem_coords):
                    rem_refs.pop(0)
                st["last_seg_idx"] = min(len(coords) - 2, st.get("last_seg_idx", 0) + 1)
                continue
            if d_nxt < 65.0 and user_hdg is not None:
                brg_to_nxt = bearing_deg(user_lat, user_lon, p_nxt[0], p_nxt[1])
                if angle_diff_deg(user_hdg, brg_to_nxt) > 92.0:
                    rem_coords.pop(0)
                    if len(rem_refs) > len(rem_coords):
                        rem_refs.pop(0)
                    st["last_seg_idx"] = min(len(coords) - 2, st.get("last_seg_idx", 0) + 1)
                    continue
            break

        route_pts = [[round(user_lat, 6), round(user_lon, 6)]] + rem_coords
        return route_pts, rem_refs

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

        # Check if user aircraft is currently on the ground at this airport (within 16.5 km for mega-airports)
        user_at_airport = False
        if user_lat is not None and user_lon is not None:
            if haversine_m(user_lat, user_lon, chart.get("center_lat", gate_lat), chart.get("center_lon", gate_lon)) < 16500.0:
                if user_on_ground is not False:
                    user_at_airport = True

        if mode == "departure":
            icao = chart.get("icao", "")
            thresh_lat = target_end_info["lat"]
            thresh_lon = target_end_info["lon"]
            rwy_hdg = target_end_info.get("heading", 0.0)
            hold_name = self._find_nearest_holding_point_name(chart, thresh_lat, thresh_lon)

            is_crossing_rwy = False
            dist_from_gate = float('inf')
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

            if isinstance(atc_taxi_via, list) and len(atc_taxi_via) == 0:
                hold_suffix = f"Hold {hold_name} (RWY {runway_id})" if hold_name else f"Hold Short RWY {runway_id}"
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": [],
                    "rollout_points": [[thresh_lat, thresh_lon], [target_end_info["end_lat"], target_end_info["end_lon"]]],
                    "taxiway_sequence": [],
                    "clearance_text": f"Stand {gate_name} -> Click Taxiways -> {hold_suffix}",
                    "detected_exit": hold_name,
                    "live_status": "PARKED"
                }

            # Target is the ATC-assigned holding point (if atc_taxi_via connects to the runway)
            # or the holding point / taxiway entry near the takeoff threshold of `runway_id`
            rwy_node = None
            atc_hold_matched = False
            if atc_taxi_via:
                rwy_node = self._find_atc_departure_holding_node(
                    graph, target_rwy_obj, thresh_lat, thresh_lon, atc_taxi_via
                )
                if rwy_node is not None:
                    atc_hold_matched = True
            if rwy_node is None:
                rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=True, max_dist_m=450.0)
            if rwy_node is None:
                rwy_node = self._find_nearest_node(graph, thresh_lat, thresh_lon, prefer_non_runway=False, max_dist_m=600.0)
            if rwy_node is not None and (atc_hold_matched or not hold_name):
                rn_lat, rn_lon = graph["nodes"][rwy_node]
                node_hold_name = self._find_nearest_holding_point_name(chart, rn_lat, rn_lon)
                last_via_u = str(atc_taxi_via[-1]).strip().upper() if atc_taxi_via else ""
                if node_hold_name and (not atc_hold_matched or node_hold_name.upper().startswith(last_via_u)):
                    hold_name = node_hold_name
                elif atc_hold_matched and last_via_u:
                    hold_name = last_via_u

            def _clip_backtrack_runway(p_coords, e_refs):
                if not is_crossing_rwy and len(p_coords) > 2 and len(e_refs) == len(p_coords) - 1:
                    rwy_run_start = None
                    consec_rwy = 0
                    for idx_e, eref in enumerate(e_refs):
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
                        return p_coords[:rwy_run_start + 1], e_refs[:rwy_run_start]
                return p_coords, e_refs

            dep_route_key = (
                str(gate_name or ""),
                str(runway_id or ""),
                tuple(str(x).upper() for x in (atc_taxi_via or ()))
            )
            is_actively_taxiing_out = bool(user_at_airport and (dist_from_gate > 32.0 or (user_gs or 0.0) > 1.5))

            if is_actively_taxiing_out:
                def _compute_live_dep():
                    pruned_via = self._prune_passed_atc_taxi_via(
                        graph, user_lat, user_lon, user_hdg, rwy_node, atc_taxi_via
                    )
                    s_node = self._find_nearest_node(
                        graph, user_lat, user_lon,
                        prefer_non_runway=(not is_crossing_rwy),
                        max_dist_m=500.0
                    )
                    p_c, e_r = self._astar_path(
                        graph, s_node, rwy_node,
                        allow_runway_start=is_crossing_rwy,
                        start_out_heading=None,
                        atc_taxi_via=pruned_via
                    )
                    return _clip_backtrack_runway(p_c, e_r)

                route_pts, edge_refs = self._trim_passed_taxi_route(
                    icao=icao,
                    mode="departure",
                    route_key=dep_route_key,
                    user_lat=user_lat,
                    user_lon=user_lon,
                    user_hdg=user_hdg,
                    user_gs=user_gs,
                    compute_fresh_fn=_compute_live_dep
                )
            else:
                start_lat, start_lon = (user_lat, user_lon) if user_at_airport else (gate_lat, gate_lon)
                dep_out_hdg = gate_hdg if no_pushback else None
                parked_astar_sig = (icao.upper(), id(graph), gate_node, rwy_node, bool(is_crossing_rwy), dep_out_hdg, dep_route_key)
                cached_p = getattr(self, "_cached_parked_dep_astar", None)
                if cached_p and cached_p[0] == parked_astar_sig:
                    path_coords, edge_refs = list(cached_p[1]), list(cached_p[2])
                else:
                    path_coords, edge_refs = self._astar_path(
                        graph, gate_node, rwy_node,
                        allow_runway_start=is_crossing_rwy,
                        start_out_heading=dep_out_hdg,
                        atc_taxi_via=atc_taxi_via
                    )
                    path_coords, edge_refs = _clip_backtrack_runway(path_coords, edge_refs)
                    self._cached_parked_dep_astar = (parked_astar_sig, list(path_coords or []), list(edge_refs or []))
                self._active_taxi_route_state[(icao.upper(), "departure")] = {
                    "key": dep_route_key,
                    "coords": [[round(gate_lat, 6), round(gate_lon, 6)]] + list(path_coords or []),
                    "refs": ([edge_refs[0]] if edge_refs else [""]) + list(edge_refs or []),
                    "last_seg_idx": 0
                }
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

            if isinstance(atc_taxi_via, list) and len(atc_taxi_via) == 0:
                return {
                    "runway_id": runway_id,
                    "available_runways": avail_rwys,
                    "threshold": [thresh_lat, thresh_lon],
                    "route_points": [],
                    "rollout_points": [[thresh_lat, thresh_lon], [end_lat, end_lon]],
                    "taxiway_sequence": [],
                    "clearance_text": f"RWY {runway_id} -> Click Taxiways -> Stand {gate_name}",
                    "detected_exit": None,
                    "live_status": "PLANNED"
                }

            rwy_exit_norms = self._get_runway_exit_refs(graph, target_rwy_obj)

            def _sanitize_arrival_seq(raw_seq, primary_exit):
                if not raw_seq:
                    return [], []
                p_norm = re.sub(r'[\s_\-]+', '', str(primary_exit or "")).upper()
                s_list = list(raw_seq)
                # If primary_exit appears at index 1 (e.g. 1-edge crossing intersection right on the exit), trim prefix
                if p_norm:
                    for idx_s, item_s in enumerate(s_list):
                        if re.sub(r'[\s_\-]+', '', str(item_s)).upper() == p_norm:
                            if idx_s > 0 and idx_s <= 2:
                                s_list = s_list[idx_s:]
                            break
                head = [s_list[0]] if s_list else []
                head_norm = re.sub(r'[\s_\-]+', '', str(head[0])).upper() if head else ""
                if p_norm and p_norm in rwy_exit_norms and head_norm in rwy_exit_norms and head_norm != p_norm:
                    head = [primary_exit]
                    head_norm = p_norm
                for item_s in s_list[1:]:
                    inorm = re.sub(r'[\s_\-]+', '', str(item_s)).upper()
                    if inorm and inorm in rwy_exit_norms and inorm != head_norm:
                        continue
                    if not head or re.sub(r'[\s_\-]+', '', str(head[-1])).upper() != inorm:
                        head.append(item_s)
                eff_p_norm = p_norm or head_norm
                rem = [
                    item_s for item_s in head
                    if re.sub(r'[\s_\-]+', '', str(item_s)).upper() != eff_p_norm
                    and re.sub(r'[\s_\-]+', '', str(item_s)).upper() not in rwy_exit_norms
                ]
                return head, rem

            if live_arr and live_arr["state"] == "TAXI_IN":
                # Aircraft has already exited the runway! Route directly from live aircraft position to assigned gate!
                icao = chart.get("icao", "")
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
                    arr_route_key = (
                        str(gate_name or ""),
                        str(runway_id or ""),
                        tuple(str(x).upper() for x in (atc_taxi_via or ()))
                    )

                    def _compute_live_arr():
                        pruned_via = self._prune_passed_atc_taxi_via(
                            graph, user_lat, user_lon, user_hdg, gate_node, atc_taxi_via
                        )
                        s_node = self._find_nearest_node(graph, user_lat, user_lon, prefer_non_runway=True, max_dist_m=300.0)
                        p_c, e_r = self._astar_path(
                            graph, s_node, gate_node, allow_runway_start=False, goal_in_heading=gate_hdg,
                            atc_taxi_via=pruned_via
                        )
                        full_c = list(p_c or []) + [[round(gate_lat, 6), round(gate_lon, 6)]]
                        full_r = list(e_r or []) + ([e_r[-1]] if e_r else [""])
                        return full_c, full_r

                    route_pts, edge_refs = self._trim_passed_taxi_route(
                        icao=icao,
                        mode="arrival",
                        route_key=arr_route_key,
                        user_lat=user_lat,
                        user_lon=user_lon,
                        user_hdg=user_hdg,
                        user_gs=user_gs,
                        compute_fresh_fn=_compute_live_arr
                    )
                    if not route_pts or route_pts[-1] != [round(gate_lat, 6), round(gate_lon, 6)]:
                        route_pts = list(route_pts) + [[round(gate_lat, 6), round(gate_lon, 6)]]
                    seq = self._compress_taxiway_refs(edge_refs)
                det_exit = live_arr.get("detected_exit") or (seq[0] if seq else None)
                if det_exit and seq:
                    det_n = re.sub(r'[\s_\-]+', '', str(det_exit)).upper()
                    seq0_n = re.sub(r'[\s_\-]+', '', str(seq[0])).upper()
                    if seq0_n in rwy_exit_norms and det_n != seq0_n:
                        det_exit = seq[0]
                seq, rem_seq = _sanitize_arrival_seq(seq, det_exit)
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
                min_roll_m = max(200.0, d_cur + 20.0) if (user_gs or 0.0) > 50.0 else max(180.0, d_cur - 38.0)
                eff_atc_via = list(atc_taxi_via) if isinstance(atc_taxi_via, list) else None
                pref_exit = eff_atc_via[0] if eff_atc_via else None
                exit_node = self._find_best_runway_exit_node(
                    graph, target_rwy_obj, thresh_lat, thresh_lon, rwy_hdg,
                    target_rollout_m=d_cur + 260.0,
                    min_rollout_m=min_roll_m,
                    preferred_exit_ref=pref_exit,
                    gate_lat=gate_lat,
                    gate_lon=gate_lon,
                    is_live_rollout=True
                )
                exit_out_hdg = getattr(self, "_last_exit_out_bearing", None)
                chosen_exit_ref = getattr(self, "_last_exit_ref", None)
                if eff_atc_via and chosen_exit_ref:
                    f_norm = re.sub(r'[\s_\-]+', '', str(eff_atc_via[0])).upper()
                    c_norm = re.sub(r'[\s_\-]+', '', str(chosen_exit_ref)).upper()
                    if f_norm in rwy_exit_norms and c_norm != f_norm:
                        # Aircraft rolled past the initial cleared runway exit -> reroute cleanly from chosen_exit_ref
                        eff_atc_via = None
                if exit_node is None:
                    exit_node = self._find_nearest_node(graph, roll_lat, roll_lon, prefer_non_runway=False, max_dist_m=250.0)
                roll_astar_sig = (
                    str(chart.get("icao") or "").upper(),
                    id(graph),
                    exit_node,
                    gate_node,
                    gate_hdg,
                    round(float(exit_out_hdg), 2) if exit_out_hdg is not None else None,
                    tuple(str(x).upper() for x in eff_atc_via) if eff_atc_via is not None else None,
                )
                cached_r = getattr(self, "_cached_rollout_arr_astar", None)
                if cached_r and cached_r[0] == roll_astar_sig:
                    path_coords, edge_refs = list(cached_r[1]), list(cached_r[2])
                else:
                    path_coords, edge_refs = self._astar_path(
                        graph, exit_node, gate_node, allow_runway_start=False, goal_in_heading=gate_hdg,
                        start_out_heading=exit_out_hdg,
                        atc_taxi_via=eff_atc_via
                    )
                    self._cached_rollout_arr_astar = (roll_astar_sig, list(path_coords or []), list(edge_refs or []))
                route_pts = path_coords + [[round(gate_lat, 6), round(gate_lon, 6)]]
                exit_start = [ list(graph["nodes"][exit_node]) ][0] if exit_node is not None else (route_pts[0] if route_pts else [roll_lat, roll_lon])
                rollout_pts = [[round(roll_lat, 6), round(roll_lon, 6)], exit_start]
                seq = self._compress_taxiway_refs(edge_refs)
                det_exit = chosen_exit_ref or (seq[0] if seq else None)
                seq, rem_seq = _sanitize_arrival_seq(seq, det_exit)
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
                chosen_exit_ref = getattr(self, "_last_exit_ref", None)
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
                det_exit = chosen_exit_ref or (seq[0] if seq else None)
                seq, rem_seq = _sanitize_arrival_seq(seq, det_exit)
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
