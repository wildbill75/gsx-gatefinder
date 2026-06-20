import os
import json
import re
import urllib.request
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import threading
import random
import configparser

AIRCRAFT_WINGSPANS = {
    'A318': 34.1, 'A319': 34.1, 'A320': 35.8, 'A321': 35.8,
    'A332': 60.3, 'A333': 60.3, 'A339': 64.0, 'A343': 60.3, 'A346': 63.4,
    'A359': 64.75, 'A35K': 64.75, 'A388': 79.75,
    'B736': 34.3, 'B737': 34.3, 'B738': 34.3, 'B739': 34.3,
    'B38M': 35.9, 'B39M': 35.9,
    'B744': 64.4, 'B748': 68.4,
    'B752': 38.0, 'B753': 38.0,
    'B763': 47.6, 'B764': 51.9,
    'B772': 60.9, 'B77W': 64.8, 'B77L': 64.8,
    'B788': 60.1, 'B789': 60.1, 'B78X': 60.1,
    'E170': 26.0, 'E175': 28.6, 'E190': 28.7, 'E195': 28.7,
    'CRJ2': 21.2, 'CRJ7': 23.2, 'CRJ9': 24.8, 'CRJX': 26.2,
    'BCS1': 35.1, 'BCS3': 35.1,
    'AT75': 27.0, 'AT76': 27.0,
    'DH8D': 28.4
}

