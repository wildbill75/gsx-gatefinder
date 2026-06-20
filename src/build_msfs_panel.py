import os
import json
from datetime import datetime

base_dir = r"D:\GateFinder\MSFS_Package\bertrand-gsx-gatefinder"
panel_dir = os.path.join(base_dir, r"html_ui\InGamePanels\GSXGateFinder")
icons_dir = os.path.join(base_dir, r"html_ui\Icons\toolbar")

os.makedirs(panel_dir, exist_ok=True)
os.makedirs(icons_dir, exist_ok=True)

# Create a simple SVG icon for the toolbar
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="20" fill="#1e3a8a"/>
    <text x="50" y="65" font-size="40" font-family="Arial" font-weight="bold" fill="white" text-anchor="middle">GF</text>
</svg>"""
with open(os.path.join(icons_dir, "GSXGateFinder.svg"), "w") as f:
    f.write(svg_content)
with open(os.path.join(icons_dir, "GSXGateFinder-OFF.svg"), "w") as f:
    f.write(svg_content)

manifest = {
  "dependencies": [],
  "content_type": "UI",
  "title": "GSX Gate Finder",
  "manufacturer": "",
  "creator": "Bertrand",
  "package_version": "2.2.0",
  "minimum_game_version": "1.0.0",
  "release_notes": {
    "neutral": {
      "LastUpdate": "GSX Gate Finder MSFS Panel Release",
      "OlderHistory": ""
    }
  }
}

with open(os.path.join(base_dir, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="/SCSS/common.css" />
    <link rel="stylesheet" href="GSXGateFinder.css" />
    <script type="text/javascript" src="/JS/common.js"></script>
    <script type="text/javascript" src="/JS/Include.js"></script>
    <script type="text/javascript" src="/JS/coherent.js"></script>
    <script type="text/javascript" src="GSXGateFinder.js"></script>
</head>
<body class="color-white">
    <gsx-gatefinder-panel>
        <div id="MainDisplay" class="hidden">
            <div id="Header">
                <h1>GSX GATE FINDER</h1>
                <button id="BtnImport">📥 IMPORT SIMBRIEF</button>
            </div>
            
            <div id="AircraftInfo" class="hidden">
                <div class="badge">✈ Aircraft: <span id="ac_val"></span></div>
                <div class="badge">🏢 Airline: <span id="al_val"></span></div>
            </div>
            
            <div id="ResultsArea">
                <div id="DepBox" class="airport-box hidden">
                    <div class="airport-title">🛫 DEPARTURE - <span id="dep_icao"></span></div>
                    <div id="dep_error" class="error-text hidden"></div>
                    <div id="dep_gates" class="gates-container"></div>
                </div>
                
                <div id="ArrBox" class="airport-box hidden">
                    <div class="airport-title">🛬 ARRIVAL - <span id="arr_icao"></span></div>
                    <div id="arr_error" class="error-text hidden"></div>
                    <div id="arr_gates" class="gates-container"></div>
                </div>
                
                <div id="AltBox" class="airport-box hidden">
                    <div class="airport-title">🔄 ALTERNATE - <span id="alt_icao"></span></div>
                    <div id="alt_error" class="error-text hidden"></div>
                    <div id="alt_gates" class="gates-container"></div>
                </div>
            </div>
        </div>
    </gsx-gatefinder-panel>
</body>
</html>
"""

css_content = """gsx-gatefinder-panel {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    background-color: rgba(30, 30, 35, 0.9);
    border-radius: 10px;
    padding: 15px;
    font-family: 'Open Sans', sans-serif;
    color: white;
    box-sizing: border-box;
    overflow-y: auto;
}

#Header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #333;
    padding-bottom: 15px;
    margin-bottom: 15px;
}

h1 {
    font-size: 24px;
    font-weight: bold;
    margin: 0;
}

#BtnImport {
    background-color: #0284c7;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 10px 15px;
    font-weight: bold;
    font-size: 16px;
    cursor: pointer;
}

#BtnImport:hover {
    background-color: #0369a1;
}

.hidden {
    display: none !important;
}

#AircraftInfo {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
}

.badge {
    background-color: #1e3a8a;
    padding: 10px 15px;
    border-radius: 8px;
    font-weight: bold;
    font-size: 16px;
    flex: 1;
    text-align: center;
}

.airport-box {
    background-color: rgba(60, 60, 65, 0.7);
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 15px;
}

.airport-title {
    font-weight: bold;
    font-size: 18px;
    margin-bottom: 10px;
}

.error-text {
    color: #ef4444;
    font-weight: bold;
}

.warning-text {
    color: #f59e0b;
    font-weight: bold;
}

.term-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 8px;
}

.term-name {
    font-weight: bold;
    margin-right: 15px;
    width: 120px;
}

.gate-badge {
    background-color: #059669;
    padding: 5px 10px;
    border-radius: 5px;
    margin-right: 10px;
    font-size: 14px;
}

.gate-badge.osm {
    background-color: #374151;
}
"""

