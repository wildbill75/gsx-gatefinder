class GSXGateFinderPanel extends TemplateElement {
    constructor() {
        super();
    }

    connectedCallback() {
        super.connectedCallback();
        
        let self = this;
        setTimeout(() => {
            try {
                let uiTitle = self.querySelector('.ingameUiTitle');
                if (uiTitle) uiTitle.innerText = "GSX GATE FINDER V1.0";
            } catch(e) {}
            self.init();
        }, 500);
    }

    init() {
        this.btnImport = this.querySelector("#BtnImport");
        if(this.btnImport) {
            this.btnImport.addEventListener("click", () => this.fetchData());
        }
    }

    fetchData() {
        if(this.btnImport) this.btnImport.innerText = "IMPORTING...";
        
        fetch('http://127.0.0.1:8420/api/simbrief')
            .then(response => response.json())
            .then(data => {
                if(data.error) {
                    console.error("GSX GateFinder Error:", data.error);
                    if(this.btnImport) this.btnImport.innerText = "ERROR: " + data.error;
                    return;
                }
                this.renderData(data);
                if(this.btnImport) this.btnImport.innerText = "IMPORT SIMBRIEF";
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
