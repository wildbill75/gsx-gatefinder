import os
import json
import urllib.request
import urllib.error
import configparser
import customtkinter as ctk
from tkinter import messagebox
from typing import Dict, List, Any
import threading
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import random
import re

# Configuration du thème moderne et chic
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Dictionnaire des envergures (wingspan en mètres) pour filtrer les portes
AIRCRAFT_WINGSPANS = {
    "E170": 26.0, "E175": 28.6, "E190": 28.7, "E195": 28.7,
    "CRJ7": 23.2, "CRJ9": 24.9, "BCS1": 35.1, "BCS3": 35.1, "AT76": 27.0,
    "A318": 34.1, "A319": 35.8, "A320": 35.8, "A321": 35.8, "A20N": 35.8, "A21N": 35.8,
    "B736": 34.3, "B737": 34.3, "B738": 35.8, "B739": 35.8, "B38M": 35.9, "B39M": 35.9,
    "A332": 60.3, "A333": 60.3, "A339": 64.0, 
    "A343": 60.3, "A346": 63.4,
    "A359": 64.8, "A35K": 64.8,
    "B763": 47.6, "B764": 51.9,
    "B772": 60.9, "B773": 60.9, "B77W": 64.8, "B77L": 64.8,
    "B788": 60.1, "B789": 60.1, "B78X": 60.1,
    "A388": 79.8,
    "B744": 64.4, "B748": 68.4
}

class ConfigManager:
    def __init__(self):
        self.config_file = "settings.json"
        self.settings = {
            "simbrief_username": "",
            "gsx_path": ""
        }
        self.load()
        
    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass
                
    def save(self):
        with open(self.config_file, "w") as f:
            json.dump(self.settings, f)

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, config: ConfigManager, on_save_callback):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x300")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        
        self.config = config
        self.on_save_callback = on_save_callback
        
        self.lbl_sb = ctk.CTkLabel(self, text="Simbrief Username / ID:", font=ctk.CTkFont(weight="bold"))
        self.lbl_sb.pack(anchor="w", padx=20, pady=(20, 5))
        
        self.entry_sb = ctk.CTkEntry(self, width=460)
        self.entry_sb.pack(padx=20)
        self.entry_sb.insert(0, self.config.settings["simbrief_username"])
        
        self.lbl_gsx = ctk.CTkLabel(self, text="GSX Profiles Folder (.ini):", font=ctk.CTkFont(weight="bold"))
        self.lbl_gsx.pack(anchor="w", padx=20, pady=(20, 5))
        
        frame_gsx = ctk.CTkFrame(self, fg_color="transparent")
        frame_gsx.pack(fill="x", padx=20)
        
        self.entry_gsx = ctk.CTkEntry(frame_gsx, width=350)
        self.entry_gsx.pack(side="left")
        self.entry_gsx.insert(0, self.config.settings["gsx_path"])
        
        self.btn_scan = ctk.CTkButton(frame_gsx, text="Auto Scan", width=100, command=self.scan_gsx)
        self.btn_scan.pack(side="right")
        
        self.btn_save = ctk.CTkButton(self, text="Save Settings", command=self.save_settings, fg_color="green", hover_color="darkgreen")
        self.btn_save.pack(pady=30)
        
    def scan_gsx(self):
        appdata = os.environ.get('APPDATA', '')
        possible_paths = [
            os.path.join(appdata, 'Virtuali', 'GSX', 'MSFS'),
            os.path.join(appdata, 'Virtuali', 'GSX')
        ]
        
        found = False
        for p in possible_paths:
            if os.path.exists(p):
                self.entry_gsx.delete(0, 'end')
                self.entry_gsx.insert(0, p)
                messagebox.showinfo("GSX Scan", f"GSX folder successfully detected:\n{p}")
                found = True
                break
                
        if not found:
            messagebox.showwarning("GSX Scan", "Unable to automatically detect GSX folder.")
            
    def save_settings(self):
        self.config.settings["simbrief_username"] = self.entry_sb.get()
        self.config.settings["gsx_path"] = self.entry_gsx.get()
        self.config.save()
        self.on_save_callback()
        self.destroy()

class GateFinderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("MSFS 2024 - GSX Gate Finder V2.2")
        self.geometry("600x750")
        self.minsize(550, 700)
        
        self.config = ConfigManager()
        
        self.data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        
        self.airport_names = {
            "LFPG": "Paris Charles de Gaulle", "LFPO": "Paris Orly", 
            "KJFK": "New York JFK", "KEWR": "New York Newark",
            "EGLL": "London Heathrow", "EGKK": "London Gatwick", 
            "EDDF": "Frankfurt am Main", "EDDM": "Munich",
            "EHAM": "Amsterdam Schiphol", "LEBL": "Barcelona El Prat", "LEMD": "Madrid Barajas"
        }
        self.airline_names = {
            "AFR": "Air France", "EZY": "easyJet", "UAL": "United Airlines",
            "DAL": "Delta Air Lines", "DLH": "Lufthansa", "BAW": "British Airways"
        }
        
        self.load_data()
        self.create_widgets()
        self.start_server()
        
    def load_data(self):
        self.data.clear()
        gsx_path = self.config.settings["gsx_path"]
        
        if os.path.exists(gsx_path):
            for filename in os.listdir(gsx_path):
                if filename.endswith('.ini'):
                    self.parse_gsx_ini(os.path.join(gsx_path, filename), filename)
                    
        local_gsx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gsx_profiles')
        if os.path.exists(local_gsx_path):
            for filename in os.listdir(local_gsx_path):
                if filename.endswith('.ini'):
                    self.parse_gsx_ini(os.path.join(local_gsx_path, filename), filename)
                    
        if not self.data:
            self.data = {
                "LFPG": {
                    "AFR": [{'name': "GATE E22", 'wingspan': 80.0}, {'name': "GATE E24", 'wingspan': 65.0}],
                    "EZY": [{'name': "GATE D2", 'wingspan': 36.0}]
                },
                "KJFK": {
                    "DAL": [{'name': "GATE B20", 'wingspan': 65.0}],
                    "AFR": [{'name': "GATE 1", 'wingspan': 80.0}]
                }
            }
                    
    def parse_gsx_ini(self, filepath: str, filename: str) -> bool:
        parser = configparser.ConfigParser(strict=False)
        try:
            parser.read(filepath, encoding='utf-8')
        except:
            try:
                parser.read(filepath, encoding='cp1252')
            except:
                return False
                
        base_name = filename.split('.')[0].upper()
        match = re.match(r'^([A-Z]{4})', base_name)
        if not match:
            return False
            
        icao = match.group(1)
        if len(icao) != 4 or not icao.isalpha():
            return False
            
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
                    gate_name = section[len(prefix):].replace('_', ' ').upper()
                else:
                    gate_name = section.replace('_', ' ').upper()
                    
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
                
                airlines = []
                if 'airlinecodes' in parser[section]:
                    airlines_str = parser[section]['airlinecodes']
                    airlines = [a.strip().upper() for a in airlines_str.split(',') if a.strip()]
                elif 'airline_codes' in parser[section]:
                    airlines_str = parser[section]['airline_codes']
                    airlines = [a.strip().upper() for a in airlines_str.split(',') if a.strip()]
                    
                if not airlines:
                    airlines = ['ANY']
                    
                for airline in airlines:
                    if airline not in airport_data:
                        airport_data[airline] = []
                    if not any(g['name'] == gate_name for g in airport_data[airline]):
                        airport_data[airline].append({'name': gate_name, 'wingspan': wingspan})
                            
        if airport_data:
            if icao not in self.data:
                self.data[icao] = {}
            for airline, gates in airport_data.items():
                if airline not in self.data[icao]:
                    self.data[icao][airline] = gates
                else:
                    existing = [g['name'] for g in self.data[icao][airline]]
                    self.data[icao][airline].extend([g for g in gates if g['name'] not in existing])
            return True
        return False

    def create_widgets(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(header_frame, text="GSX GATE FINDER", font=ctk.CTkFont(size=32, weight="bold")).pack(side="left")
        ctk.CTkButton(header_frame, text="⚙ Settings", width=120, command=self.open_settings).pack(side="right")
        
        self.sb_frame = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray17"))
        self.sb_frame.pack(fill="x", padx=20, pady=10)
        
        self.btn_import = ctk.CTkButton(self.sb_frame, text="📥 Import SimBrief Flight Plan", 
                                        font=ctk.CTkFont(size=16, weight="bold"), height=50,
                                        command=self.fetch_simbrief)
        self.btn_import.pack(fill="x", padx=20, pady=20)
        
        self.results_frame = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color=("white", "gray12"))
        self.results_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.placeholder_lbl = ctk.CTkLabel(self.results_frame, text="Waiting for SimBrief import...", text_color="gray")
        self.placeholder_lbl.pack(pady=50)

    def open_settings(self):
        SettingsWindow(self, self.config, self.load_data)

    def fetch_osm_gates(self, icao: str) -> List[str]:
        query = f"""
        [out:json];
        area["icao"="{icao}"]->.a;
        node(area.a)["aeroway"="parking_position"];
        out tags;
        """
        url = "https://overpass-api.de/api/interpreter"
        data = query.encode('utf-8')
        try:
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'GateFinder/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode())
                
            gates = []
            for element in result.get('elements', []):
                tags = element.get('tags', {})
                ref = tags.get('ref')
                if ref:
                    gates.append(f"GATE {ref}")
            return sorted(list(set(gates)))
        except Exception:
            return []

    def get_flight_data(self, username: str) -> dict:
        self.load_data()
        
        if username.isdigit():
            url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username}&json=1"
        else:
            url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
            
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
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
            
        aircraft = data.get('aircraft', {}).get('icaocode', '')
        wingspan = AIRCRAFT_WINGSPANS.get(aircraft, 36.0)

        def get_terminal(g):
            m = re.match(r'^([A-Z]+)', g.replace(' ', ''))
            if m: return f"Terminal {m.group(1)}"
            m_num = re.match(r'^(\d+)', g.replace(' ', ''))
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
            
            compatible_gates = []
            for g in all_gates:
                if g['wingspan'] >= wingspan:
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
        al_display = f"{airline} - {al_name}" if al_name else airline

        return {
            "aircraft": aircraft,
            "airline": al_display,
            "departure": process_airport(origin),
            "arrival": process_airport(destination),
            "alternate": process_airport(alternate)
        }

    def fetch_simbrief(self):
        username = self.config.settings["simbrief_username"].strip()
        if not username:
            messagebox.showerror("Error", "Please configure your Simbrief Username or Pilot ID in Settings.")
            return
            
        self.btn_import.configure(text="⏳ Importing...", state="disabled")
        self.update()
        
        try:
            result = self.get_flight_data(username)
            self.render_results(result)
        except Exception as e:
            messagebox.showerror("Simbrief Error", f"Unable to fetch flight plan.\nCheck your ID.\n{str(e)}")
        finally:
            self.btn_import.configure(text="📥 Import SimBrief Flight Plan", state="normal")

    def render_results(self, result):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        header_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        ac_badge = ctk.CTkFrame(header_frame, corner_radius=10, fg_color="#1E3A8A")
        ac_badge.pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkLabel(ac_badge, text=f"✈ Aircraft: {result['aircraft']}", 
                     font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(padx=20, pady=10)
                     
        al_badge = ctk.CTkFrame(header_frame, corner_radius=10, fg_color="#1E3A8A")
        al_badge.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(al_badge, text=f"🏢 Airline: {result['airline']}", 
                     font=ctk.CTkFont(size=18, weight="bold"), text_color="white").pack(padx=20, pady=10)

        def render_section(title, airport_data):
            if not airport_data: return
            
            section_frame = ctk.CTkFrame(self.results_frame, corner_radius=10, fg_color=("gray90", "gray15"))
            section_frame.pack(fill="x", pady=10)
            
            title_text = f"{title} - {airport_data['icao']}"
            if airport_data['name']:
                title_text += f" ({airport_data['name']})"
                
            ctk.CTkLabel(section_frame, text=title_text, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
            
            if airport_data.get('error'):
                color = "#F59E0B" if airport_data['osm'] else "#EF4444"
                msg = "🌐 GSX Profile not found. Fallback results (OSM):" if airport_data['osm'] else airport_data['error']
                ctk.CTkLabel(section_frame, text=msg, text_color=color).pack(anchor="w", padx=15, pady=(0, 10))
            
            if airport_data['gates']:
                for term, gates in sorted(airport_data['gates'].items()):
                    t_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
                    t_frame.pack(fill="x", padx=15, pady=5)
                    
                    if airport_data['osm']:
                        for g in gates:
                            ctk.CTkLabel(t_frame, text=f"✅ {g}", fg_color="#374151", corner_radius=5, padx=10, pady=5).pack(side="left", padx=5)
                    else:
                        ctk.CTkLabel(t_frame, text=f"📍 {term} :", font=ctk.CTkFont(weight="bold")).pack(side="left")
                        for g in gates:
                            ctk.CTkLabel(t_frame, text=f"✅ {g}", fg_color="#059669", corner_radius=5, padx=10, pady=5).pack(side="left", padx=10)

        render_section("🛫 DEPARTURE", result['departure'])
        render_section("🛬 ARRIVAL", result['arrival'])
        render_section("🔄 ALTERNATE", result['alternate'])
        
        self.update_idletasks()
        req_height = min(self.winfo_reqheight() + 50, 950)
        self.geometry(f"600x{req_height}")

    def start_server(self):
        class APIHandler(http.server.SimpleHTTPRequestHandler):
            app_instance = self
            
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
                        username = APIHandler.app_instance.config.settings.get("simbrief_username", "").strip()
                        
                    if not username:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No username provided"}).encode('utf-8'))
                        return
                        
                    try:
                        data = APIHandler.app_instance.get_flight_data(username)
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
            with socketserver.TCPServer(("127.0.0.1", 8420), APIHandler) as httpd:
                httpd.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

if __name__ == "__main__":
    app = GateFinderApp()
    app.mainloop()