class GateFinderBackend:
    def __init__(self, config):
        self.config = config
        self.data = {}
        self.airport_names = {}
        self.airline_names = self._load_airlines()
        self.cloud_ruleset = self._fetch_cloud_ruleset()
        self.server_thread = None

    def load_data(self):
        gsx_path = self.config.settings["gsx_profile_path"]
        self.data = {}
        self.airport_names = {}
        if not os.path.exists(gsx_path):
            return

        for filename in os.listdir(gsx_path):
            if filename.lower().endswith('.ini'):
                icao = filename[:4].upper()
                filepath = os.path.join(gsx_path, filename)
                try:
                    parser = configparser.ConfigParser()
                    parser.read(filepath, encoding='utf-8')
                except Exception:
                    continue

                if icao not in self.data:
                    self.data[icao] = {}

                for section in parser.sections():
                    sec_lower = section.lower()
                    if sec_lower.startswith(('parking', 'gate', 'stand', 'ramp', 'dock')):
                        prefix = ""
                        for p in ('parking_', 'parking ', 'gate_', 'gate ', 'stand_', 'stand ', 'ramp_', 'ramp ', 'dock_', 'dock '):
                            if sec_lower.startswith(p):
                                prefix = p
                                break
                        
                        if prefix:
                            name = section[len(prefix):].replace('_', ' ').upper()
                        else:
                            name = section.replace('_', ' ').upper()
                        
                        airlines = []
                        if 'airlinecodes' in parser[section]:
                            airlines = [a.strip().upper() for a in parser[section]['airlinecodes'].split(',') if a.strip()]
                        elif 'airline_codes' in parser[section]:
                            airlines = [a.strip().upper() for a in parser[section]['airline_codes'].split(',') if a.strip()]
                            
                        wingspan = 999.0
                        if 'maxwingspan' in parser[section]:
                            try:
                                wingspan = float(parser[section]['maxwingspan'])
                            except ValueError:
                                pass
                        elif 'max_wingspan' in parser[section]:
                            try:
                                wingspan = float(parser[section]['max_wingspan'])
                            except ValueError:
                                pass

                        gate_info = {'name': name, 'wingspan': wingspan}
                        
                        if airlines:
                            for a in airlines:
                                if a not in self.data[icao]:
                                    self.data[icao][a] = []
                                self.data[icao][a].append(gate_info)
                        else:
                            if 'ANY' not in self.data[icao]:
                                self.data[icao]['ANY'] = []
                            self.data[icao]['ANY'].append(gate_info)

    def _load_airlines(self):
        return {
            "AFR": "Air France",
            "DLH": "Lufthansa",
            "BAW": "British Airways",
            "RYR": "Ryanair",
            "EZY": "easyJet",
            "UAE": "Emirates",
            "QFA": "Qantas",
            "AAL": "American Airlines",
            "DAL": "Delta Air Lines",
            "UAL": "United Airlines",
            "VLG": "Vueling",
            "IBE": "Iberia",
            "KLM": "KLM",
            "SWR": "Swiss",
            "ACA": "Air Canada",
            "TAP": "TAP Air Portugal",
            "SAS": "SAS",
            "FIN": "Finnair",
            "LOT": "LOT Polish Airlines",
            "THY": "Turkish Airlines",
            "AEA": "Air Europa",
            "SVA": "Saudia",
            "QTR": "Qatar Airways",
            "ETD": "Etihad Airways",
            "SIA": "Singapore Airlines",
            "CPA": "Cathay Pacific",
            "ANA": "All Nippon Airways",
            "JAL": "Japan Airlines",
            "CCA": "Air China",
            "CSN": "China Southern Airlines",
            "CES": "China Eastern Airlines",
            "CCM": "Air Corsica",
            "TVF": "Transavia France",
            "EJU": "easyJet Europe",
            "VKG": "Sunclass Airlines",
            "FPO": "ASL Airlines France",
            "CRL": "Corsair",
            "TRA": "Transavia Airlines"
        }

    def _fetch_cloud_ruleset(self):
        url = "https://raw.githubusercontent.com/wildbill75/gsx-gatefinder/main/airlines_terminals.json"
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cloud_rules_cache.json")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                return data
        except Exception:
            try:
                if os.path.exists(cache_file):
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception:
                pass
        return {}

    def fetch_osm_gates(self, icao):
        try:
            overpass_url = "https://overpass-api.de/api/interpreter"
            query = f"""
            [out:json][timeout:10];
            area["icao"="{icao}"]->.a;
            node(area.a)["aeroway"="parking_position"];
            out tags;
            """
            req = urllib.request.Request(overpass_url, data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                osm_data = json.loads(response.read().decode())
                
            gates = []
            for element in osm_data.get('elements', []):
                tags = element.get('tags', {})
                ref = tags.get('ref')
                if ref:
                    gates.append(ref)
            return sorted(list(set(gates)))
        except Exception:
            return []

    def get_flight_data(self, username):
        if username.isdigit():
            url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username}&json=1"
        else:
            url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
            
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        origin = data.get('origin', {}).get('icao_code', '')
        if origin: self.airport_names[origin] = data.get('origin', {}).get('name', '').title()
        
        destination = data.get('destination', {}).get('icao_code', '')
        if destination: self.airport_names[destination] = data.get('destination', {}).get('name', '').title()
        
        alternate = data.get('alternate', {}).get('icao_code', '')
        if alternate: self.airport_names[alternate] = data.get('alternate', {}).get('name', '').title()
        
        general = data.get('general', {})
        airline = general.get('icao_airline', '')
        if not airline:
            airline = general.get('airline', '')
            
        aircraft_icao = data.get('aircraft', {}).get('icaocode', '')
        aircraft_name = data.get('aircraft', {}).get('name', '')
        aircraft = aircraft_name if aircraft_name and aircraft_name != aircraft_icao else f"{aircraft_icao}"
        
        wingspan = AIRCRAFT_WINGSPANS.get(aircraft_icao, 36.0)

        def get_terminal(g):
            g_clean = g.replace(' ', '')
            m = re.match(r'^([A-Z]+)', g_clean)
            if m:
                term = m.group(1)
                if term.startswith('T') and len(term) > 1 and term[1:].isdigit():
                    return f"Terminal {term[1:]}"
                if term == "GATE" or term == "STAND" or term == "PARKING":
                    # If it's literally just the word GATE followed by a number
                    num_match = re.search(r'\d+', g_clean)
                    if num_match:
                        num = int(num_match.group())
                        hundreds = (num // 100) * 100
                        return f"Zone {hundreds}s" if hundreds > 0 else "Main Apron"
                    return "Main Apron"
                return f"Terminal {term}"
            m_num = re.match(r'^(\d+)', g_clean)
            if m_num:
                num = int(m_num.group(1))
                hundreds = (num // 100) * 100
                return f"Zone {hundreds}s" if hundreds > 0 else "Main Apron"
            return "Other"

        def process_airport(icao):
            if not icao: return None
            
            res = {
                "icao": icao,
                "name": self.airport_names.get(icao, ''),
                "osm": False,
                "gates": {},
                "error": None
            }
            
            if icao not in self.data:
                osm_gates = self.fetch_osm_gates(icao)
                if osm_gates:
                    res["osm"] = True
                    res["gates"] = {"OSM": osm_gates[:10]}
                else:
                    res["error"] = "No gates found (GSX or Internet)."
                return res

            gates = self.data.get(icao, {}).get(airline, [])
            any_gates = self.data.get(icao, {}).get('ANY', [])
            
            all_gates = gates.copy()
            existing_names = {g['name'] for g in gates}
            for g in any_gates:
                if g['name'] not in existing_names:
                    all_gates.append(g)
            
            airport_cloud_data = self.cloud_ruleset.get(icao, {})
            cloud_rules = []
            mapping = {}
            if "rules" in airport_cloud_data:
                cloud_rules = airport_cloud_data["rules"].get(airline, [])
                mapping = airport_cloud_data.get("mapping", {})
            else:
                cloud_rules = airport_cloud_data.get(airline, [])
            
            compatible_gates = []
            for g in all_gates:
                if g['wingspan'] >= wingspan:
                    t = get_terminal(g['name'])
                    if cloud_rules:
                        matched_real_terminals = []
                        for real_term, aliases in mapping.items():
                            if t in aliases:
                                matched_real_terminals.append(real_term)
                        
                        if mapping:
                            if not any(rt in cloud_rules for rt in matched_real_terminals):
                                continue
                        else:
                            if t not in cloud_rules:
                                continue
                    compatible_gates.append(g['name'])
                    
            if not compatible_gates:
                res["error"] = "No gates found compatible with aircraft size."
                return res
                
            compatible_gates = sorted(list(set(compatible_gates)))
            terminals = {}
            for g in compatible_gates:
                t = get_terminal(g)
                if t not in terminals:
                    terminals[t] = []
                terminals[t].append(g)

            suggested_dict = {}
            if len(compatible_gates) > 5:
                suggested = []
                available_terms = list(terminals.keys())
                random.shuffle(available_terms)
                
                for t in available_terms:
                    if len(suggested) >= 3: break
                    suggested.append((t, random.choice(terminals[t])))
                    
                if len(suggested) < 3:
                    used_gates = [g for t, g in suggested]
                    remaining = [g for g in compatible_gates if g not in used_gates]
                    random.shuffle(remaining)
                    for g in remaining:
                        if len(suggested) >= 3: break
                        suggested.append((get_terminal(g), g))
                        
                for t, g in suggested:
                    if t not in suggested_dict:
                        suggested_dict[t] = []
                    suggested_dict[t].append(g)
            else:
                suggested_dict = terminals
                
            res["gates"] = {k: sorted(v) for k, v in suggested_dict.items()}
            return res

        al_name = self.airline_names.get(airline, '')
        al_display = f"{al_name} ({airline})" if al_name else airline

        return {
            "aircraft": aircraft,
            "airline": al_display,
            "departure": process_airport(origin),
            "arrival": process_airport(destination),
            "alternate": process_airport(alternate)
        }

    def scan_gsx_profiles(self):
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        if not gsx_path or not os.path.exists(gsx_path):
            return {"supported": [], "unknown": []}
            
        supported = set()
        unknown = set()
        for filename in os.listdir(gsx_path):
            if filename.lower().endswith('.ini'):
                icao = filename[:4].upper()
                if icao in self.cloud_ruleset:
                    supported.add(icao)
                else:
                    unknown.add(filename)
                    
        return {"supported": sorted(list(supported)), "unknown": sorted(list(unknown))}

    def generate_contribution_file(self, unknown_filenames):
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        data_to_contribute = {}
        
        for filename in unknown_filenames:
            icao = filename[:4].upper()
            filepath = os.path.join(gsx_path, filename)
            try:
                parser = configparser.ConfigParser()
                parser.read(filepath, encoding='utf-8')
            except Exception:
                continue
                
            airport_data = {}
            for section in parser.sections():
                sec_lower = section.lower()
                if sec_lower.startswith(('parking', 'gate', 'stand', 'ramp', 'dock')):
                    prefix = ""
                    for p in ('parking_', 'parking ', 'gate_', 'gate ', 'stand_', 'stand ', 'ramp_', 'ramp ', 'dock_', 'dock '):
                        if sec_lower.startswith(p):
                            prefix = p
                            break
                    
                    if prefix:
                        name = section[len(prefix):].replace('_', ' ').upper()
                    else:
                        name = section.replace('_', ' ').upper()
                        
                    airlines = []
                    if 'airlinecodes' in parser[section]:
                        airlines = [a.strip().upper() for a in parser[section]['airlinecodes'].split(',') if a.strip()]
                    elif 'airline_codes' in parser[section]:
                        airlines = [a.strip().upper() for a in parser[section]['airline_codes'].split(',') if a.strip()]
                        
                    if airlines:
                        airport_data[name] = airlines
            
            if airport_data:
                data_to_contribute[icao] = airport_data
                
        if not data_to_contribute:
            return None
            
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop') 
        out_path = os.path.join(desktop, "GateFinder_Contribution.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data_to_contribute, f, indent=2)
            
        return out_path

    def start_server(self):
        class APIHandler(http.server.SimpleHTTPRequestHandler):
            backend_instance = self
            
            def log_message(self, format, *args):
                pass
                
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Content-type', 'application/json')
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == '/api/simbrief':
                    query = parse_qs(parsed.query)
                    username = query.get('username', [''])[0]
                    if not username:
                        username = APIHandler.backend_instance.config.settings.get("simbrief_username", "").strip()
                        
                    if not username:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No username provided"}).encode('utf-8'))
                        return
                        
                    try:
                        data = APIHandler.backend_instance.get_flight_data(username)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps(data).encode('utf-8'))
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                    return
                    
                self.send_response(404)
                self.end_headers()

        def run_server():
            class ThreadingSimpleServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
                pass
            with ThreadingSimpleServer(("127.0.0.1", 8420), APIHandler) as httpd:
                httpd.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