js_content = """class GSXGateFinderPanel extends TemplateElement {
    constructor() {
        super();
    }

    connectedCallback() {
        super.connectedCallback();
        
        let self = this;
        setTimeout(() => {
            self.init();
        }, 500);
    }

    init() {
        this.btnImport = this.querySelector("#BtnImport");
        if(this.btnImport) {
            this.btnImport.addEventListener("click", () => this.fetchData());
        }
        this.querySelector("#MainDisplay").classList.remove("hidden");
    }

    fetchData() {
        if(this.btnImport) this.btnImport.innerText = "⏳ IMPORTING...";
        
        fetch('http://127.0.0.1:8420/api/simbrief')
            .then(response => response.json())
            .then(data => {
                if(data.error) {
                    console.error("GSX GateFinder Error:", data.error);
                    if(this.btnImport) this.btnImport.innerText = "ERROR: " + data.error;
                    return;
                }
                this.renderData(data);
                if(this.btnImport) this.btnImport.innerText = "📥 IMPORT SIMBRIEF";
            })
            .catch(err => {
                console.error("GSX GateFinder Network Error:", err);
                if(this.btnImport) this.btnImport.innerText = "SERVER DISCONNECTED";
            });
    }

    renderData(data) {
        this.querySelector("#AircraftInfo").classList.remove("hidden");
        this.querySelector("#ac_val").innerText = data.aircraft;
        this.querySelector("#al_val").innerText = data.airline;
        
        this.renderAirport("DepBox", "dep", data.departure);
        this.renderAirport("ArrBox", "arr", data.arrival);
        this.renderAirport("AltBox", "alt", data.alternate);
    }
    
    renderAirport(boxId, prefix, aptData) {
        let box = this.querySelector("#" + boxId);
        if(!aptData) {
            box.classList.add("hidden");
            return;
        }
        
        box.classList.remove("hidden");
        let title = aptData.icao;
        if(aptData.name) title += " (" + aptData.name + ")";
        this.querySelector("#" + prefix + "_icao").innerText = title;
        
        let errDiv = this.querySelector("#" + prefix + "_error");
        let gatesDiv = this.querySelector("#" + prefix + "_gates");
        
        errDiv.classList.add("hidden");
        gatesDiv.innerHTML = "";
        
        if(aptData.error) {
            errDiv.innerText = aptData.osm ? "🌐 GSX Profile not found. Fallback results (OSM):" : "❌ " + aptData.error;
            errDiv.className = aptData.osm ? "warning-text" : "error-text";
            errDiv.classList.remove("hidden");
        }
        
        if(aptData.gates) {
            for(let term in aptData.gates) {
                let row = document.createElement("div");
                row.className = "term-row";
                
                if(!aptData.osm) {
                    let termLabel = document.createElement("div");
                    termLabel.className = "term-name";
                    termLabel.innerText = "📍 " + term + " :";
                    row.appendChild(termLabel);
                }
                
                let gates = aptData.gates[term];
                for(let i=0; i<gates.length; i++) {
                    let gBadge = document.createElement("div");
                    gBadge.className = "gate-badge" + (aptData.osm ? " osm" : "");
                    gBadge.innerText = "✅ " + gates[i];
                    row.appendChild(gBadge);
                }
                
                gatesDiv.appendChild(row);
            }
        }
    }
}

window.customElements.define("gsx-gatefinder-panel", GSXGateFinderPanel);
checkAutoload();
"""

with open(os.path.join(panel_dir, "GSXGateFinder.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

with open(os.path.join(panel_dir, "GSXGateFinder.css"), "w", encoding="utf-8") as f:
    f.write(css_content)

with open(os.path.join(panel_dir, "GSXGateFinder.js"), "w", encoding="utf-8") as f:
    f.write(js_content)

# InGamePanel XML to show in the toolbar
xml_dir = os.path.join(base_dir, r"InGamePanels")
os.makedirs(xml_dir, exist_ok=True)
xml_content = """<?xml version="1.0" encoding="Windows-1252"?>
<InGamePanels>
	<InGamePanel>
		<id>GSXGateFinderPanel</id>
		<icon>ToolbarIcon</icon>
		<html_file>html_ui/InGamePanels/GSXGateFinder/GSXGateFinder.html</html_file>
		<toolbar_icon>html_ui/Icons/toolbar/GSXGateFinder.svg</toolbar_icon>
		<title>GSX Gate Finder</title>
		<tooltip>GSX Gate Finder</tooltip>
		<size>800, 600</size>
		<min_size>600, 400</min_size>
		<show_when_toolbar_hidden>False</show_when_toolbar_hidden>
		<start_hidden>True</start_hidden>
	</InGamePanel>
</InGamePanels>
"""
with open(os.path.join(xml_dir, "GSXGateFinder.xml"), "w") as f:
    f.write(xml_content)

# layout.json generator
layout_entries = []
for root, _, files in os.walk(base_dir):
    for file in files:
        if file == "layout.json": continue
        filepath = os.path.join(root, file)
        rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")
        size = os.path.getsize(filepath)
        date = int(os.path.getmtime(filepath)) * 10000000 + 116444736000000000 # Windows file time
        layout_entries.append({
            "path": rel_path,
            "size": size,
            "date": date
        })

layout = {"content": layout_entries}
with open(os.path.join(base_dir, "layout.json"), "w") as f:
    json.dump(layout, f, indent=2)

print("MSFS Panel Package Built successfully in D:\\GateFinder\\MSFS_Package\\bertrand-gsx-gatefinder")
