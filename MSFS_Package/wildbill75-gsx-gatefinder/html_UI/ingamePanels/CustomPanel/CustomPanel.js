class GSXGateFinderPanel extends TemplateElement {
    constructor() {
        super();
    }

    connectedCallback() {
        super.connectedCallback();
        
        let self = this;
        function replaceText(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                if (node.nodeValue && node.nodeValue.toUpperCase().trim() === "CUSTOMPANEL") {
                    node.nodeValue = "GATEFINDER V1.0";
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                if (node.shadowRoot) {
                    for (let child of node.shadowRoot.childNodes) replaceText(child);
                }
                for (let child of node.childNodes) replaceText(child);
            }
        }
        
        function forceTitle() {
            replaceText(document.documentElement);
            let ui = document.querySelector("ingame-ui");
            if (ui) {
                ui.setAttribute("title", "GATEFINDER V1.0");
            }
            let header = document.querySelector("ingame-ui-header");
            if (header) {
                header.setAttribute("title", "GATEFINDER V1.0");
                if(header.shadowRoot) {
                    let titleElem = header.shadowRoot.querySelector(".title");
                    if (titleElem) titleElem.innerText = "GATEFINDER V1.0";
                }
            }
        }
        
        setTimeout(forceTitle, 500);
        setTimeout(forceTitle, 1500);
        setTimeout(forceTitle, 3000);
        setTimeout(forceTitle, 5000);

        setTimeout(() => {
            self.init();
        }, 500);
    }

    init() {
        this.fetchCurrentData();
        setInterval(() => this.fetchCurrentData(), 2000);
    }

    fetchCurrentData() {
        fetch('http://127.0.0.1:8420/api/current')
            .then(response => response.json())
            .then(data => {
                if(data && Object.keys(data).length > 0) {
                    let dataStr = JSON.stringify(data);
                    if (this.lastDataStr !== dataStr) {
                        this.lastDataStr = dataStr;
                        this.renderData(data);
                    }
                }
            })
            .catch(err => {
                // Ignore silent polling errors
            });
    }

    renderData(data) {
        this.querySelector("#AircraftInfo").classList.remove("hidden");
        this.querySelector("#ac_val").innerText = data.aircraft;
        this.querySelector("#al_val").innerText = data.airline;
        
        this.renderAirport("DepBox", "dep", data.departure);
        this.renderAirport("ArrBox", "arr", data.arrival);
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
            errDiv.innerText = aptData.osm ? "GSX Profile not found. Fallback results (OSM):" : aptData.error;
            errDiv.className = aptData.osm ? "warning-text" : "error-text";
            errDiv.classList.remove("hidden");
        }
        
        if(aptData.gate) {
            let row = document.createElement("div");
            row.className = "term-row";
            
            if(aptData.terminal) {
                let tName = document.createElement("div");
                tName.className = "term-name";
                tName.innerText = aptData.terminal;
                row.appendChild(tName);
            }
            
            let gBadge = document.createElement("div");
            gBadge.className = "gate-badge" + (aptData.osm ? " osm" : "");
            
            let gateText = aptData.gate;
            if(aptData.osm) gateText = "Stand " + gateText;
            gBadge.innerText = gateText;
            
            row.appendChild(gBadge);
            gatesDiv.appendChild(row);
        }
    }
}

window.customElements.define("gsx-gatefinder-panel", GSXGateFinderPanel);
checkAutoload();
