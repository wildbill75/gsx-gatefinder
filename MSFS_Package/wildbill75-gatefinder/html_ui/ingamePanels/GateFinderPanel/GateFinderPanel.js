class GSXGateFinderPanel extends TemplateElement {
    constructor() {
        super();
        this.activePhase = "departure";
        this.manualPhaseOverride = false;
        this.themeMode = "night"; // "night" or "day"
        this.viewMode = "route";  // "route" (AGC) or "terminal" (APC)
        this.followAircraft = false;
        this.headingUp = false;
        this.followUserZoomMpp = null;
        this.followPanLatOffset = 0.0;
        this.followPanLonOffset = 0.0;
        this.lastLiveStatus = null;
        this.centerLat = 0.0;
        this.centerLon = 0.0;
        this.metersPerPixel = 4.0;
        this.initialFitDone = false;
        this.isDragging = false;
        this.dragOriginX = 0;
        this.dragOriginY = 0;
        this.dragTotalDX = 0;
        this.dragTotalDY = 0;
        this.dragStartLat = 0.0;
        this.dragStartLon = 0.0;
        this.dragCanvasX = 0;
        this.dragCanvasY = 0;
        this.dragSettleTimer = null;
        this.wheelSettleTimer = null;
        this.wheelScale = 1.0;
        this.wheelTX = 0.0;
        this.wheelTY = 0.0;
        this.canvasW = 0;
        this.canvasH = 0;
        this.basePad = 140;
        this.lastBaseKey = "";
        this.rafPending = false;
        this.currentData = null;
        this.rawCharts = {};
        this.fastCharts = {};
        this.lastSidebarSig = "";
        this.lastChartSig = "";
        this.initialSizeResetDone = false;
        this.standHitboxes = [];
        this.rwyHitboxes = [];
    }

    sanitizeText(str) {
        return String(str || "")
            .replace(/\s*[\u2022\u00b7\u25aa\u25cf]\s*/g, " - ")
            .replace(/[\u2794\u2192]/g, "->")
            .trim();
    }

    getCamaieu(data) {
        let d = data || this.currentData || {};
        if (d.camaieu_palette && d.camaieu_palette.s1) {
            return d.camaieu_palette;
        }
        return {
            s1: "#578DA8",
            s2: "#517B90",
            s3: "#4A6C7D",
            s4: "#435D6B",
            s5: "#4E788E",
            s6: "#3F5663",
            accent: "#66A1BE",
            card_bg: "#1B1E24",
            card_sel_bg: "#25343D",
            card_hover_bg: "#1D2930",
            subcard_bg: "#1B1E24"
        };
    }

    injectCoreStyles() {
        if (document.getElementById("GFStyleOverrideV40")) return;
        let st = document.createElement("style");
        st.id = "GFStyleOverrideV40";
        st.textContent = `
            gsx-gatefinder-panel {
                display: flex !important;
                flex-direction: column !important;
                width: 100% !important;
                height: 100% !important;
                background-color: rgba(18, 20, 26, 0.98) !important;
                border-radius: 10px !important;
                padding: 8px !important;
                font-family: 'Open Sans', sans-serif !important;
                color: #ffffff !important;
                box-sizing: border-box !important;
                overflow: hidden !important;
            }
            .top-bar {
                display: flex !important;
                flex-direction: column !important;
                margin-bottom: 8px !important;
                flex-shrink: 0 !important;
            }
            .header-row {
                display: flex !important;
                align-items: center !important;
                justify-content: space-between !important;
                background-color: #1B1E24 !important;
                border-radius: 10px !important;
                min-height: 58px !important;
                padding: 9px 14px !important;
                margin-bottom: 8px !important;
            }
            .flight-pills {
                display: flex !important;
                align-items: center !important;
                flex-wrap: wrap !important;
            }
            .airline-wide-logo {
                width: 92px !important;
                height: 40px !important;
                border-radius: 7px !important;
                object-fit: contain !important;
                background-color: #ffffff !important;
                flex-shrink: 0 !important;
                display: block !important;
                margin-right: 10px !important;
            }
            .pill-badge {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 40px !important;
                color: #ffffff !important;
                padding: 0 18px !important;
                border-radius: 8px !important;
                font-weight: bold !important;
                font-size: 14px !important;
                line-height: 1 !important;
                white-space: nowrap !important;
                margin-right: 10px !important;
                box-sizing: border-box !important;
            }
            .phase-tabs-row {
                display: flex !important;
                flex-direction: row !important;
                width: 100% !important;
            }
            .phase-card {
                flex: 1 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                background-color: #1B1E24;
                min-height: 54px !important;
                padding: 10px 16px !important;
                border-radius: 10px !important;
                cursor: pointer !important;
                user-select: none !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                box-sizing: border-box !important;
            }
            #TabDep {
                margin-right: 8px !important;
            }
            .phase-title {
                font-weight: bold !important;
                font-size: 15px !important;
                color: #ffffff !important;
                margin-right: 14px !important;
                letter-spacing: 0.5px !important;
            }
            .phase-mini-pill {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 34px !important;
                padding: 0 15px !important;
                border-radius: 7px !important;
                font-weight: bold !important;
                font-size: 13.5px !important;
                color: #ffffff !important;
                white-space: nowrap !important;
                margin-right: 8px !important;
                box-sizing: border-box !important;
            }
            .workspace-area {
                display: flex !important;
                flex-direction: row !important;
                flex: 1 1 auto !important;
                min-height: 0 !important;
                min-width: 0 !important;
                overflow: hidden !important;
            }
            .left-sidebar {
                width: 288px !important;
                min-width: 268px !important;
                max-width: 304px !important;
                margin-right: 8px !important;
                display: flex !important;
                flex-direction: column !important;
                min-height: 0 !important;
                box-sizing: border-box !important;
                overflow-y: auto !important;
            }
            .efb-card {
                background-color: #1B1E24 !important;
                border-radius: 10px !important;
                padding: 14px 12px !important;
                margin-bottom: 8px !important;
                box-sizing: border-box !important;
                flex-shrink: 0 !important;
            }
            .efb-card:last-child {
                margin-bottom: 0 !important;
            }
            .efb-card-expand {
                flex: 1 1 auto !important;
                display: flex !important;
                flex-direction: column !important;
                min-height: 0 !important;
            }
            .right-chart-pane {
                flex: 1 1 auto !important;
                display: flex !important;
                flex-direction: column !important;
                background-color: #1B1E24 !important;
                border-radius: 10px !important;
                overflow: hidden !important;
                min-width: 240px !important;
                min-height: 0 !important;
            }
            .chart-top-bar {
                min-height: 48px !important;
                background-color: #1B1E24 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: space-between !important;
                padding: 7px 12px !important;
                flex-shrink: 0 !important;
            }
            .sc-status-pill {
                display: inline-flex !important;
                align-items: center !important;
                height: 34px !important;
                background-color: #2B303B !important;
                color: #ffffff !important;
                font-size: 12.5px !important;
                font-weight: bold !important;
                padding: 0 14px !important;
                border-radius: 8px !important;
                white-space: nowrap !important;
            }
            .chart-toolbar {
                display: flex !important;
                align-items: center !important;
            }
            .chart-btn {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 34px !important;
                background-color: #2B303B;
                color: #ffffff !important;
                padding: 0 13px !important;
                border-radius: 8px !important;
                font-size: 12.5px !important;
                font-weight: bold !important;
                cursor: pointer !important;
                user-select: none !important;
                white-space: nowrap !important;
                margin-left: 6px !important;
            }
            .chart-btn:first-child {
                margin-left: 0 !important;
            }
        `;
        (document.head || this).appendChild(st);
    }

    connectedCallback() {
        super.connectedCallback();
        let self = this;
        this.injectCoreStyles();

        function replaceText(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                if (node.nodeValue && (node.nodeValue.toUpperCase().trim() === "GATEFINDERPANEL" || node.nodeValue.toUpperCase().trim() === "GATEFINDER")) {
                    node.nodeValue = "GATEFINDER V2.0";
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
                ui.setAttribute("title", "GATEFINDER V2.0");
                ui.setAttribute("resize", "both");
                ui.classList.remove("minimized");
                if (ui.m_MainDisplay) ui.m_MainDisplay.classList.remove("hidden");
            }
            let mainDisp = document.querySelector("#MainDisplay");
            if (mainDisp) mainDisp.classList.remove("hidden");
            if (typeof Coherent !== "undefined" && window.innerHeight > 0 && window.innerHeight < 200) {
                let pid = (ui && ui.panelID) ? ui.panelID : "PANEL_GATEFINDER";
                try {
                    Coherent.trigger("UPDATE_PANEL_HEIGHT", pid, 540);
                } catch (e) {}
            }
            let header = document.querySelector("ingame-ui-header");
            if (header) {
                header.setAttribute("title", "GATEFINDER V2.0");
                if (header.shadowRoot) {
                    let titleElem = header.shadowRoot.querySelector(".title");
                    if (titleElem) titleElem.innerText = "GATEFINDER V2.0";
                }
            }
        }

        setTimeout(forceTitle, 300);
        setTimeout(forceTitle, 1200);
        setTimeout(forceTitle, 2800);

        setTimeout(() => {
            self.init();
        }, 350);
    }

    init() {
        this._lastPollTs = 0;
        this._fetchInFlight = false;
        this._backendDisconnected = false;
        this.injectCoreStyles();
        this.setupInteractions();
        this.fetchCurrentData();
        setInterval(() => {
            let now = Date.now();
            let uAc = (this.currentData && this.currentData.user_aircraft) || null;
            let isAirborne = Boolean(uAc && uAc.connected && uAc.on_ground === false);
            let minInterval = (isAirborne || this._backendDisconnected) ? 3000 : 350;
            if ((now - (this._lastPollTs || 0)) >= minInterval) {
                this._lastPollTs = now;
                this.fetchCurrentData();
            }
        }, 350);
    }

    scheduleDraw() {
        if (this.rafPending) return;
        this.rafPending = true;
        requestAnimationFrame(() => {
            this.rafPending = false;
            this.drawChart();
        });
    }

    updateCanvasMetrics() {
        let wrap = this.querySelector("#ChartWrapper");
        let canvas = this.querySelector("#LidoCanvas");
        if (!canvas || !wrap) return false;
        let w = wrap.clientWidth || 0;
        let h = wrap.clientHeight || 0;
        if (w < 100 || h < 100) return false;
        if (this.canvasW !== w || this.canvasH !== h) {
            this.canvasW = w;
            this.canvasH = h;
            let pad = this.basePad || 140;
            let bw = w + pad * 2;
            let bh = h + pad * 2;
            canvas.width = bw;
            canvas.height = bh;
            canvas.style.width = bw + "px";
            canvas.style.height = bh + "px";
            canvas.style.left = (-pad) + "px";
            canvas.style.top = (-pad) + "px";
            this.lastBaseKey = "";
            return true;
        }
        return false;
    }

    resetCanvasTransform() {
        let canvas = this.querySelector("#LidoCanvas");
        this.wheelScale = 1.0;
        this.wheelTX = 0.0;
        this.wheelTY = 0.0;
        this.dragTotalDX = 0;
        this.dragTotalDY = 0;
        if (canvas) {
            canvas.style.transform = "translate3d(0px, 0px, 0px) scale(1)";
        }
    }

    applyZoomFactor(factor, pivotX, pivotY) {
        let canvas = this.querySelector("#LidoCanvas");
        let wrap = this.querySelector("#ChartWrapper");
        if (!canvas || !wrap) return;

        let oldMpp = this.metersPerPixel;
        let newMpp = Math.max(0.22, Math.min(25.0, oldMpp * factor));
        let effRatio = oldMpp / newMpp;
        if (Math.abs(effRatio - 1.0) < 0.0001) return;
        this.hideStandTooltip();
        this.closeStandContextModal();
        this.metersPerPixel = newMpp;
        if (this.followAircraft) {
            this.followUserZoomMpp = newMpp;
        }
        this.updateToolbarButtons();

        let pad = this.basePad || 140;
        let cx = (pivotX !== undefined ? pivotX : (this.canvasW || 520) * 0.5) + pad;
        let cy = (pivotY !== undefined ? pivotY : (this.canvasH || 400) * 0.5) + pad;

        this.wheelTX = cx - effRatio * (cx - this.wheelTX);
        this.wheelTY = cy - effRatio * (cy - this.wheelTY);
        this.wheelScale = this.wheelScale * effRatio;
        canvas.style.transform = "translate3d(" + this.wheelTX.toFixed(1) + "px, " + this.wheelTY.toFixed(1) + "px, 0px) scale(" + this.wheelScale.toFixed(4) + ")";

        if (this.wheelSettleTimer) clearTimeout(this.wheelSettleTimer);
        this.wheelSettleTimer = setTimeout(() => {
            this.wheelSettleTimer = null;
            this.resetCanvasTransform();
            this.lastBaseKey = "";
            this.drawChart();
        }, 200);
    }

    isAirborneNow() {
        if (!this.currentData) return false;
        return Boolean(this.currentData.is_airborne);
    }

    showAirborneDepartureLockedToast() {
        let efb = this.querySelector("#EFBContainer") || this;
        let toast = this.querySelector("#AirborneLockedToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "AirborneLockedToast";
            toast.style.cssText =
                "position:absolute;top:52px;left:50%;transform:translateX(-50%);" +
                "background:#2B303B;color:#fbbf24;" +
                "font-size:11px;font-weight:700;padding:7px 16px;border-radius:8px;" +
                "z-index:80;pointer-events:none;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.45);";
            efb.appendChild(toast);
        }
        toast.innerText = "IN FLIGHT  |  Departure chart locked while airborne (Arrival diagram active).";
        toast.style.display = "block";
        if (this._airborneToastTimer) clearTimeout(this._airborneToastTimer);
        this._airborneToastTimer = setTimeout(() => {
            if (toast) toast.style.display = "none";
        }, 3500);
    }

    applySmartFollowCamera(snap) {
        let uAc = (this.currentData && this.currentData.user_aircraft) ? this.currentData.user_aircraft : null;
        let apt = (this.currentData && this.currentData[this.activePhase]) ? this.currentData[this.activePhase] : null;
        if (!uAc || uAc.lat == null || uAc.lon == null) {
            if (apt && apt.lat != null && apt.lon != null) {
                this.centerLat = parseFloat(apt.lat);
                this.centerLon = parseFloat(apt.lon);
                this.metersPerPixel = 0.85;
            }
            return;
        }
        let acLat = parseFloat(uAc.lat);
        let acLon = parseFloat(uAc.lon);
        let tgtLat = (apt && apt.lat != null) ? parseFloat(apt.lat) : null;
        let tgtLon = (apt && apt.lon != null) ? parseFloat(apt.lon) : null;

        if (this.activePhase === "departure" && apt && apt.taxi_route) {
            let rPts = apt.taxi_route.route_points || [];
            if (rPts.length >= 2) {
                tgtLat = parseFloat(rPts[rPts.length - 1][0]);
                tgtLon = parseFloat(rPts[rPts.length - 1][1]);
            }
        }

        let panLat = this.followPanLatOffset || 0.0;
        let panLon = this.followPanLonOffset || 0.0;
        let userZoom = this.followUserZoomMpp || null;

        if (tgtLat == null || tgtLon == null || isNaN(tgtLat) || isNaN(tgtLon)) {
            this.centerLat = acLat + panLat;
            this.centerLon = acLon + panLon;
            this.metersPerPixel = userZoom != null ? userZoom : 0.85;
            return;
        }

        let cosLat = Math.max(0.15, Math.cos(acLat * 0.017453292519943295));
        let dxM = (tgtLon - acLon) * 111320.0 * cosLat;
        let dyM = -(tgtLat - acLat) * 111320.0;
        let distM = Math.hypot(dxM, dyM);

        if (distM > 12000.0) {
            this.centerLat = acLat + panLat;
            this.centerLon = acLon + panLon;
            this.metersPerPixel = userZoom != null ? userZoom : 0.85;
            return;
        }

        this.centerLat = (acLat + tgtLat) * 0.5 + panLat;
        this.centerLon = (acLon + tgtLon) * 0.5 + panLon;

        if (userZoom != null) {
            this.metersPerPixel = userZoom;
            return;
        }

        let rxM = dxM;
        let ryM = dyM;
        if (this.headingUp && uAc.connected && uAc.heading != null) {
            let ang = -(parseFloat(uAc.heading) * Math.PI) / 180.0;
            rxM = dxM * Math.cos(ang) - dyM * Math.sin(ang);
            ryM = dxM * Math.sin(ang) + dyM * Math.cos(ang);
        }

        let w = Math.max(this.canvasW || 520, 420);
        let h = Math.max(this.canvasH || 400, 320);
        let spanXM = Math.max(95.0, Math.abs(rxM) * 1.48);
        let spanYM = Math.max(95.0, Math.abs(ryM) * 1.48);
        let targetMpp = Math.max(spanXM / Math.max(200.0, w - 90.0), spanYM / Math.max(180.0, h - 90.0), 0.45);
        targetMpp = Math.min(12.0, targetMpp);

        if (snap || !this.metersPerPixel || this.metersPerPixel <= 0) {
            this.metersPerPixel = targetMpp;
        } else {
            this.metersPerPixel = (0.68 * this.metersPerPixel) + (0.32 * targetMpp);
        }
    }

    requestRunwayChange(chosenRwy) {
        if (!this.currentData) return;
        let aptData = this.currentData[this.activePhase] || {};
        let curRwy = String(aptData.selected_runway || "").toUpperCase();
        let chosenClean = String(chosenRwy || "").replace(/^RWY\s*/i, "").trim().toUpperCase();
        if (!chosenClean || chosenClean === curRwy) return;

        let atcRwy = aptData.atc_runway ? String(aptData.atc_runway).toUpperCase() : "";
        let atcSrc = aptData.atc_runway_source || aptData.runway_source || "AI ATC";

        let applySelection = () => {
            fetch("http://127.0.0.1:8420/api/set_runway?phase=" + encodeURIComponent(this.activePhase) + "&rwy=" + encodeURIComponent(chosenClean))
                .then(r => r.json())
                .then(d => {
                    ["departure", "arrival"].forEach(ph => {
                        if (d[ph] && d[ph].icao && !d[ph].chart_data && this.rawCharts[d[ph].icao]) {
                            d[ph].chart_data = this.rawCharts[d[ph].icao];
                        }
                    });
                    this.currentData = d;
                    this.initialFitDone = false;
                    this.lastSidebarSig = "";
                    this.lastChartSig = "";
                    this.renderData(d, true);
                })
                .catch(() => {});
        };

        if (atcRwy && chosenClean !== atcRwy) {
            this.showAtcRunwayModal(atcSrc, aptData.icao || "", atcRwy, chosenClean, applySelection);
        } else {
            applySelection();
        }
    }

    requestStandChange(chosenGate) {
        if (!this.currentData) return;
        let aptData = this.currentData[this.activePhase] || {};
        let curGate = String(aptData.gate || "").replace(/\s+/g, "").toUpperCase();
        let gClean = String(chosenGate || "").trim();
        if (!gClean || gClean.replace(/\s+/g, "").toUpperCase() === curGate) return;

        fetch("http://127.0.0.1:8420/api/set_gate?phase=" + encodeURIComponent(this.activePhase) + "&gate=" + encodeURIComponent(gClean))
            .then(r => r.json())
            .then(d => {
                ["departure", "arrival"].forEach(ph => {
                    if (d[ph] && d[ph].icao && !d[ph].chart_data && this.rawCharts[d[ph].icao]) {
                        d[ph].chart_data = this.rawCharts[d[ph].icao];
                    }
                });
                this.currentData = d;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
                this.renderData(d, true);
            })
            .catch(() => {});
    }

    requestRepositionAircraft(chosenGate) {
        if (!this.currentData) return;
        let gClean = String(chosenGate || "").trim();
        if (!gClean) return;

        fetch("http://127.0.0.1:8420/api/reposition_aircraft?phase=" + encodeURIComponent(this.activePhase) + "&gate=" + encodeURIComponent(gClean))
            .then(r => r.json())
            .then(d => {
                ["departure", "arrival"].forEach(ph => {
                    if (d[ph] && d[ph].icao && !d[ph].chart_data && this.rawCharts[d[ph].icao]) {
                        d[ph].chart_data = this.rawCharts[d[ph].icao];
                    }
                });
                this.currentData = d;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
                this.renderData(d, true);
            })
            .catch(() => {});
    }

    closeStandContextModal() {
        let modal = this.querySelector("#StandContextModal");
        if (modal) {
            modal.style.display = "none";
        }
    }

    openStandContextModal(sh) {
        let wrap = this.querySelector("#ChartWrapper");
        if (!wrap || !sh) return;
        this.hideStandTooltip();

        let modal = this.querySelector("#StandContextModal");
        if (!modal) {
            modal = document.createElement("div");
            modal.id = "StandContextModal";
            modal.addEventListener("mousedown", (e) => { e.stopPropagation(); });
            modal.addEventListener("mouseup", (e) => { e.stopPropagation(); });
            modal.addEventListener("click", (e) => { e.stopPropagation(); });
            modal.addEventListener("contextmenu", (e) => { e.preventDefault(); e.stopPropagation(); return false; });
            wrap.appendChild(modal);
        }

        let borderCol = sh.isAssigned ? "#0284C7" : "#38BDF8";
        modal.style.cssText =
            "position:absolute;z-index:220;background-color:#111827;" +
            "border:1.5px solid " + borderCol + ";border-radius:10px;" +
            "padding:11px 13px;min-width:230px;box-shadow:0 8px 24px rgba(0,0,0,0.85);" +
            "box-sizing:border-box;display:block;";

        let titleTxt = "STAND " + sh.ref;
        if (sh.terminal) {
            titleTxt += "  |  " + this.sanitizeText(String(sh.terminal).toUpperCase());
        }

        let planeSvg = '<svg width="14" height="14" viewBox="0 0 24 24" style="margin-right:7px;flex-shrink:0;" fill="#FFFFFF"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>';

        modal.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">' +
                '<span style="font-size:13.5px;font-weight:700;color:#F8FAFC;">' + titleTxt + '</span>' +
                '<span id="BtnCloseStandCtx" style="font-size:13px;font-weight:700;color:#94A3B8;cursor:pointer;padding:2px 6px;border-radius:5px;">X</span>' +
            '</div>' +
            '<div style="font-size:11.5px;font-weight:700;color:#38BDF8;margin-bottom:10px;">GSX Pro Reposition & Stand Sync</div>' +
            '<div id="BtnWarpStandCtx" style="display:flex;align-items:center;justify-content:center;height:36px;background-color:#0284C7;color:#FFFFFF;font-size:13px;font-weight:700;border-radius:7px;cursor:pointer;padding:0 14px;margin-bottom:' + (sh.isAssigned ? '2px' : '7px') + ';">' + planeSvg + '<span>Reposition Aircraft to ' + sh.ref + '</span></div>' +
            (!sh.isAssigned
                ? '<div id="BtnSelectStandCtx" style="display:flex;align-items:center;justify-content:center;height:32px;background-color:#1E293B;color:#E2E8F0;font-size:12.5px;font-weight:700;border-radius:7px;cursor:pointer;padding:0 14px;">Select Stand ' + sh.ref + ' Only</div>'
                : '');

        let btnClose = modal.querySelector("#BtnCloseStandCtx");
        if (btnClose) {
            btnClose.addEventListener("click", (e) => {
                e.stopPropagation();
                this.closeStandContextModal();
            });
        }

        let btnWarp = modal.querySelector("#BtnWarpStandCtx");
        if (btnWarp) {
            btnWarp.addEventListener("click", (e) => {
                e.stopPropagation();
                this.closeStandContextModal();
                this.requestRepositionAircraft(sh.ref);
            });
        }

        let btnSel = modal.querySelector("#BtnSelectStandCtx");
        if (btnSel) {
            btnSel.addEventListener("click", (e) => {
                e.stopPropagation();
                this.closeStandContextModal();
                this.requestStandChange(sh.ref);
            });
        }

        let mw = modal.offsetWidth || 236;
        let mh = modal.offsetHeight || (sh.isAssigned ? 98 : 134);
        let wrapW = wrap.clientWidth || 520;
        let wrapH = wrap.clientHeight || 400;
        let cx = (sh.x0 + sh.x1) * 0.5;
        let left = Math.max(10, Math.min(wrapW - mw - 10, cx - mw * 0.5));
        let top = sh.y0 - mh - 10;
        if (top < 12) {
            top = sh.y1 + 10;
        }
        top = Math.max(10, Math.min(wrapH - mh - 10, top));
        modal.style.left = Math.round(left) + "px";
        modal.style.top = Math.round(top) + "px";
    }

    handleCanvasRightClick(clientX, clientY) {
        let wrap = this.querySelector("#ChartWrapper");
        if (!wrap) return;
        let rect = wrap.getBoundingClientRect();
        let mx = clientX - rect.left;
        let my = clientY - rect.top;

        if (this.standHitboxes && this.standHitboxes.length > 0) {
            for (let i = this.standHitboxes.length - 1; i >= 0; i--) {
                let sh = this.standHitboxes[i];
                if (mx >= sh.x0 - 5 && mx <= sh.x1 + 5 && my >= sh.y0 - 5 && my <= sh.y1 + 5) {
                    this.openStandContextModal(sh);
                    return;
                }
            }
        }
        this.closeStandContextModal();
    }

    handleCanvasClick(clientX, clientY) {
        let wrap = this.querySelector("#ChartWrapper");
        if (!wrap) return;
        let rect = wrap.getBoundingClientRect();
        let mx = clientX - rect.left;
        let my = clientY - rect.top;

        // 1. Check Runway Threshold Circle Hitboxes first
        if (this.rwyHitboxes && this.rwyHitboxes.length > 0) {
            for (let i = this.rwyHitboxes.length - 1; i >= 0; i--) {
                let rh = this.rwyHitboxes[i];
                if (mx >= rh.x0 - 4 && mx <= rh.x1 + 4 && my >= rh.y0 - 4 && my <= rh.y1 + 4) {
                    this.closeStandContextModal();
                    if (!rh.isActive) {
                        this.requestRunwayChange(rh.endId);
                    }
                    return;
                }
            }
        }

        // 2. Check Stand Tag Hitboxes
        if (this.standHitboxes && this.standHitboxes.length > 0) {
            for (let i = this.standHitboxes.length - 1; i >= 0; i--) {
                let sh = this.standHitboxes[i];
                if (mx >= sh.x0 - 4 && mx <= sh.x1 + 4 && my >= sh.y0 - 4 && my <= sh.y1 + 4) {
                    this.openStandContextModal(sh);
                    return;
                }
            }
        }
        this.closeStandContextModal();
    }

    setupInteractions() {
        let tabDep = this.querySelector("#TabDep");
        let tabArr = this.querySelector("#TabArr");
        if (tabDep) {
            tabDep.addEventListener("click", () => {
                if (this.isAirborneNow()) {
                    this.showAirborneDepartureLockedToast();
                    return;
                }
                this.activePhase = "departure";
                this.manualPhaseOverride = true;
                this.initialFitDone = false;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
                if (this.currentData) this.renderData(this.currentData, true);
            });
        }
        if (tabArr) {
            tabArr.addEventListener("click", () => {
                this.activePhase = "arrival";
                this.manualPhaseOverride = true;
                this.initialFitDone = false;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
                if (this.currentData) this.renderData(this.currentData, true);
            });
        }

        let btnZoomIn = this.querySelector("#BtnZoomIn");
        let btnZoomOut = this.querySelector("#BtnZoomOut");
        let btnAPC = this.querySelector("#BtnAPC");
        let btnAGC = this.querySelector("#BtnAGC");
        let btnFollow = this.querySelector("#BtnFollow");
        let btnOrient = this.querySelector("#BtnOrient");
        let btnTheme = this.querySelector("#BtnTheme");

        if (btnOrient && btnOrient.parentNode) {
            btnOrient.parentNode.removeChild(btnOrient);
        }
        if (btnAPC) btnAPC.innerText = "Gate";
        if (btnAGC) btnAGC.innerText = "Route";
        if (btnFollow) {
            btnFollow.innerText = "Follow + Hdg Up";
        }

        if (btnZoomIn) btnZoomIn.addEventListener("click", () => { this.applyZoomFactor(0.75); });
        if (btnZoomOut) btnZoomOut.addEventListener("click", () => { this.applyZoomFactor(1.33); });
        if (btnAPC) btnAPC.addEventListener("click", () => { this.fitTerminalView(); });
        if (btnAGC) btnAGC.addEventListener("click", () => { this.fitRouteView(); });
        if (btnFollow) {
            btnFollow.addEventListener("click", () => {
                if (this.isAirborneNow()) return;
                this.followAircraft = !this.followAircraft;
                this.headingUp = Boolean(this.followAircraft);
                this.followUserZoomMpp = null;
                this.followPanLatOffset = 0.0;
                this.followPanLonOffset = 0.0;
                if (this.followAircraft) {
                    this.applySmartFollowCamera(true);
                    this.resetCanvasTransform();
                    this.updateToolbarButtons();
                    this.scheduleDraw();
                } else {
                    this.fitRouteView();
                }
            });
        }
        if (btnTheme) {
            btnTheme.addEventListener("click", () => {
                this.themeMode = (this.themeMode === "night") ? "day" : "night";
                this.updateToolbarButtons();
                this.scheduleDraw();
            });
        }

        let canvas = this.querySelector("#LidoCanvas");
        let wrap = this.querySelector("#ChartWrapper");
        let handBadge = this.querySelector("#DragHandBadge");
        if (canvas) {
            canvas.addEventListener("dragstart", (e) => { e.preventDefault(); e.stopPropagation(); return false; });
            canvas.addEventListener("selectstart", (e) => { e.preventDefault(); e.stopPropagation(); return false; });
            canvas.addEventListener("contextmenu", (e) => {
                e.preventDefault();
                e.stopPropagation();
                let now = Date.now();
                if (!this._lastRightClickTs || (now - this._lastRightClickTs) > 180) {
                    this._lastRightClickTs = now;
                    this.handleCanvasRightClick(e.clientX, e.clientY);
                }
                return false;
            });

            let startMapDrag = (clientX, clientY, e) => {
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                this.hideStandTooltip();
                if (this.wheelSettleTimer) {
                    clearTimeout(this.wheelSettleTimer);
                    this.wheelSettleTimer = null;
                    this.resetCanvasTransform();
                }
                this.isDragging = true;
                this.dragOriginX = clientX;
                this.dragOriginY = clientY;
                this.dragTotalDX = 0;
                this.dragTotalDY = 0;
                this.dragStartLat = this.centerLat;
                this.dragStartLon = this.centerLon;
                let rect = (wrap || canvas).getBoundingClientRect();
                this.dragRectLeft = rect.left;
                this.dragRectTop = rect.top;
                this.dragCanvasX = clientX - rect.left;
                this.dragCanvasY = clientY - rect.top;
                canvas.classList.add("dragging");
                canvas.style.cursor = "pointer";
                document.body.style.cursor = "pointer";
                if (handBadge) {
                    handBadge.classList.remove("hidden");
                    handBadge.style.transform = "translate3d(" + this.dragCanvasX + "px, " + this.dragCanvasY + "px, 0px)";
                }
                this.updateToolbarButtons();
            };

            let moveMapDrag = (clientX, clientY, e) => {
                if (!this.isDragging) return;
                if (e && e.buttons !== undefined && e.buttons === 0) {
                    endMapDrag(clientX, clientY);
                    return;
                }
                if (e) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                this.dragTotalDX = clientX - this.dragOriginX;
                this.dragTotalDY = clientY - this.dragOriginY;
                if (Math.abs(this.dragTotalDX) > 4 || Math.abs(this.dragTotalDY) > 4) {
                    this.closeStandContextModal();
                }
                this.dragCanvasX = clientX - (this.dragRectLeft || 0);
                this.dragCanvasY = clientY - (this.dragRectTop || 0);

                canvas.style.transform = "translate3d(" + this.dragTotalDX + "px, " + this.dragTotalDY + "px, 0px) scale(1)";
                if (handBadge) {
                    handBadge.style.transform = "translate3d(" + this.dragCanvasX + "px, " + this.dragCanvasY + "px, 0px)";
                }
            };

            let endMapDrag = (clientX, clientY) => {
                if (!this.isDragging) return;
                let dx = this.dragTotalDX;
                let dy = this.dragTotalDY;
                let cosLat = Math.max(0.15, Math.cos(this.dragStartLat * 0.017453292519943295));
                let effDx = dx;
                let effDy = dy;
                let uAc = (this.currentData && this.currentData.user_aircraft) ? this.currentData.user_aircraft : null;
                if (this.headingUp && uAc && uAc.connected && uAc.heading != null) {
                    let ang = (parseFloat(uAc.heading) * Math.PI) / 180.0;
                    effDx = dx * Math.cos(ang) - dy * Math.sin(ang);
                    effDy = dx * Math.sin(ang) + dy * Math.cos(ang);
                }
                let dLat = (effDy * this.metersPerPixel) / 111320.0;
                let dLon = -(effDx * this.metersPerPixel) / (111320.0 * cosLat);
                this.centerLat = this.dragStartLat + dLat;
                this.centerLon = this.dragStartLon + dLon;
                if (this.followAircraft && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
                    this.followPanLatOffset = (this.followPanLatOffset || 0.0) + dLat;
                    this.followPanLonOffset = (this.followPanLonOffset || 0.0) + dLon;
                }
                this.isDragging = false;
                if (handBadge) {
                    handBadge.classList.add("hidden");
                }
                canvas.classList.remove("dragging");
                canvas.style.cursor = "default";
                document.body.style.cursor = "default";
                this.resetCanvasTransform();
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                    this.lastBaseKey = "";
                    this.drawChart();
                } else {
                    this.handleCanvasClick(
                        clientX !== undefined ? clientX : this.dragOriginX,
                        clientY !== undefined ? clientY : this.dragOriginY
                    );
                }
            };

            canvas.addEventListener("mousedown", (e) => {
                if (e.button === 2) {
                    e.preventDefault();
                    e.stopPropagation();
                    let now = Date.now();
                    if (!this._lastRightClickTs || (now - this._lastRightClickTs) > 180) {
                        this._lastRightClickTs = now;
                        this.handleCanvasRightClick(e.clientX, e.clientY);
                    }
                    return;
                }
                if (e.button !== 0) return;
                startMapDrag(e.clientX, e.clientY, e);
            });
            window.addEventListener("mousemove", (e) => {
                if (this.isDragging) {
                    moveMapDrag(e.clientX, e.clientY, e);
                }
            });
            canvas.addEventListener("mousemove", (e) => {
                if (!this.isDragging) {
                    this.handleCanvasHover(e.clientX, e.clientY);
                }
            });
            window.addEventListener("mouseup", (e) => {
                endMapDrag(e.clientX, e.clientY);
            });
            canvas.addEventListener("mouseleave", (e) => {
                this.hideStandTooltip();
                if (this.isDragging && e.buttons === 0) {
                    endMapDrag(e.clientX, e.clientY);
                }
            });
            canvas.addEventListener("wheel", (e) => {
                e.preventDefault();
                e.stopPropagation();
                let factor = (e.deltaY < 0) ? 0.80 : 1.25;
                this.applyZoomFactor(factor);
            });
            window.addEventListener("resize", () => {
                if (this.updateCanvasMetrics()) {
                    if (!this.initialFitDone && this.currentData) {
                        this.fitRouteView();
                        this.initialFitDone = true;
                    } else {
                        this.scheduleDraw();
                    }
                }
            });
            if (wrap && typeof ResizeObserver !== "undefined") {
                this._resizeObs = new ResizeObserver(() => {
                    if (this.updateCanvasMetrics()) {
                        if (!this.initialFitDone && this.currentData) {
                            this.fitRouteView();
                            this.initialFitDone = true;
                        } else {
                            this.scheduleDraw();
                        }
                    }
                });
                this._resizeObs.observe(wrap);
            }
            let ui = document.querySelector("ingame-ui");
            if (ui && ui.addEventListener) {
                ui.addEventListener("onResizeElement", () => {
                    if (this.updateCanvasMetrics()) {
                        this.scheduleDraw();
                    }
                });
            }
        }
    }

    compileFastChart(chart) {
        if (!chart) return null;
        let refLat = chart.center_lat || 0.0;
        let refLon = chart.center_lon || 0.0;
        let cosLat = Math.max(0.15, Math.cos(refLat * 0.017453292519943295));
        let mPerDegLon = 111320.0 * cosLat;
        let mPerDegLat = 111320.0;

        let toM = (lat, lon) => [(lon - refLon) * mPerDegLon, (lat - refLat) * mPerDegLat];
        let simplifyM = (mPts, minStepSq, isClosed) => {
            if (mPts.length <= 3) return mPts;
            let out = [mPts[0]];
            let last = mPts[0];
            let limit = mPts.length - 1;
            for (let i = 1; i < limit; i++) {
                let pt = mPts[i];
                let dx = pt[0] - last[0];
                let dy = pt[1] - last[1];
                if (dx * dx + dy * dy >= minStepSq) {
                    out.push(pt);
                    last = pt;
                }
            }
            out.push(mPts[limit]);
            if (isClosed && out.length < 3) return mPts;
            return out;
        };
        let withBBox = (mPts, extra) => {
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            let sumX = 0.0, sumY = 0.0;
            for (let i = 0; i < mPts.length; i++) {
                let x = mPts[i][0], y = mPts[i][1];
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
                sumX += x;
                sumY += y;
            }
            let n = Math.max(1, mPts.length);
            let res = { pts: mPts, minX: minX, maxX: maxX, minY: minY, maxY: maxY, cxM: sumX / n, cyM: sumY / n };
            if (extra) {
                Object.keys(extra).forEach(k => { res[k] = extra[k]; });
            }
            return res;
        };

        let aprons = [];
        (chart.aprons || []).forEach(ap => {
            let pts = ap.points || [];
            if (pts.length >= 3) {
                let mPts = simplifyM(pts.map(p => toM(p[0], p[1])), 16.0, true);
                aprons.push(withBBox(mPts, { name: String(ap.name || "").trim() }));
            }
        });

        let mainTaxiways = [];
        let taxilanes = [];
        let twyLabels = [];
        let labelMap = {};

        (chart.taxiways || []).forEach(twy => {
            let pts = twy.points || [];
            if (pts.length < 2) return;
            let mPts = simplifyM(pts.map(p => toM(p[0], p[1])), 12.25, false);
            let boxed = withBBox(mPts);
            let isLane = (twy.type === "taxilane");
            if (isLane) {
                taxilanes.push(boxed);
            } else {
                mainTaxiways.push(boxed);
                let ref = (twy.ref || "").trim();
                if (ref && ref.length <= 7) {
                    let candIndices = mPts.length >= 8
                        ? [Math.floor(mPts.length / 4), Math.floor(mPts.length / 2), Math.floor((3 * mPts.length) / 4)]
                        : [Math.floor(mPts.length / 2)];
                    for (let ci = 0; ci < candIndices.length; ci++) {
                        let mid = mPts[candIndices[ci]];
                        let prevList = labelMap[ref] || [];
                        let tooCloseSame = false;
                        for (let i = 0; i < prevList.length; i++) {
                            if (Math.hypot(mid[0] - prevList[i][0], mid[1] - prevList[i][1]) < 240.0) {
                                tooCloseSame = true;
                                break;
                            }
                        }
                        if (!tooCloseSame) {
                            let tooCloseAny = false;
                            for (let i = 0; i < twyLabels.length; i++) {
                                if (Math.hypot(mid[0] - twyLabels[i].xM, mid[1] - twyLabels[i].yM) < 40.0) {
                                    tooCloseAny = true;
                                    break;
                                }
                            }
                            if (!tooCloseAny) {
                                if (!labelMap[ref]) labelMap[ref] = [];
                                labelMap[ref].push(mid);
                                twyLabels.push({ ref: ref, xM: mid[0], yM: mid[1], halfW: Math.max(9, ref.length * 4 + 4) });
                            }
                        }
                    }
                }
            }
        });

        let terminals = [];
        (chart.terminals || []).forEach(term => {
            let pts = term.points || [];
            if (pts.length >= 3) {
                let mPts = simplifyM(pts.map(p => toM(p[0], p[1])), 6.25, true);
                terminals.push(withBBox(mPts, { name: String(term.name || "").trim() }));
            }
        });

        let runways = [];
        (chart.runways || []).forEach(rwy => {
            let pts = rwy.points || [];
            if (pts.length < 2) return;
            let mPts = pts.map(p => toM(p[0], p[1]));
            let endsM = {};
            Object.keys(rwy.ends || {}).forEach(k => {
                let e = rwy.ends[k];
                let [ex, ey] = toM(e.lat, e.lon);
                endsM[k] = {
                    xM: ex,
                    yM: ey,
                    lat: e.lat,
                    lon: e.lon,
                    heading: (e.heading != null && !isNaN(parseFloat(e.heading))) ? parseFloat(e.heading) : 0.0
                };
            });
            runways.push({ mPts: mPts, rawPts: pts, ends: endsM });
        });

        let holdingPoints = [];
        (chart.holding_points || []).forEach(hp => {
            if (hp.lat != null && hp.lon != null) {
                let [hxM, hyM] = toM(hp.lat, hp.lon);
                holdingPoints.push({ xM: hxM, yM: hyM });
            }
        });

        let standsAll = [];
        (chart.stands || []).forEach(st => {
            let sRef = String(st.ref || "").trim();
            if (!sRef || st.lat == null || st.lon == null) return;
            let [sxM, syM] = toM(st.lat, st.lon);
            let sClean = sRef.replace(/\s+/g, "").toUpperCase();
            let sDisp = sRef.replace(/^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*/i, "").replace(/\s+/g, "").toUpperCase() || sRef;
            standsAll.push({
                ref: sRef,
                clean: sClean,
                disp: sDisp,
                xM: sxM,
                yM: syM,
                heading: (st.heading != null && !isNaN(parseFloat(st.heading))) ? parseFloat(st.heading) : 0.0,
                airlines: Array.isArray(st.airlines) ? st.airlines.slice(0, 3) : [],
                terminal: String(st.terminal || "")
            });
        });

        return {
            refLat: refLat,
            refLon: refLon,
            mPerDegLon: mPerDegLon,
            mPerDegLat: mPerDegLat,
            aprons: aprons,
            mainTaxiways: mainTaxiways,
            taxilanes: taxilanes,
            twyLabels: twyLabels,
            terminals: terminals,
            runways: runways,
            holdingPoints: holdingPoints,
            standsAll: standsAll,
            airlineStyles: chart.airline_styles || {}
        };
    }

    getAirlineLogoImg(code) {
        if (!code) return null;
        let c = String(code).trim().toUpperCase();
        if (!c || c === "ANY" || c === "NONE") return null;
        if (!this.airlineLogos) this.airlineLogos = {};
        if (this.airlineLogos[c]) return this.airlineLogos[c];
        let img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = () => {
            this.scheduleDraw();
        };
        img.src = "http://127.0.0.1:8420/api/airline_logo?code=" + encodeURIComponent(c) + "&size=36&v=5";
        this.airlineLogos[c] = img;
        return img;
    }

    hideStandTooltip() {
        let tip = this.querySelector("#StandHoverTooltip");
        if (tip) tip.style.display = "none";
        this._hoveredStandKey = "";
    }

    handleCanvasHover(clientX, clientY) {
        let wrap = this.querySelector("#ChartWrapper");
        let canvas = this.querySelector("#LidoCanvas");
        if (!wrap) return;
        let rect = wrap.getBoundingClientRect();
        let mx = clientX - rect.left;
        let my = clientY - rect.top;

        if (this.rwyHitboxes && this.rwyHitboxes.length > 0) {
            for (let i = this.rwyHitboxes.length - 1; i >= 0; i--) {
                let rh = this.rwyHitboxes[i];
                if (mx >= rh.x0 - 3 && mx <= rh.x1 + 3 && my >= rh.y0 - 3 && my <= rh.y1 + 3) {
                    if (canvas) canvas.style.cursor = "pointer";
                    this.hideStandTooltip();
                    return;
                }
            }
        }

        if (!this.standHitboxes || this.standHitboxes.length === 0) {
            if (canvas) canvas.style.cursor = "default";
            this.hideStandTooltip();
            return;
        }
        let hit = null;
        for (let i = this.standHitboxes.length - 1; i >= 0; i--) {
            let hb = this.standHitboxes[i];
            if (mx >= (hb.x0 - 3) && mx <= (hb.x1 + 3) && my >= (hb.y0 - 3) && my <= (hb.y1 + 3)) {
                hit = hb;
                break;
            }
        }
        if (!hit) {
            if (canvas) canvas.style.cursor = "default";
            this.hideStandTooltip();
            return;
        }
        if (canvas) canvas.style.cursor = "pointer";
        let tip = this.querySelector("#StandHoverTooltip");
        if (!tip) {
            tip = document.createElement("div");
            tip.id = "StandHoverTooltip";
            tip.style.cssText =
                "position:absolute;z-index:75;pointer-events:none;background:#1B1E24;" +
                "border:1.5px solid #22D3EE;border-radius:8px;padding:6px 12px;" +
                "box-shadow:0 4px 14px rgba(0,0,0,0.65);text-align:center;white-space:nowrap;display:none;";
            wrap.appendChild(tip);
        }
        let key = hit.ref + "|" + (hit.airlines || []).join(",") + "|" + hit.terminal + "|" + (hit.isAssigned ? "1" : "0");
        if (this._hoveredStandKey !== key) {
            this._hoveredStandKey = key;
            let hdrParts = ["STAND " + hit.ref];
            if (hit.isAssigned) hdrParts.push("ASSIGNED GATE");
            if (hit.terminal) hdrParts.push(String(hit.terminal).toUpperCase());
            if (!hit.isAssigned) {
                hdrParts.push("CLICK: SELECT  |  RIGHT-CLICK: REPOSITION");
            } else {
                hdrParts.push("CLICK / RIGHT-CLICK: REPOSITION");
            }
            let hdrTxt = hdrParts.join("  |  ");
            let styles = hit.stylesMap || {};
            let alParts = [];
            (hit.airlines || []).forEach(c => {
                let st = styles[c] || {};
                let fullN = st.name || c;
                if (fullN && fullN.toUpperCase() !== c.toUpperCase()) {
                    alParts.push(fullN + " (" + c + ")");
                } else {
                    alParts.push(c);
                }
            });
            let alTxt = alParts.length > 0 ? alParts.join("   |   ") : "General Commercial Stand";
            let hdrCol = hit.isAssigned ? "#FDBA74" : "#22D3EE";
            tip.style.borderColor = hit.isAssigned ? "#F0743E" : "#22D3EE";
            tip.innerHTML =
                '<div style="font-family:monospace;font-size:10px;font-weight:700;color:' + hdrCol + ';margin-bottom:2px;">' + hdrTxt + '</div>' +
                '<div style="font-size:12px;font-weight:700;color:#ffffff;">' + alTxt + '</div>';
        }
        tip.style.display = "block";
        let tw = tip.offsetWidth || 210;
        let th = tip.offsetHeight || 46;
        let wrapW = wrap.clientWidth || 520;
        let cx = (hit.x0 + hit.x1) * 0.5;
        let left = Math.max(8, Math.min(wrapW - tw - 8, cx - tw * 0.5));
        let top = hit.y0 - th - 8;
        if (top < 42) top = hit.y1 + 8;
        tip.style.left = Math.round(left) + "px";
        tip.style.top = Math.round(top) + "px";
    }

    drawAirlineRectTile(ctx, code, x0, y0, w, h, stylesMap) {
        let c = String(code || "").trim().toUpperCase();
        if (!c) return;
        let img = this.getAirlineLogoImg(c);
        if (img && img.complete && img.naturalWidth > 0) {
            ctx.drawImage(img, x0, y0, w, h);
            return;
        }
        let st = (stylesMap && stylesMap[c]) ? stylesMap[c] : { bg: "#FFFFFF", fg: "#0F172A", bd: "#CBD5E1", iata: "" };
        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(x0, y0, w, h);
        let lbl = (st.iata && h <= 18) ? st.iata : c.slice(0, 3);
        ctx.save();
        ctx.font = "bold " + (lbl.length <= 2 ? "9px" : "7px") + " sans-serif";
        ctx.fillStyle = st.bg || "#0F172A";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(lbl, x0 + w * 0.5, y0 + h * 0.5);
        ctx.restore();
    }

    updateToolbarButtons() {
        let btnZoomIn = this.querySelector("#BtnZoomIn");
        let btnZoomOut = this.querySelector("#BtnZoomOut");
        let btnAPC = this.querySelector("#BtnAPC");
        let btnAGC = this.querySelector("#BtnAGC");
        let btnFollow = this.querySelector("#BtnFollow");
        let btnOrient = this.querySelector("#BtnOrient");
        let btnTheme = this.querySelector("#BtnTheme");

        if (btnOrient && btnOrient.parentNode) {
            btnOrient.parentNode.removeChild(btnOrient);
        }

        let cam = this.getCamaieu();
        let airborne = this.isAirborneNow();
        if (airborne || !this.followAircraft) {
            this.headingUp = false;
        } else {
            this.headingUp = true;
        }
        if (airborne) {
            this.followAircraft = false;
        }

        let baseBtnCss = "display:inline-flex;align-items:center;justify-content:center;height:34px;padding:0 13px;border-radius:8px;font-size:12.5px;font-weight:700;cursor:pointer;white-space:nowrap;margin-left:6px;color:#ffffff;";
        if (btnZoomIn) btnZoomIn.style.cssText = baseBtnCss + "margin-left:0;background-color:#2B303B;";
        if (btnZoomOut) btnZoomOut.style.cssText = baseBtnCss + "background-color:#2B303B;";
        if (btnAPC) btnAPC.style.cssText = baseBtnCss + "background-color:" + ((!this.followAircraft && this.viewMode === "terminal") ? cam.s2 : "#2B303B") + ";";
        if (btnAGC) btnAGC.style.cssText = baseBtnCss + "background-color:" + ((!this.followAircraft && this.viewMode === "route") ? cam.s2 : "#2B303B") + ";";

        if (btnFollow) {
            btnFollow.innerText = "Follow + Hdg Up";
            if (airborne) {
                btnFollow.style.cssText = baseBtnCss + "background-color:#2B303B;color:#64748B;opacity:0.5;cursor:not-allowed;";
            } else {
                btnFollow.style.cssText = baseBtnCss + "background-color:" + (this.followAircraft ? cam.s2 : "#2B303B") + ";";
            }
        }
        if (btnTheme) {
            btnTheme.innerText = (this.themeMode === "day") ? "Map Night" : "Map Day";
            btnTheme.style.cssText = baseBtnCss + "background-color:" + ((this.themeMode === "day") ? cam.s3 : "#2B303B") + ";";
        }
    }

    fetchCurrentData() {
        if (this.isDragging || this._fetchInFlight) return;
        this._fetchInFlight = true;

        let haveDep = "";
        let haveArr = "";
        if (this.currentData) {
            let dIcao = (this.currentData.departure && this.currentData.departure.icao) || "";
            let aIcao = (this.currentData.arrival && this.currentData.arrival.icao) || "";
            if (dIcao && this.fastCharts[dIcao]) haveDep = dIcao;
            if (aIcao && this.fastCharts[aIcao]) haveArr = aIcao;
        }
        let url = "http://127.0.0.1:8420/api/current?have_dep=" + encodeURIComponent(haveDep) + "&have_arr=" + encodeURIComponent(haveArr);

        fetch(url)
            .then(response => response.json())
            .then(data => {
                this._fetchInFlight = false;
                this._backendDisconnected = false;
                if (this.isDragging) return;
                let statusBox = this.querySelector("#StatusMessage");
                let efbContainer = this.querySelector("#EFBContainer");

                if (data && Object.keys(data).length > 0 && (data.departure || data.arrival)) {
                    let wasHidden = efbContainer && efbContainer.classList.contains("hidden");
                    if (statusBox) statusBox.classList.add("hidden");
                    if (efbContainer) efbContainer.classList.remove("hidden");

                    ["departure", "arrival"].forEach(ph => {
                        let apt = data[ph];
                        if (apt && apt.icao) {
                            if (apt.chart_data) {
                                this.rawCharts[apt.icao] = apt.chart_data;
                                this.fastCharts[apt.icao] = this.compileFastChart(apt.chart_data);
                            } else if (this.rawCharts[apt.icao]) {
                                apt.chart_data = this.rawCharts[apt.icao];
                            }
                        }
                    });

                    this.currentData = data;
                    if (wasHidden) {
                        this.initialFitDone = false;
                        requestAnimationFrame(() => {
                            this.updateCanvasMetrics();
                            this.renderData(data, true);
                        });
                    } else {
                        this.renderData(data, false);
                    }
                } else {
                    if (efbContainer) efbContainer.classList.add("hidden");
                    if (statusBox) {
                        statusBox.classList.remove("hidden");
                        let title = this.querySelector("#StatusTitle");
                        let text = this.querySelector("#StatusText");
                        if (title) {
                            title.innerText = "Awaiting Flight Data";
                            title.style.color = "#0284c7";
                        }
                        if (text) text.innerHTML = "Please import a flight from SimBrief in the <strong>GateFinder</strong> desktop application first.";
                    }
                }
            })
            .catch(err => {
                this._fetchInFlight = false;
                this._backendDisconnected = true;
                if (this.isDragging) return;
                if (this.currentData && (this.currentData.departure || this.currentData.arrival)) {
                    return;
                }
                let efbContainer = this.querySelector("#EFBContainer");
                if (efbContainer) efbContainer.classList.add("hidden");
                let statusBox = this.querySelector("#StatusMessage");
                if (statusBox) {
                    statusBox.classList.remove("hidden");
                    let title = this.querySelector("#StatusTitle");
                    let text = this.querySelector("#StatusText");
                    if (title) {
                        title.innerText = "GateFinder is not running";
                        title.style.color = "#ef4444";
                    }
                    if (text) text.innerHTML = "Please launch the <strong>GateFinder</strong> desktop application first to fetch airport and gate details.";
                }
            });
    }

    renderData(data, forceChartRedraw) {
        this.injectCoreStyles();
        let uAc = data.user_aircraft || {};
        let isAirborne = Boolean(data.is_airborne);
        let justTouchedDown = Boolean(this._wasAirborne && !isAirborne && uAc.connected && uAc.on_ground === true);
        this._wasAirborne = isAirborne;
        let cam = this.getCamaieu(data);

        if (isAirborne) {
            this.manualPhaseOverride = false;
            if (this.activePhase !== "arrival") {
                this.activePhase = "arrival";
                this.initialFitDone = false;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
            }
            if (this.followAircraft || this.headingUp) {
                this.followAircraft = false;
                this.headingUp = false;
            }
        } else if (data.recommended_phase && !this.manualPhaseOverride) {
            if (data.recommended_phase !== this.activePhase) {
                this.activePhase = data.recommended_phase;
                this.initialFitDone = false;
                this.lastSidebarSig = "";
                this.lastChartSig = "";
            }
        }
        this.updateToolbarButtons();

        // 1. Top Header Strip (Wide Logo Outside Pill + Airline / Callsign / Reg / Aircraft Pills)
        let rawAl = this.sanitizeText(data.airline || "AIRLINE");
        let alCodeHdr = rawAl.indexOf("-") !== -1 ? rawAl.split("-")[0].trim().toUpperCase() : rawAl.slice(0, 3).trim().toUpperCase();
        let logoWide = this.querySelector("#al_logo_wide");
        if (logoWide) {
            logoWide.style.cssText = "width:92px;height:40px;border-radius:7px;object-fit:contain;background-color:#ffffff;flex-shrink:0;display:block;margin-right:10px;";
            if (alCodeHdr && alCodeHdr !== "AIR") {
                let wantSrc = "http://127.0.0.1:8420/api/airline_logo?code=" + encodeURIComponent(alCodeHdr) + "&size=40&width=90&radius=7&v=6";
                if (logoWide.getAttribute("data-code") !== alCodeHdr) {
                    logoWide.setAttribute("data-code", alCodeHdr);
                    logoWide.src = wantSrc;
                }
                logoWide.classList.remove("hidden");
            } else {
                logoWide.classList.add("hidden");
            }
        }

        let hdrPillCss = "display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 18px;border-radius:8px;font-weight:700;font-size:14px;color:#ffffff;white-space:nowrap;margin-right:10px;box-sizing:border-box;";

        let alVal = this.querySelector("#al_val");
        if (alVal) {
            alVal.innerText = rawAl;
            alVal.style.cssText = hdrPillCss + "background-color:" + cam.s1 + ";";
        }

        let csVal = this.querySelector("#cs_val");
        if (csVal) {
            let csStr = this.sanitizeText(data.callsign || "");
            if (csStr) {
                csVal.innerText = csStr;
                csVal.style.cssText = hdrPillCss + "background-color:" + cam.s2 + ";";
                csVal.classList.remove("hidden");
            } else {
                csVal.classList.add("hidden");
            }
        }

        let regVal = this.querySelector("#reg_val");
        if (regVal) {
            let regStr = this.sanitizeText(data.registration || "");
            if (regStr) {
                regVal.innerText = regStr;
                regVal.style.cssText = hdrPillCss + "background-color:" + cam.s3 + ";";
                regVal.classList.remove("hidden");
            } else {
                regVal.classList.add("hidden");
            }
        }

        let acVal = this.querySelector("#ac_val");
        if (acVal) {
            acVal.innerText = this.sanitizeText(data.aircraft_version || data.aircraft || "AIRCRAFT");
            acVal.style.cssText = hdrPillCss + "background-color:" + cam.s4 + ";margin-right:0;";
        }

        // 2. Phase Selector Cards (DEPARTURE vs ARRIVAL with 3 Camaïeu Pills each)
        let dep = data.departure || {};
        let arr = data.arrival || {};
        let tabDep = this.querySelector("#TabDep");
        let tabArr = this.querySelector("#TabArr");

        let depIcao = String(dep.icao || "----").toUpperCase();
        let depStand = dep.gate ? ("STAND " + dep.gate) : "NO STAND";
        let depRwy = dep.selected_runway ? ("RWY " + dep.selected_runway) : "RWY --";

        let arrIcao = String(arr.icao || "----").toUpperCase();
        let arrStand = arr.gate ? ("STAND " + arr.gate) : "NO STAND";
        let arrRwy = arr.selected_runway ? ("RWY " + arr.selected_runway) : "RWY --";

        let miniPillStyle = "display:inline-flex;align-items:center;justify-content:center;height:34px;padding:0 15px;border-radius:7px;font-weight:700;font-size:13.5px;color:#ffffff;white-space:nowrap;margin-right:8px;";
        let phaseTitleStyle = "font-weight:700;font-size:15px;color:#ffffff;margin-right:14px;letter-spacing:0.5px;";

        if (tabDep) {
            let isDepAct = (this.activePhase === "departure");
            tabDep.style.backgroundColor = isDepAct ? (cam.card_sel_bg || "#25343D") : "#1B1E24";
            tabDep.style.opacity = isAirborne ? "0.45" : "1.0";
            tabDep.style.marginRight = "8px";
            let depKey = depIcao + "|" + depStand + "|" + depRwy + "|" + cam.s1 + "|" + cam.s2 + "|" + cam.s3;
            if (tabDep.getAttribute("data-key") !== depKey) {
                tabDep.setAttribute("data-key", depKey);
                tabDep.innerHTML =
                    '<span style="' + phaseTitleStyle + '">DEPARTURE</span>' +
                    '<span style="' + miniPillStyle + 'background:' + cam.s1 + ';">' + depIcao + '</span>' +
                    '<span style="' + miniPillStyle + 'background:' + cam.s2 + ';">' + depStand + '</span>' +
                    '<span style="' + miniPillStyle + 'margin-right:0;background:' + cam.s3 + ';">' + depRwy + '</span>';
            }
        }

        if (tabArr) {
            let isArrAct = (this.activePhase === "arrival");
            tabArr.style.backgroundColor = isArrAct ? (cam.card_sel_bg || "#25343D") : "#1B1E24";
            let s5 = cam.s5 || cam.s2;
            let s6 = cam.s6 || cam.s3;
            let arrKey = arrIcao + "|" + arrStand + "|" + arrRwy + "|" + cam.s4 + "|" + s5 + "|" + s6;
            if (tabArr.getAttribute("data-key") !== arrKey) {
                tabArr.setAttribute("data-key", arrKey);
                tabArr.innerHTML =
                    '<span style="' + phaseTitleStyle + '">ARRIVAL</span>' +
                    '<span style="' + miniPillStyle + 'background:' + cam.s4 + ';">' + arrIcao + '</span>' +
                    '<span style="' + miniPillStyle + 'background:' + s5 + ';">' + arrStand + '</span>' +
                    '<span style="' + miniPillStyle + 'margin-right:0;background:' + s6 + ';">' + arrRwy + '</span>';
            }
        }

        let aptData = (this.activePhase === "departure") ? dep : arr;
        let tr = aptData.taxi_route || {};

        // 3. SimConnect Status Pill in Map Top Bar (left side, grey background, white text)
        let scVal = this.querySelector("#sc_val");
        if (scVal) {
            let scTxt = "SimConnect Standby";
            if (aptData.ai_cleared) {
                scTxt = "AI Aircraft Cleared from Stand";
            } else if (aptData.ai_active) {
                scTxt = "Gate Secured (Auto-Clear Active)";
            } else if (aptData.simconnect_connected || uAc.connected) {
                scTxt = "SimConnect Connected (Stand Monitored)";
            }
            if (scVal.innerText !== scTxt) {
                scVal.innerText = scTxt;
            }
            scVal.style.cssText = "display:inline-flex;align-items:center;height:34px;padding:0 14px;border-radius:8px;background-color:#2B303B;color:#FFFFFF;font-size:12.5px;font-weight:700;white-space:nowrap;";
        }

        let sig = JSON.stringify([
            this.activePhase, aptData.icao, aptData.gate, aptData.gate_source,
            aptData.selected_runway, aptData.atc_runway, aptData.bypassed_summary,
            cam.s1, cam.s2, cam.s3, cam.s4
        ]);

        if (sig !== this.lastSidebarSig) {
            this.lastSidebarSig = sig;
            this.renderSidebar(aptData, data);
        } else {
            this.updateLiveSidebarElements(aptData, data);
        }

        this.syncLiveStandModal(data.pending_live_stand_prompt, isAirborne, uAc);

        let rawHib = Boolean(data.map_hibernated);
        if (!rawHib) {
            this.inflightPreviewOverride = false;
        }
        let effHib = rawHib && !this.inflightPreviewOverride;
        let chartWrap = this.querySelector("#ChartWrapper");
        let lidoCanvas = this.querySelector("#LidoCanvas");
        let toolbar = this.querySelector(".chart-toolbar");
        let chartTopBar = this.querySelector(".chart-top-bar");
        let resumeBtn = this.querySelector("#BtnResumeStandby");
        if (rawHib && this.inflightPreviewOverride && chartTopBar) {
            if (!resumeBtn) {
                resumeBtn = document.createElement("span");
                resumeBtn.id = "BtnResumeStandby";
                resumeBtn.style.cssText = "background:" + cam.s1 + ";color:#ffffff;font-size:10px;font-weight:700;padding:4px 10px;border-radius:6px;cursor:pointer;margin-left:8px;";
                resumeBtn.innerText = "Resume In-Flight Standby";
                resumeBtn.addEventListener("click", () => {
                    this.inflightPreviewOverride = false;
                    this.lastChartSig = "";
                    if (this.currentData) this.renderData(this.currentData, true);
                });
                chartTopBar.appendChild(resumeBtn);
            }
            resumeBtn.style.display = "inline-block";
        } else if (resumeBtn) {
            resumeBtn.style.display = "none";
        }

        let standbyOverlay = this.querySelector("#InFlightStandbyOverlay");
        if (effHib) {
            if (lidoCanvas) lidoCanvas.style.display = "none";
            if (toolbar) toolbar.style.display = "none";
            if (!standbyOverlay && chartWrap) {
                standbyOverlay = document.createElement("div");
                standbyOverlay.id = "InFlightStandbyOverlay";
                chartWrap.appendChild(standbyOverlay);
            }
            if (standbyOverlay) {
                standbyOverlay.style.cssText = "position:absolute;top:0;left:0;right:0;bottom:0;width:100%;height:100%;box-sizing:border-box;display:flex;align-items:center;justify-content:center;background:#1B1E24;z-index:45;padding:20px;";
                let arrIcaoS = (arr && arr.icao) || "DEST";
                let arrGateS = (arr && arr.gate) || "N/A";
                let arrRwyS = (arr && arr.selected_runway) || "AUTO";
                let ovKey = arrIcaoS + ":" + arrGateS + ":" + arrRwyS + ":" + cam.s1;
                if (standbyOverlay.getAttribute("data-key") !== ovKey) {
                    standbyOverlay.setAttribute("data-key", ovKey);
                    standbyOverlay.innerHTML =
                        '<div style="background:#2B303B;border-radius:10px;padding:22px 26px;max-width:420px;text-align:center;">' +
                        '<div style="color:' + (cam.accent || "#38bdf8") + ';font-size:11px;font-weight:700;letter-spacing:0.6px;margin-bottom:8px;">IN-FLIGHT LOW-POWER STANDBY  |  WHEELS OFF</div>' +
                        '<div style="color:#ffffff;font-size:15px;font-weight:700;margin-bottom:8px;">Lido Ground Chart Paused During Flight</div>' +
                        '<div style="color:#cbd5e1;font-size:12px;line-height:1.45;margin-bottom:16px;">Chart rendering is automatically suspended while airborne.<br/>Auto-resumes at Touchdown (Wheels-On) at <strong>' + arrIcaoS + '</strong> (Stand ' + arrGateS + ' | RWY ' + arrRwyS + ').</div>' +
                        '<div id="BtnPreviewInflight" style="display:inline-block;background:' + cam.s1 + ';color:#ffffff;font-size:12px;font-weight:700;padding:7px 18px;border-radius:6px;cursor:pointer;">Preview Chart Now</div>' +
                        '</div>';
                    let btnPrev = standbyOverlay.querySelector("#BtnPreviewInflight");
                    if (btnPrev) {
                        btnPrev.addEventListener("click", () => {
                            this.inflightPreviewOverride = true;
                            this.activePhase = "arrival";
                            this.followAircraft = false;
                            this.headingUp = false;
                            this.lastChartSig = "";
                            if (this.currentData) this.renderData(this.currentData, true);
                        });
                    }
                }
            }
            return;
        } else {
            if (standbyOverlay) standbyOverlay.style.display = "none";
            if (lidoCanvas) lidoCanvas.style.display = "block";
            if (toolbar) toolbar.style.display = "flex";
        }

        let routeFitKey = this.activePhase + ":" + (aptData.icao || "") + ":" + (aptData.gate || "") + ":" + (aptData.selected_runway || "");
        if (this.lastFittedRouteKey !== routeFitKey) {
            this.lastFittedRouteKey = routeFitKey;
            this.initialFitDone = false;
        }

        if (!this.initialFitDone) {
            let engageTouchdownFollow = Boolean(
                !isAirborne &&
                this.activePhase === "arrival" &&
                (justTouchedDown || tr.live_status === "LANDING_ROLL" || tr.live_status === "TAXI_IN") &&
                uAc && uAc.lat != null && uAc.lon != null
            );
            let applyInitialView = () => {
                if (engageTouchdownFollow) {
                    this.followAircraft = true;
                    this.headingUp = true;
                    this.applySmartFollowCamera(true);
                    this.updateToolbarButtons();
                    this.scheduleDraw();
                } else {
                    this.fitRouteView();
                }
                this.initialFitDone = true;
            };
            this.updateCanvasMetrics();
            if (this.canvasW >= 100 && this.canvasH >= 100) {
                applyInitialView();
            } else {
                requestAnimationFrame(() => {
                    this.updateCanvasMetrics();
                    applyInitialView();
                });
            }
            return;
        }

        let acLatGrid = (uAc && uAc.lat != null) ? Math.round(uAc.lat * 100000) : null;
        let acLonGrid = (uAc && uAc.lon != null) ? Math.round(uAc.lon * 100000) : null;
        let acHdgGrid = (uAc && uAc.heading != null) ? Math.round(uAc.heading * 1.0) : null;
        let chartSig = JSON.stringify([
            this.activePhase, aptData.icao, aptData.gate, aptData.selected_runway,
            tr.clearance_text, uAc.connected, acLatGrid, acLonGrid, acHdgGrid, cam.s1
        ]);

        let prevSt = this.lastLiveStatus;
        this.lastLiveStatus = tr.live_status;

        if (
            !isAirborne &&
            this.activePhase === "arrival" &&
            (
                justTouchedDown ||
                ((tr.live_status === "LANDING_ROLL" || tr.live_status === "TAXI_IN") &&
                 prevSt !== "LANDING_ROLL" && prevSt !== "TAXI_IN")
            ) &&
            uAc && uAc.lat != null && uAc.lon != null
        ) {
            this.followAircraft = true;
            this.headingUp = true;
            this.applySmartFollowCamera(true);
            this.updateToolbarButtons();
            forceChartRedraw = true;
        }

        if (this.followAircraft && this.activePhase === "departure" && tr.live_status === "ON_RUNWAY") {
            this.followAircraft = false;
            this.updateToolbarButtons();
            this.fitRouteView();
            return;
        }

        if (forceChartRedraw || chartSig !== this.lastChartSig) {
            this.lastChartSig = chartSig;
            if (this.followAircraft && !isAirborne && uAc && uAc.lat != null) {
                this.applySmartFollowCamera(false);
            }
            if (!this.isDragging && !this.wheelSettleTimer) {
                this.scheduleDraw();
            }
        }
    }

    buildClearancePillsModel(clearanceStr, selRwy, detExit) {
        let rawParts = String(clearanceStr || "").split(/\s*(?:->|\u2794)\s*/).map(s => s.trim()).filter(Boolean);
        let tokens = [];
        for (let i = 0; i < rawParts.length; i++) {
            let p = rawParts[i];
            let pNorm = p.toUpperCase().replace(/^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*/, "").replace(/\s+/g, "");
            if (tokens.length > 0) {
                let prevNorm = tokens[tokens.length - 1].toUpperCase().replace(/^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*/, "").replace(/\s+/g, "");
                if (pNorm && pNorm === prevNorm) {
                    if (p.length > tokens[tokens.length - 1].length) {
                        tokens[tokens.length - 1] = p;
                    }
                    continue;
                }
            }
            tokens.push(p);
        }
        if (tokens.length === 0) {
            tokens = [String(clearanceStr || "ROUTE READY").trim()];
        }

        let selRwyClean = String(selRwy || "").replace(/^RWY\s*/i, "").trim().toUpperCase();
        let detExitClean = String(detExit || "").trim();
        let isArr = (this.activePhase === "arrival");
        let items = [];
        let hasRwyDropdown = false;
        let hasExitPill = false;

        for (let i = 0; i < tokens.length; i++) {
            let tok = tokens[i];

            // 1. Arrival combined "RWY 02 (Exit W5)" -> split into ("RWY 02") + ("EXIT : W5")
            let mRwyExit = tok.match(/^RWY\s+([0-9]{1,2}[LRC]?)\s*\(\s*Exit\s+([^)]+)\s*\)$/i);
            if (mRwyExit) {
                let rId = mRwyExit[1].toUpperCase();
                let exId = mRwyExit[2].trim();
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                if (exId) {
                    items.push({ kind: "EXIT_PILL", text: "EXIT : " + exId });
                    hasExitPill = true;
                }
                continue;
            }

            // 2. Arrival live states: "Next Exit W5", "Exit W5", "Vacated RWY 02"
            let mLiveExit = tok.match(/^(?:Next\s+)?Exit\s+(.+)$/i);
            if (mLiveExit && isArr) {
                let exId = mLiveExit[1].trim();
                let rId = selRwyClean || "--";
                if (!hasRwyDropdown) {
                    items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                    hasRwyDropdown = true;
                }
                if (exId && !hasExitPill) {
                    items.push({ kind: "EXIT_PILL", text: "EXIT : " + exId });
                    hasExitPill = true;
                }
                continue;
            }

            let mVacRwy = tok.match(/^Vacated\s+RWY\s+([0-9]{1,2}[LRC]?)$/i);
            if (mVacRwy) {
                let rId = mVacRwy[1].toUpperCase();
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                if (detExitClean && !hasExitPill && isArr) {
                    items.push({ kind: "EXIT_PILL", text: "EXIT : " + detExitClean });
                    hasExitPill = true;
                }
                continue;
            }

            // 3. Departure "Hold D (RWY 20)" or "Hold Short RWY 20"
            let mHoldNamed = tok.match(/^Hold\s+(.+?)\s*\(\s*RWY\s+([0-9]{1,2}[LRC]?)\s*\)$/i);
            if (mHoldNamed) {
                let hName = mHoldNamed[1].trim();
                let rId = mHoldNamed[2].toUpperCase();
                if (hName && hName.toUpperCase() !== "SHORT") {
                    if (items.length === 0 || items[items.length - 1].text.toUpperCase() !== hName.toUpperCase()) {
                        items.push({ kind: "NORMAL", text: hName });
                    }
                }
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                continue;
            }

            let mHoldShort = tok.match(/^Hold\s+Short\s+RWY\s+([0-9]{1,2}[LRC]?)$/i);
            if (mHoldShort) {
                let rId = mHoldShort[1].toUpperCase();
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                continue;
            }

            // 4. Departure "RWY 20 Entered"
            let mRwyEnt = tok.match(/^RWY\s+([0-9]{1,2}[LRC]?)\s+Entered$/i);
            if (mRwyEnt) {
                let rId = mRwyEnt[1].toUpperCase();
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                items.push({ kind: "NORMAL", text: "Entered" });
                continue;
            }

            // 5. Plain "RWY 20"
            let mPlainRwy = tok.match(/^RWY\s+([0-9]{1,2}[LRC]?|--)$/i);
            if (mPlainRwy) {
                let rId = mPlainRwy[1].toUpperCase();
                if (rId === "--" && selRwyClean) rId = selRwyClean;
                items.push({ kind: "RWY_DROPDOWN", text: "RWY " + rId });
                hasRwyDropdown = true;
                if (isArr && detExitClean && !hasExitPill) {
                    items.push({ kind: "EXIT_PILL", text: "EXIT : " + detExitClean });
                    hasExitPill = true;
                }
                continue;
            }

            items.push({ kind: "NORMAL", text: tok });
        }

        if (!hasRwyDropdown && selRwyClean) {
            let rwyItem = { kind: "RWY_DROPDOWN", text: "RWY " + selRwyClean };
            if (isArr) {
                let ins = [rwyItem];
                if (detExitClean && !hasExitPill) {
                    ins.push({ kind: "EXIT_PILL", text: "EXIT : " + detExitClean });
                }
                items = ins.concat(items);
            } else {
                items.push(rwyItem);
            }
        }
        return items;
    }

    populateClearancePillsContainer(container, aptData, cam) {
        if (!container || !aptData) return;
        let tr = aptData.taxi_route || {};
        let gateVal = aptData.gate || "N/A";
        if (aptData.osm && gateVal !== "N/A") gateVal = "Stand " + gateVal;
        let selRwy = aptData.selected_runway || "RWY";
        let detExit = tr.detected_exit || "";
        let clearanceStr = (tr.clearance_text || ("Stand " + gateVal + " -> RWY " + selRwy)).replace(/\u2794/g, "->");
        let items = this.buildClearancePillsModel(clearanceStr, selRwy, detExit);

        let availRwys = (aptData.available_runways || []).slice();
        let selRwyClean = String(selRwy).replace(/^RWY\s*/i, "").trim().toUpperCase();
        if (selRwyClean && availRwys.indexOf(selRwyClean) === -1) {
            availRwys.unshift(selRwyClean);
        }

        let pool = [cam.s1, cam.s2, cam.s3, cam.s4, cam.s5 || cam.s2, cam.s6 || cam.s3];
        let sig = JSON.stringify({ items: items, avail: availRwys, pool: pool, atc: aptData.atc_runway });
        if (container.getAttribute("data-sig") === sig) return;
        container.setAttribute("data-sig", sig);
        container.innerHTML = "";

        let atcRwy = aptData.atc_runway ? String(aptData.atc_runway).toUpperCase() : "";
        let atcSrc = aptData.atc_runway_source || aptData.runway_source || "AI ATC";
        let shortAtcSrc = (atcSrc.indexOf("Beyond") !== -1) ? "BATC" : ((atcSrc.indexOf("Say") !== -1) ? "SI" : "ATC");

        let pillBaseCss = "display:inline-flex;align-items:center;justify-content:center;color:#ffffff;font-size:13.5px;font-weight:700;padding:7px 14px;border-radius:8px;margin-right:7px;margin-bottom:7px;white-space:nowrap;box-sizing:border-box;";

        items.forEach((item, idx) => {
            let bg = pool[idx % pool.length];
            if (item.kind === "RWY_DROPDOWN" && availRwys.length > 0) {
                let ddWrap = document.createElement("div");
                ddWrap.className = "rwy-dropdown-wrap";
                ddWrap.style.cssText = "position:relative;display:inline-block;flex-shrink:0;margin-right:6px;margin-bottom:6px;";

                let ddBtn = document.createElement("div");
                ddBtn.className = "clearance-pill rwy-dropdown-pill";
                ddBtn.style.cssText = pillBaseCss + "margin-right:0;margin-bottom:0;cursor:pointer;background-color:" + bg + ";";
                ddBtn.innerHTML =
                    '<span>' + item.text + '</span>' +
                    '<svg width="9" height="6" viewBox="0 0 10 6" style="flex-shrink:0;margin-left:5px;">' +
                    '<path d="M1 1 L5 5 L9 1" stroke="#ffffff" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '</svg>';

                let ddMenu = document.createElement("div");
                ddMenu.className = "rwy-dropdown-menu hidden";
                ddMenu.style.cssText = "position:absolute;top:calc(100% + 4px);left:0;min-width:118px;background-color:#1B1E24;border:1px solid #4B5563;border-radius:7px;box-shadow:0 8px 20px rgba(0,0,0,0.85);z-index:300;overflow:hidden;padding:3px;";

                availRwys.forEach(r => {
                    let rClean = String(r).replace(/^RWY\s*/i, "").trim().toUpperCase();
                    let row = document.createElement("div");
                    row.className = "rwy-dropdown-item";
                    row.style.cssText = "padding:6px 10px;font-size:11.5px;font-weight:700;color:#ffffff;cursor:pointer;display:flex;justify-content:space-between;align-items:center;border-radius:5px;margin-bottom:2px;background-color:" + ((rClean === selRwyClean) ? cam.s1 : "#2B303B") + ";";

                    let lbl = document.createElement("span");
                    lbl.innerText = "RWY " + rClean;
                    row.appendChild(lbl);

                    if (atcRwy && rClean === atcRwy) {
                        let tag = document.createElement("span");
                        tag.className = "rwy-atc-tag";
                        tag.style.cssText = "font-size:9px;background-color:#065f46;color:#34d399;padding:1px 4px;border-radius:3px;margin-left:6px;";
                        tag.innerText = shortAtcSrc;
                        row.appendChild(tag);
                    }

                    row.addEventListener("click", (e) => {
                        e.stopPropagation();
                        ddMenu.classList.add("hidden");
                        this.requestRunwayChange(rClean);
                    });
                    ddMenu.appendChild(row);
                });

                ddBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    let wasHidden = ddMenu.classList.contains("hidden");
                    let allMenus = this.querySelectorAll(".rwy-dropdown-menu");
                    allMenus.forEach(m => m.classList.add("hidden"));
                    if (wasHidden) ddMenu.classList.remove("hidden");
                });

                ddWrap.appendChild(ddBtn);
                ddWrap.appendChild(ddMenu);
                container.appendChild(ddWrap);
            } else {
                let p = document.createElement("span");
                p.className = "clearance-pill";
                p.style.cssText = pillBaseCss + "background-color:" + bg + ";";
                p.innerText = item.text;
                container.appendChild(p);
            }
        });

        if (!this._globalDropdownClickBound) {
            this._globalDropdownClickBound = true;
            document.addEventListener("click", () => {
                let openMenus = this.querySelectorAll(".rwy-dropdown-menu");
                openMenus.forEach(m => m.classList.add("hidden"));
            });
        }
    }

    renderSidebar(aptData, flightData) {
        let sidebar = this.querySelector("#LeftSidebar");
        if (!sidebar) return;
        sidebar.innerHTML = "";
        if (!aptData) return;

        let cam = this.getCamaieu(flightData);
        let isDep = (this.activePhase === "departure");

        // ============================================================
        // CARD 1: Airport & Assigned Stand Hero Card
        // ============================================================
        let gateCard = document.createElement("div");
        gateCard.className = "efb-card";
        gateCard.style.cssText = "background-color:#1B1E24;border-radius:10px;padding:14px 12px;margin-bottom:8px;box-sizing:border-box;flex-shrink:0;";

        let aptTitle = document.createElement("div");
        aptTitle.className = "apt-hero-title";
        aptTitle.style.cssText = "font-size:17px;font-weight:700;color:#ffffff;text-align:center;margin-bottom:4px;line-height:1.25;";
        aptTitle.innerText = (aptData.icao || "") + (aptData.name ? " - " + aptData.name : "");
        gateCard.appendChild(aptTitle);

        let cityStr = String(aptData.city || aptData.terminal || "").trim();
        if (cityStr) {
            let citySub = document.createElement("div");
            citySub.className = "apt-hero-city";
            citySub.style.cssText = "font-size:14px;font-weight:700;color:#cbd5e1;text-align:center;margin-bottom:12px;line-height:1.2;";
            citySub.innerText = cityStr;
            gateCard.appendChild(citySub);
        }

        if (aptData.error && !aptData.osm) {
            let errDiv = document.createElement("div");
            errDiv.style.cssText = "color:#EF4444;font-size:11px;font-weight:700;text-align:center;margin-bottom:6px;";
            errDiv.innerText = aptData.error;
            gateCard.appendChild(errDiv);
        }

        let gateWrap = document.createElement("div");
        gateWrap.className = "gate-hero-pill-wrap";
        gateWrap.style.cssText = "display:flex;justify-content:center;align-items:center;margin-top:2px;margin-bottom:15px;";
        let gBadge = document.createElement("div");
        gBadge.className = "gate-hero-pill";
        gBadge.style.cssText = "display:inline-block;color:#ffffff;font-size:30px;font-weight:700;padding:8px 30px;border-radius:9px;text-align:center;min-width:112px;line-height:1.15;box-sizing:border-box;background-color:" + cam.s1 + ";";
        let gateVal = aptData.gate || "N/A";
        gBadge.innerText = aptData.osm && gateVal !== "N/A" ? ("Stand " + gateVal) : gateVal;
        gateWrap.appendChild(gBadge);
        gateCard.appendChild(gateWrap);

        // 2x2 Info Pills (2 Flexbox Rows — CoherentGT safe)
        let cellCss = "flex:1;color:#ffffff;font-size:12px;font-weight:700;padding:8px 8px;border-radius:8px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-sizing:border-box;";

        let row1 = document.createElement("div");
        row1.className = "info-pills-row";
        row1.style.cssText = "display:flex;flex-direction:row;width:100%;margin-bottom:7px;";

        let termStr = String(aptData.terminal || "MAIN APRON").toUpperCase();
        let hasJetway = (aptData.has_jetway !== undefined && aptData.has_jetway !== null)
            ? Boolean(aptData.has_jetway)
            : (aptData.type === "GATE" || aptData.type === "DOCK");
        let isCargo = termStr.indexOf("CARGO") !== -1 || Boolean(aptData.is_cargo);
        let boardingTxt = (isCargo && hasJetway) ? "Cargo Jetway / Ramp" : (isCargo ? "Cargo Ramp" : (hasJetway ? "Jetway boarding" : "Walk / Bus boarding"));

        let pBoarding = document.createElement("div");
        pBoarding.className = "info-grid-pill left-col";
        pBoarding.style.cssText = cellCss + "margin-right:7px;background-color:" + cam.s2 + ";";
        pBoarding.innerText = boardingTxt;
        row1.appendChild(pBoarding);

        let pWingspan = document.createElement("div");
        pWingspan.className = "info-grid-pill";
        pWingspan.style.cssText = cellCss + "background-color:" + cam.s3 + ";";
        if (aptData.max_wingspan && aptData.max_wingspan < 900) {
            pWingspan.innerText = "Max Wingspan: " + Number(aptData.max_wingspan).toFixed(1) + "m";
        } else {
            pWingspan.innerText = "Wingspan: Unlimited";
        }
        row1.appendChild(pWingspan);
        gateCard.appendChild(row1);

        let row2 = document.createElement("div");
        row2.className = "info-pills-row";
        row2.style.cssText = "display:flex;flex-direction:row;width:100%;";

        let rawSrc = String(aptData.gate_source || "GateFinder").toUpperCase();
        let cleanSrc = "GateFinder";
        if (rawSrc.indexOf("BEYOND") !== -1) cleanSrc = "BeyondATC";
        else if (rawSrc.indexOf("SAYINTENTIONS") !== -1) cleanSrc = "SayIntentions.AI";
        else if (rawSrc.indexOf("GSX") !== -1) cleanSrc = "GSX Pro";
        else if (rawSrc.indexOf("MANUAL") !== -1) cleanSrc = "Manual Selection";
        else if (rawSrc.indexOf("LIVE") !== -1 || rawSrc.indexOf("PARKED") !== -1) cleanSrc = "MSFS Live";

        let pSource = document.createElement("div");
        pSource.className = "info-grid-pill left-col";
        pSource.style.cssText = cellCss + "margin-right:7px;background-color:" + cam.s4 + ";";
        pSource.innerText = cleanSrc;
        row2.appendChild(pSource);

        if (!isDep) {
            let gsxSt = aptData.gsx_status || {};
            let rawGsx = String(gsxSt.label || "").toUpperCase();
            let shortGsx = "GSX Pro: Armed";
            if (rawGsx.indexOf("INJECTED") !== -1 || rawGsx.indexOf("SYNCED") !== -1 || rawGsx.indexOf("ACTIVE") !== -1) {
                shortGsx = "GSX Pro: Synced";
            }
            let pGsx = document.createElement("div");
            pGsx.id = "LiveGsxPill";
            pGsx.className = "info-grid-pill clickable";
            pGsx.style.cssText = cellCss + "cursor:pointer;background-color:" + (cam.s5 || cam.s2) + ";";
            pGsx.innerText = shortGsx;
            pGsx.addEventListener("click", (e) => {
                e.stopPropagation();
                fetch("http://127.0.0.1:8420/api/trigger_gsx?phase=arrival")
                    .then(r => r.json())
                    .then(d => {
                        ["departure", "arrival"].forEach(ph => {
                            if (d[ph] && d[ph].icao && !d[ph].chart_data && this.rawCharts[d[ph].icao]) {
                                d[ph].chart_data = this.rawCharts[d[ph].icao];
                            }
                        });
                        this.currentData = d;
                        this.renderData(d, false);
                    });
            });
            row2.appendChild(pGsx);
        } else {
            let spacer = document.createElement("div");
            spacer.style.cssText = "flex:1;height:1px;";
            row2.appendChild(spacer);
        }

        gateCard.appendChild(row2);
        sidebar.appendChild(gateCard);

        // ============================================================
        // CARD 2: ATC Taxi Clearance & Live Status Card
        // ============================================================
        let routeCard = document.createElement("div");
        routeCard.className = "efb-card efb-card-expand";
        routeCard.style.cssText = "background-color:#1B1E24;border-radius:10px;padding:14px 12px;margin-bottom:8px;box-sizing:border-box;flex:1 1 auto;display:flex;flex-direction:column;min-height:0;";

        let stBanner = document.createElement("div");
        stBanner.id = "LiveStatusBanner";
        stBanner.className = "live-status-pill";
        stBanner.style.cssText = "background-color:#2B303B;color:#ffffff;font-size:11.5px;font-weight:700;padding:8px 12px;border-radius:8px;text-align:center;margin-bottom:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
        routeCard.appendChild(stBanner);

        let clearHdr = document.createElement("div");
        clearHdr.className = "section-header-white";
        clearHdr.style.cssText = "font-size:12.5px;font-weight:700;color:#ffffff;margin-bottom:9px;letter-spacing:0.35px;white-space:nowrap;";
        clearHdr.innerText = "ATC TAXI CLEARANCE";
        routeCard.appendChild(clearHdr);

        let pillsWrap = document.createElement("div");
        pillsWrap.id = "ClearancePillsContainer";
        pillsWrap.className = "pills-flow-wrap";
        pillsWrap.style.cssText = "display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;";
        routeCard.appendChild(pillsWrap);

        sidebar.appendChild(routeCard);

        // ============================================================
        // CARD 3: Traffic & Stand Status Card
        // ============================================================
        let secCard = document.createElement("div");
        secCard.className = "efb-card";
        secCard.style.cssText = "background-color:#1B1E24;border-radius:10px;padding:14px 12px;margin-bottom:0;box-sizing:border-box;flex-shrink:0;";

        let secTitle = document.createElement("div");
        secTitle.className = "section-header-white";
        secTitle.style.cssText = "font-size:12.5px;font-weight:700;color:#ffffff;margin-bottom:9px;letter-spacing:0.35px;white-space:nowrap;";
        secTitle.innerText = "TRAFFIC & STAND STATUS";
        secCard.appendChild(secTitle);

        let trafficWrap = document.createElement("div");
        trafficWrap.id = "TrafficPillsContainer";
        trafficWrap.className = "pills-flow-wrap";
        trafficWrap.style.cssText = "display:flex;flex-direction:row;flex-wrap:wrap;align-items:center;";
        secCard.appendChild(trafficWrap);

        sidebar.appendChild(secCard);

        this.updateLiveSidebarElements(aptData, flightData);
    }

    updateLiveSidebarElements(aptData, flightData) {
        if (!aptData) return;
        let cam = this.getCamaieu(flightData || this.currentData);
        let tr = aptData.taxi_route || {};
        let isDep = (this.activePhase === "departure");
        let liveStatus = tr.live_status || "PLANNED";
        let detExit = tr.detected_exit;

        let statusMap = {
            "PARKED": "PARKED AT GATE  -  READY FOR TAXI",
            "TAXI_OUT": "LIVE TAXIING TO RUNWAY",
            "ON_RUNWAY": "ON RUNWAY  -  MONITORING STOPPED",
            "LANDING_ROLL": "LANDING ROLL  -  EXIT: " + (detExit || "AUTO"),
            "TAXI_IN": "VACATED VIA " + (detExit || "TWY") + "  -  TAXI TO STAND",
            "ARRIVED_AT_GATE": "ARRIVED AT STAND  -  BLOCKS ON",
            "PLANNED": isDep ? "OPTIMAL TAXI ROUTE READY" : ""
        };
        let stText = (liveStatus in statusMap) ? statusMap[liveStatus] : (isDep ? "OPTIMAL TAXI ROUTE READY" : "");
        let stBanner = this.querySelector("#LiveStatusBanner");
        if (stBanner) {
            if (stText) {
                stBanner.innerText = stText;
                stBanner.style.display = "block";
            } else {
                stBanner.style.display = "none";
            }
        }

        let pillsWrap = this.querySelector("#ClearancePillsContainer");
        if (pillsWrap) {
            this.populateClearancePillsContainer(pillsWrap, aptData, cam);
        }

        let trafficWrap = this.querySelector("#TrafficPillsContainer");
        if (trafficWrap) {
            let tStr = String(aptData.bypassed_summary || "VATSIM / IVAO: Stand clear of online traffic").trim();
            let tKey = tStr + "|" + cam.s1 + "|" + cam.s2;
            if (trafficWrap.getAttribute("data-key") !== tKey) {
                trafficWrap.setAttribute("data-key", tKey);
                trafficWrap.innerHTML = "";
                let tokens = [];
                if (tStr.toUpperCase().indexOf("OCCUPIED") === 0 && tStr.indexOf(":") !== -1) {
                    let parts = tStr.split(":");
                    let tail = parts.slice(1).join(":");
                    tail.split(",").forEach(part => {
                        let c = part.trim();
                        if (c) tokens.push(c);
                    });
                    if (tokens.length === 0) tokens = [tStr];
                } else {
                    tokens = [tStr];
                }
                let pool = [cam.s1, cam.s2, cam.s3, cam.s4];
                tokens.forEach((tok, idx) => {
                    let sp = document.createElement("span");
                    sp.className = "traffic-pill";
                    sp.style.cssText =
                        "display:inline-flex;align-items:center;justify-content:center;" +
                        "color:#ffffff;font-size:12.5px;font-weight:700;padding:7px 13px;" +
                        "border-radius:8px;margin-right:6px;margin-bottom:6px;white-space:nowrap;box-sizing:border-box;" +
                        "background-color:" + pool[idx % pool.length] + ";";
                    sp.innerText = tok;
                    trafficWrap.appendChild(sp);
                });
            }
        }

        if (!isDep) {
            let pGsx = this.querySelector("#LiveGsxPill");
            if (pGsx && aptData.gsx_status) {
                let rawGsx = String(aptData.gsx_status.label || "").toUpperCase();
                let shortGsx = "GSX Pro: Armed";
                if (rawGsx.indexOf("INJECTED") !== -1 || rawGsx.indexOf("SYNCED") !== -1 || rawGsx.indexOf("ACTIVE") !== -1) {
                    shortGsx = "GSX Pro: Synced";
                }
                if (pGsx.innerText !== shortGsx) pGsx.innerText = shortGsx;
            }
        }
    }

    showAtcRunwayModal(atcSrc, icao, atcRwy, chosenRwy, onConfirm) {
        let modal = this.querySelector("#AtcRunwayModal");
        let hdr = this.querySelector("#AtcModalHeader");
        let txt = this.querySelector("#AtcModalText");
        let btnKeep = this.querySelector("#BtnAtcModalKeep");
        let btnOver = this.querySelector("#BtnAtcModalOverride");

        if (!modal || !hdr || !txt || !btnKeep || !btnOver) {
            if (onConfirm) onConfirm();
            return;
        }

        let cam = this.getCamaieu();
        let srcName = atcSrc || "AI ATC";
        hdr.innerText = srcName.toUpperCase() + "  |  " + icao;
        hdr.style.color = cam.accent || "#38bdf8";
        txt.innerHTML = "ATC active runway is <strong>RWY " + atcRwy + "</strong>. Switch to <strong>RWY " + chosenRwy + "</strong>?";

        btnKeep.innerText = "Keep RWY " + atcRwy;
        btnKeep.style.backgroundColor = cam.s1;
        btnOver.innerText = "Use RWY " + chosenRwy;
        btnOver.style.backgroundColor = cam.s3;

        btnKeep.onclick = (e) => {
            e.stopPropagation();
            modal.classList.add("hidden");
        };
        btnOver.onclick = (e) => {
            e.stopPropagation();
            modal.classList.add("hidden");
            if (onConfirm) onConfirm();
        };

        modal.classList.remove("hidden");
    }

    syncLiveStandModal(promptInfo, isAirborne, uAc) {
        let modal = this.querySelector("#LiveStandModal");
        let hdr = this.querySelector("#LiveStandModalHeader");
        let txt = this.querySelector("#LiveStandModalText");
        let btnKeep = this.querySelector("#BtnLiveStandKeep");
        let btnStay = this.querySelector("#BtnLiveStandStay");
        if (!modal || !hdr || !txt || !btnKeep || !btnStay) return;

        let gs = (uAc && uAc.gs != null) ? parseFloat(uAc.gs) : 0.0;
        if (!promptInfo || isAirborne || gs >= 4.0) {
            modal.classList.add("hidden");
            return;
        }

        let cam = this.getCamaieu();
        let icao = promptInfo.icao || "";
        let liveStand = promptInfo.live_stand || "";
        let curGate = promptInfo.current_gate || "";
        let pKey = icao + ":" + liveStand + ":" + curGate;
        if (modal.getAttribute("data-prompt-key") !== pKey) {
            modal.setAttribute("data-prompt-key", pKey);
            hdr.innerText = "MSFS LIVE STAND  |  " + icao;
            hdr.style.color = cam.accent || "#38bdf8";
            txt.innerHTML =
                "Parked at <strong>Stand " + liveStand + "</strong> in MSFS (GateFinder is set to <strong>Stand " + curGate + "</strong>).<br/><br/>" +
                "Switch to <strong>Stand " + liveStand + "</strong>?";
            btnKeep.innerText = "Use Stand " + liveStand;
            btnKeep.style.backgroundColor = cam.s1;
            btnStay.innerText = "Keep Stand " + curGate;
            btnStay.style.backgroundColor = cam.s3;

            let sendResolution = (keepVal) => {
                modal.classList.add("hidden");
                fetch(
                    "http://127.0.0.1:8420/api/resolve_live_stand?action=" + (keepVal ? "keep_live" : "keep_assigned")
                )
                    .then(r => r.json())
                    .then(d => {
                        ["departure", "arrival"].forEach(ph => {
                            if (d[ph] && d[ph].icao && !d[ph].chart_data && this.rawCharts[d[ph].icao]) {
                                d[ph].chart_data = this.rawCharts[d[ph].icao];
                            }
                        });
                        this.currentData = d;
                        this.initialFitDone = false;
                        this.lastSidebarSig = "";
                        this.lastChartSig = "";
                        this.renderData(d, true);
                    })
                    .catch(() => {});
            };

            btnKeep.onclick = (e) => {
                e.stopPropagation();
                sendResolution(true);
            };
            btnStay.onclick = (e) => {
                e.stopPropagation();
                sendResolution(false);
            };
        }
        modal.classList.remove("hidden");
    }

    fitTerminalView() {
        this.viewMode = "terminal";
        this.followAircraft = false;
        this.headingUp = false;
        this.followUserZoomMpp = null;
        this.followPanLatOffset = 0.0;
        this.followPanLonOffset = 0.0;
        this.updateToolbarButtons();
        let apt = this.currentData ? this.currentData[this.activePhase] : null;
        if (apt && apt.lat != null && apt.lon != null) {
            this.centerLat = parseFloat(apt.lat);
            this.centerLon = parseFloat(apt.lon);
            this.metersPerPixel = 1.2;
        }
        this.resetCanvasTransform();
        this.lastBaseKey = "";
        this.scheduleDraw();
    }

    fitRouteView() {
        this.viewMode = "route";
        this.followAircraft = false;
        this.headingUp = false;
        this.followUserZoomMpp = null;
        this.followPanLatOffset = 0.0;
        this.followPanLonOffset = 0.0;
        this.updateToolbarButtons();
        let apt = this.currentData ? this.currentData[this.activePhase] : null;
        if (!apt) return;

        let pts = [];
        if (apt.lat != null && apt.lon != null) pts.push([parseFloat(apt.lat), parseFloat(apt.lon)]);
        let tr = apt.taxi_route || {};
        (tr.route_points || []).forEach(p => pts.push(p));
        (tr.rollout_points || []).forEach(p => pts.push(p));

        let selRwy = (apt.selected_runway || "").toUpperCase();
        if (selRwy && apt.chart_data && apt.chart_data.runways) {
            apt.chart_data.runways.forEach(rwy => {
                if (rwy.ends && (selRwy in rwy.ends)) {
                    (rwy.points || []).forEach(p => pts.push(p));
                }
            });
        }

        this.updateCanvasMetrics();
        let w = Math.max(380, (this.canvasW || 560) - 64);
        let h = Math.max(280, (this.canvasH || 420) - 64);

        if (pts.length >= 2) {
            let minLat = Math.min(...pts.map(p => p[0]));
            let maxLat = Math.max(...pts.map(p => p[0]));
            let minLon = Math.min(...pts.map(p => p[1]));
            let maxLon = Math.max(...pts.map(p => p[1]));
            this.centerLat = (minLat + maxLat) / 2.0;
            this.centerLon = (minLon + maxLon) / 2.0;
            let cosLat = Math.max(0.2, Math.cos(this.centerLat * 0.017453292519943295));
            let spanY = Math.max(350.0, (maxLat - minLat) * 111320.0 * 1.32);
            let spanX = Math.max(350.0, (maxLon - minLon) * 111320.0 * cosLat * 1.32);
            this.metersPerPixel = Math.max(spanX / w, spanY / h, 0.9);
        } else if (pts.length === 1) {
            this.centerLat = pts[0][0];
            this.centerLon = pts[0][1];
            this.metersPerPixel = 1.8;
        } else if (apt.chart_data) {
            this.centerLat = apt.chart_data.center_lat || 0;
            this.centerLon = apt.chart_data.center_lon || 0;
            this.metersPerPixel = 3.8;
        }
        this.resetCanvasTransform();
        this.lastBaseKey = "";
        this.scheduleDraw();
    }

    drawLidoStandTag(ctx, sx, sy, sDisp, visHdg, fillCol, borderCol, fgCol, scMult, borderW, logoCodes, stylesMap, twyCenterCol) {
        let sRad = (visHdg - 90.0) * Math.PI / 180.0;
        let cosR = Math.cos(sRad), sinR = Math.sin(sRad);
        let perpX = -sinR, perpY = cosR;

        let sc = Math.max(0.70, Math.min(1.38, (1.05 / Math.pow(Math.max(0.24, this.metersPerPixel), 0.28)) * scMult));
        let fontSz = (sc >= 1.02) ? 9 : ((sc >= 0.82) ? 8 : 7);
        let halfW = Math.max(6.8, Math.min(12.0, 8.4 * sc));
        let textLen = Math.max(17.0, sDisp.length * (fontSz * 0.72) + 7.5);
        let bodyBack = textLen * 0.52;
        let bodyFront = textLen * 0.48;
        let noseLen = Math.max(7.0, Math.min(13.5, 9.2 * sc));
        let tailLine = bodyBack + Math.max(5.0, Math.min(16.0, 8.0 / Math.max(0.35, this.metersPerPixel)));

        let pt = (along, across) => [
            sx + along * cosR + across * perpX,
            sy + along * sinR + across * perpY
        ];

        // 1. Yellow/Amber stand lead-in line from taxilane into rear of stand tag
        let [t0x, t0y] = pt(-tailLine, 0.0);
        let [t1x, t1y] = pt(-bodyBack, 0.0);
        ctx.beginPath();
        ctx.moveTo(t0x, t0y);
        ctx.lineTo(t1x, t1y);
        ctx.strokeStyle = twyCenterCol;
        ctx.lineWidth = 1.4;
        ctx.stroke();

        // 2. Rectangular body of the Lido AMM stand tag
        let bRL = pt(-bodyBack, -halfW);
        let bFL = pt(bodyFront, -halfW);
        let bFR = pt(bodyFront, +halfW);
        let bRR = pt(-bodyBack, +halfW);
        ctx.beginPath();
        ctx.moveTo(bRL[0], bRL[1]);
        ctx.lineTo(bFL[0], bFL[1]);
        ctx.lineTo(bFR[0], bFR[1]);
        ctx.lineTo(bRR[0], bRR[1]);
        ctx.closePath();
        ctx.fillStyle = fillCol;
        ctx.fill();
        ctx.strokeStyle = borderCol;
        ctx.lineWidth = borderW;
        ctx.stroke();

        // 3. Triangular directional nose cone sharing the front edge of the tag body
        let nTip = pt(bodyFront + noseLen, 0.0);
        ctx.beginPath();
        ctx.moveTo(bFL[0], bFL[1]);
        ctx.lineTo(nTip[0], nTip[1]);
        ctx.lineTo(bFR[0], bFR[1]);
        ctx.closePath();
        ctx.fillStyle = fillCol;
        ctx.fill();
        ctx.strokeStyle = borderCol;
        ctx.lineWidth = borderW;
        ctx.stroke();

        // 4. Rotated stand designator text (always right-side-up)
        let txtRad = Math.atan2(sinR, cosR);
        if (txtRad > Math.PI * 0.5) txtRad -= Math.PI;
        else if (txtRad < -Math.PI * 0.5) txtRad += Math.PI;

        ctx.save();
        ctx.translate(sx, sy);
        ctx.rotate(txtRad);
        ctx.font = "bold " + fontSz + "px sans-serif";
        ctx.fillStyle = fgCol;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(sDisp, 0, 0);
        ctx.restore();

        let allX = [bRL[0], bFL[0], bFR[0], bRR[0], nTip[0]];
        let allY = [bRL[1], bFL[1], bFR[1], bRR[1], nTip[1]];

        // 5. Airline icon(s) displayed right in front of the triangular tip
        if (logoCodes && logoCodes.length > 0 && this.metersPerPixel <= 2.6) {
            let rawLh = (scMult > 1.05 ? 18.0 : 13.5) * sc;
            let logoH = Math.max(12, Math.min(scMult > 1.05 ? 24 : 18, Math.round(rawLh / 2.0) * 2));
            let logoW = Math.round(logoH * 1.16);
            let maxLogos = (this.metersPerPixel <= 0.85 && scMult <= 1.05) ? 2 : 1;
            let shown = logoCodes.slice(0, maxLogos);
            let tipAlong = bodyFront + noseLen;
            for (let idxL = 0; idxL < shown.length; idxL++) {
                let lAlong = tipAlong + 2.8 + (logoH * 0.56) + idxL * (logoH + 2.0);
                let [lx, ly] = pt(lAlong, 0.0);
                let x0 = lx - logoW * 0.5;
                let y0 = ly - logoH * 0.5;
                this.drawAirlineRectTile(ctx, shown[idxL], x0, y0, logoW, logoH, stylesMap);
                allX.push(x0, x0 + logoW);
                allY.push(y0, y0 + logoH);
            }
        }

        return [Math.min(...allX), Math.min(...allY), Math.max(...allX), Math.max(...allY)];
    }

    drawChart() {
        if (this.isDragging) return;
        let canvas = this.querySelector("#LidoCanvas");
        if (!canvas) return;
        if (!this.canvasW || !this.canvasH) {
            this.updateCanvasMetrics();
        }
        let w = this.canvasW || 520;
        let h = this.canvasH || 400;
        let pad = this.basePad || 140;
        let bw = w + pad * 2;
        let bh = h + pad * 2;
        if (canvas.width !== bw || canvas.height !== bh) {
            canvas.width = bw;
            canvas.height = bh;
            canvas.style.width = bw + "px";
            canvas.style.height = bh + "px";
            canvas.style.left = (-pad) + "px";
            canvas.style.top = (-pad) + "px";
        }

        let ctx = canvas.getContext("2d");
        let cam = this.getCamaieu();
        let isDay = (this.themeMode === "day");
        let pal = isDay ? {
            bg: "#ECEAE2", grid: "#DFDDD4",
            apronFill: "#D5D8DC", apronStroke: "#9CA3AF",
            termFill: "#1F2937", termStroke: "#111827",
            termText: "#FFFFFF", apronText: "#334155",
            twyBorder: "#6B7280", twyFill: "#BFC4CA", twyCenter: "#D97706",
            twyLabelBg: "#D5D8DC", twyLabelFg: "#0F172A",
            rwyFill: "#1E293B", rwyStroke: "#0F172A", rwyCenter: "#FFFFFF",
            rwyCircleFill: "#0F293D", rwyCircleRing: "#0284C7",
            standBg: "#FFF7ED", standStroke: "#EA580C", standFg: "#9A3412",
            routeGlow: "#047857", routeMain: "#10B981", routeArrow: "#FFFFFF",
            rollout: "#0284C7", holdBar: "#EAB308"
        } : {
            bg: "#2B353E", grid: "#2F3A44",
            apronFill: "#465664", apronStroke: "#526474",
            termFill: "#070A0F", termStroke: "#1A242F",
            termText: "#FFFFFF", apronText: "#F1F5F9",
            twyBorder: "#3A4854", twyFill: "#4E6070", twyCenter: "#D9B44A",
            twyLabelBg: "#24303B", twyLabelFg: "#FFFFFF",
            rwyFill: "#080C11", rwyStroke: "#CBD5E1", rwyCenter: "#F8FAFC",
            rwyCircleFill: "#0C2B3D", rwyCircleRing: "#22D3EE",
            standBg: "#1D2630", standStroke: "#F0743E", standFg: "#FFFFFF",
            routeGlow: "#065F46", routeMain: "#10B981", routeArrow: "#ECFDF5",
            rollout: "#38BDF8", holdBar: "#FACC15"
        };

        let apt = this.currentData ? this.currentData[this.activePhase] : null;
        if (!apt) {
            ctx.fillStyle = pal.bg;
            ctx.fillRect(0, 0, bw, bh);
            return;
        }
        let fast = this.fastCharts[apt.icao];
        if (!fast && apt.chart_data) {
            fast = this.compileFastChart(apt.chart_data);
            this.fastCharts[apt.icao] = fast;
        }
        if (!fast) {
            ctx.fillStyle = pal.bg;
            ctx.fillRect(0, 0, bw, bh);
            return;
        }

        ctx.fillStyle = pal.bg;
        ctx.fillRect(0, 0, bw, bh);

        // 0. Batched Subtle Coordinate Grid
        ctx.beginPath();
        for (let gx = 0; gx < bw; gx += 90) {
            ctx.moveTo(gx, 0); ctx.lineTo(gx, bh);
        }
        for (let gy = 0; gy < bh; gy += 90) {
            ctx.moveTo(0, gy); ctx.lineTo(bw, gy);
        }
        ctx.strokeStyle = pal.grid;
        ctx.lineWidth = 1;
        ctx.stroke();

        let invMpp = 1.0 / this.metersPerPixel;
        let camXm = (this.centerLon - fast.refLon) * fast.mPerDegLon;
        let camYm = (this.centerLat - fast.refLat) * fast.mPerDegLat;
        let cx = bw * 0.5;
        let cy = bh * 0.5;

        let uAc = this.currentData ? this.currentData.user_aircraft : null;
        let isAirborne = this.isAirborneNow();
        let useHdgUp = Boolean(this.followAircraft && this.headingUp && !isAirborne && uAc && uAc.connected && uAc.heading != null);
        let acHdgS = (useHdgUp && uAc && uAc.heading != null) ? parseFloat(uAc.heading) : 0.0;
        let rotRad = useHdgUp ? (-acHdgS * Math.PI / 180.0) : 0.0;
        let cosR = useHdgUp ? Math.cos(rotRad) : 1.0;
        let sinR = useHdgUp ? Math.sin(rotRad) : 0.0;

        let halfSpanXm = (bw * (useHdgUp ? 0.76 : 0.53)) * this.metersPerPixel;
        let halfSpanYm = (bh * (useHdgUp ? 0.76 : 0.53)) * this.metersPerPixel;
        let minXm = camXm - halfSpanXm, maxXm = camXm + halfSpanXm;
        let minYm = camYm - halfSpanYm, maxYm = camYm + halfSpanYm;

        let mToXY = (xM, yM) => {
            let dx = (xM - camXm) * invMpp;
            let dy = -(yM - camYm) * invMpp;
            if (!useHdgUp) return [cx + dx, cy + dy];
            return [cx + (dx * cosR - dy * sinR), cy + (dx * sinR + dy * cosR)];
        };

        let toXY = (lat, lon) => mToXY(
            (lon - fast.refLon) * fast.mPerDegLon,
            (lat - fast.refLat) * fast.mPerDegLat
        );

        // 1. Batched Aprons with Frustum Culling + Apron Label Candidates
        let apronLabelCandidates = [];
        if (fast.aprons.length > 0) {
            ctx.beginPath();
            for (let i = 0; i < fast.aprons.length; i++) {
                let item = fast.aprons[i];
                if (item.maxX < minXm || item.minX > maxXm || item.maxY < minYm || item.minY > maxYm) continue;
                let pts = item.pts;
                let [sx0, sy0] = mToXY(pts[0][0], pts[0][1]);
                ctx.moveTo(sx0, sy0);
                for (let j = 1; j < pts.length; j++) {
                    let [sx, sy] = mToXY(pts[j][0], pts[j][1]);
                    ctx.lineTo(sx, sy);
                }
                ctx.closePath();
                if (item.name && ((item.maxX - item.minX) * invMpp >= 55 || (item.maxY - item.minY) * invMpp >= 55)) {
                    let apU = item.name.toUpperCase();
                    if (apU.indexOf("APRON") !== -1 || apU.indexOf("AIRE") !== -1 || apU.indexOf("PARKING") !== -1 || apU.indexOf("RAMP") !== -1) {
                        let [axC, ayC] = mToXY(item.cxM, item.cyM);
                        apronLabelCandidates.push([apU, axC, ayC]);
                    }
                }
            }
            ctx.fillStyle = pal.apronFill;
            ctx.fill();
        }

        // 2A. Batched Taxilanes
        let twyW = Math.max(2.5, Math.min(14.0, 18.0 * invMpp));
        ctx.lineCap = "butt";
        ctx.lineJoin = "miter";

        if (fast.taxilanes.length > 0) {
            ctx.beginPath();
            for (let i = 0; i < fast.taxilanes.length; i++) {
                let item = fast.taxilanes[i];
                if (item.maxX < minXm || item.minX > maxXm || item.maxY < minYm || item.minY > maxYm) continue;
                let pts = item.pts;
                let [sx0, sy0] = mToXY(pts[0][0], pts[0][1]);
                ctx.moveTo(sx0, sy0);
                for (let j = 1; j < pts.length; j++) {
                    let [sx, sy] = mToXY(pts[j][0], pts[j][1]);
                    ctx.lineTo(sx, sy);
                }
            }
            ctx.strokeStyle = pal.twyFill;
            ctx.lineWidth = Math.max(1.8, twyW * 0.65);
            ctx.stroke();
            if (this.metersPerPixel < 3.6) {
                ctx.strokeStyle = pal.twyCenter;
                ctx.lineWidth = 1.1;
                ctx.stroke();
            }
        }

        // 2B. Batched Main Taxiways with Frustum Culling
        if (fast.mainTaxiways.length > 0) {
            ctx.beginPath();
            for (let i = 0; i < fast.mainTaxiways.length; i++) {
                let item = fast.mainTaxiways[i];
                if (item.maxX < minXm || item.minX > maxXm || item.maxY < minYm || item.minY > maxYm) continue;
                let pts = item.pts;
                let [sx0, sy0] = mToXY(pts[0][0], pts[0][1]);
                ctx.moveTo(sx0, sy0);
                for (let j = 1; j < pts.length; j++) {
                    let [sx, sy] = mToXY(pts[j][0], pts[j][1]);
                    ctx.lineTo(sx, sy);
                }
            }
            if (this.metersPerPixel < 5.0) {
                ctx.strokeStyle = pal.twyBorder;
                ctx.lineWidth = twyW + 2.0;
                ctx.stroke();
            }
            ctx.strokeStyle = pal.twyFill;
            ctx.lineWidth = twyW;
            ctx.stroke();

            if (this.metersPerPixel < 3.6) {
                ctx.strokeStyle = pal.twyCenter;
                ctx.lineWidth = 1.2;
                ctx.stroke();
            }
        }

        // 3. Batched Terminal Buildings (Pitch-black Lido AMM silhouettes) & Terminal/Pier Labels
        let termPolyLabels = [];
        let seenTermLabels = {};
        if (fast.terminals.length > 0) {
            ctx.beginPath();
            for (let i = 0; i < fast.terminals.length; i++) {
                let item = fast.terminals[i];
                if (item.maxX < minXm || item.minX > maxXm || item.maxY < minYm || item.minY > maxYm) continue;
                let pts = item.pts;
                let [sx0, sy0] = mToXY(pts[0][0], pts[0][1]);
                ctx.moveTo(sx0, sy0);
                for (let j = 1; j < pts.length; j++) {
                    let [sx, sy] = mToXY(pts[j][0], pts[j][1]);
                    ctx.lineTo(sx, sy);
                }
                ctx.closePath();

                let rawTn = item.name || "";
                if (rawTn && ((item.maxX - item.minX) * invMpp >= 36 || (item.maxY - item.minY) * invMpp >= 36)) {
                    if (/terminal|term|orly\s*\d|hall|concourse|pier|sat|dock|jet[eé]e/i.test(rawTn) && !/sslia|pompier|fire|tower|tour\s+de|hangar|servair|fret|wfs/i.test(rawTn)) {
                        let cleanTn = rawTn.replace(/\s*\([^)]*\)/g, "").trim();
                        cleanTn = cleanTn.replace(/^(?:a[eé]rogare|a[eé]roport|b[aâ]timent)\s+(?:d['\u2019]|de\s+|du\s+)?/i, "").trim().toUpperCase();
                        if (/^ORLY\s*1\s*(?:ET|&|-|\/)\s*2$/i.test(cleanTn)) {
                            let swXM = item.minX + 0.34 * (item.maxX - item.minX);
                            let swYM = item.minY + 0.32 * (item.maxY - item.minY);
                            let neXM = item.minX + 0.66 * (item.maxX - item.minX);
                            let neYM = item.minY + 0.68 * (item.maxY - item.minY);
                            let [swX, swY] = mToXY(swXM, swYM);
                            let [neX, neY] = mToXY(neXM, neYM);
                            if (!seenTermLabels["ORLY 1"]) {
                                termPolyLabels.push(["ORLY 1", swX, swY]);
                                seenTermLabels["ORLY 1"] = true;
                            }
                            if (!seenTermLabels["ORLY 2"]) {
                                termPolyLabels.push(["ORLY 2", neX, neY]);
                                seenTermLabels["ORLY 2"] = true;
                            }
                        } else {
                            let mShort = cleanTn.match(/^((?:TERMINAL|TERM|PIER|CONCOURSE|HALL|SAT(?:ELLITE)?|DOCK|JET[EÉ]E)\s*(?:[0-9]{1,2}[A-Z]?|[A-Z]\b)?)/);
                            if (mShort && cleanTn.length > 16) {
                                cleanTn = mShort[1].trim();
                            } else if (cleanTn.length > 22) {
                                cleanTn = cleanTn.slice(0, 22).trim();
                            }
                            if (cleanTn && !seenTermLabels[cleanTn]) {
                                let [txC, tyC] = mToXY(item.cxM, item.cyM);
                                termPolyLabels.push([cleanTn, txC, tyC]);
                                seenTermLabels[cleanTn] = true;
                            }
                        }
                    }
                }
            }
            ctx.fillStyle = pal.termFill;
            ctx.fill();
            ctx.strokeStyle = pal.termStroke;
            ctx.lineWidth = 1.0;
            ctx.stroke();
        }

        // 4. Runways + Collect Threshold Badges
        let rwyW = Math.max(8.0, Math.min(34.0, 45.0 * invMpp));
        let activeRwy = (apt.selected_runway || "").toUpperCase();
        let rwyThresholdBadges = [];

        for (let i = 0; i < fast.runways.length; i++) {
            let rwy = fast.runways[i];
            let pts = rwy.mPts;
            ctx.beginPath();
            let [rx0, ry0] = mToXY(pts[0][0], pts[0][1]);
            ctx.moveTo(rx0, ry0);
            for (let j = 1; j < pts.length; j++) {
                let [rx, ry] = mToXY(pts[j][0], pts[j][1]);
                ctx.lineTo(rx, ry);
            }
            let isSel = rwy.ends && (activeRwy in rwy.ends);
            ctx.strokeStyle = isSel ? pal.rwyCircleRing : pal.rwyStroke;
            ctx.lineWidth = rwyW + 2.5;
            ctx.lineCap = "butt";
            ctx.stroke();

            ctx.strokeStyle = pal.rwyFill;
            ctx.lineWidth = rwyW;
            ctx.stroke();

            ctx.setLineDash([8, 8]);
            ctx.strokeStyle = pal.rwyCenter;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.setLineDash([]);

            let endKeys = Object.keys(rwy.ends || {});
            for (let k = 0; k < endKeys.length; k++) {
                let endId = endKeys[k];
                let endInfo = rwy.ends[endId];
                let [ex, ey] = mToXY(endInfo.xM, endInfo.yM);
                rwyThresholdBadges.push({
                    ex: ex,
                    ey: ey,
                    endId: endId,
                    isActive: (endId === activeRwy),
                    heading: endInfo.heading || 0.0
                });
            }
        }

        // 4b. Lido Yellow Hold-Short Bars at Holding Points
        if (this.metersPerPixel <= 3.8 && fast.holdingPoints && fast.holdingPoints.length > 0) {
            let hbHalf = Math.max(4.0, Math.min(9.0, 7.5 * invMpp));
            ctx.beginPath();
            for (let i = 0; i < fast.holdingPoints.length; i++) {
                let hp = fast.holdingPoints[i];
                if (hp.xM < minXm || hp.xM > maxXm || hp.yM < minYm || hp.yM > maxYm) continue;
                let [hx, hy] = mToXY(hp.xM, hp.yM);
                ctx.moveTo(hx - hbHalf, hy - 2);
                ctx.lineTo(hx + hbHalf, hy + 2);
            }
            ctx.strokeStyle = pal.holdBar;
            ctx.lineWidth = 2.4;
            ctx.stroke();
        }

        // 5. Neighboring Stands (Authentic Lido AMM Oriented Pentagonal / Triangular-Nose Stand Tags)
        this.standHitboxes = [];
        this.rwyHitboxes = [];
        let gxPin = null, gyPin = null;
        if (apt.lat != null && apt.lon != null) {
            [gxPin, gyPin] = toXY(parseFloat(apt.lat), parseFloat(apt.lon));
        }

        let assignedGate = String(apt.gate || "").replace(/\s+/g, "").toUpperCase();
        let assignedNorm = assignedGate.replace(/^([A-Z]*)0+(\d+)/, "$1$2");
        let assignedDigits = assignedGate.replace(/\D+/g, "");

        let standTermGroups = {};
        let standApronGroups = {};
        let standsAll = fast.standsAll || [];

        for (let i = 0; i < standsAll.length; i++) {
            let st = standsAll[i];
            if (st.xM < minXm || st.xM > maxXm || st.yM < minYm || st.yM > maxYm) continue;
            let [sxG, syG] = mToXY(st.xM, st.yM);
            let visHdgG = useHdgUp ? (st.heading - acHdgS) : st.heading;
            let radG = (visHdgG - 90.0) * Math.PI / 180.0;
            let crG = Math.cos(radG), srG = Math.sin(radG);

            let rawT = st.terminal.trim();
            if (rawT) {
                let tU = rawT.replace(/\s*\([^)]*\)/g, "").trim().toUpperCase();
                if (
                    tU &&
                    tU !== "MAIN APRON" &&
                    tU !== "OTHER" &&
                    tU !== "CARGO APRON" &&
                    tU !== "GENERAL AVIATION" &&
                    !/^ORLY\s*1\s*(?:ET|&|-|\/)\s*2$/i.test(tU) &&
                    tU.indexOf("ZONE ") !== 0
                ) {
                    if (!standTermGroups[tU]) standTermGroups[tU] = [];
                    standTermGroups[tU].push([sxG, syG, crG, srG]);
                }
            }
            let mAp = st.disp.match(/^([A-Z])\d{1,3}[A-Z]?$/);
            if (mAp) {
                let apL = mAp[1];
                if (!standApronGroups[apL]) standApronGroups[apL] = [];
                standApronGroups[apL].push([sxG, syG, crG, srG]);
            }
        }

        let drawnStandBoxes = [];
        if (this.metersPerPixel <= 3.2) {
            let latThr = (this.metersPerPixel < 1.2) ? 11.5 : ((this.metersPerPixel <= 2.0) ? 14.5 : 20.0);
            let lonThr = (this.metersPerPixel < 1.2) ? 22.0 : 28.0;

            for (let i = 0; i < standsAll.length; i++) {
                let st = standsAll[i];
                if (st.xM < minXm || st.xM > maxXm || st.yM < minYm || st.yM > maxYm) continue;
                let stNorm = st.clean.replace(/^([A-Z]*)0+(\d+)/, "$1$2");
                if (st.clean === assignedGate || stNorm === assignedNorm || (assignedDigits && st.clean === assignedDigits)) continue;

                let [sx, sy] = mToXY(st.xM, st.yM);
                if (sx < 14 || sx > bw - 14 || sy < 14 || sy > bh - 14) continue;
                if (gxPin !== null && Math.hypot(sx - gxPin, sy - gyPin) < 16) continue;

                let visSHdg = useHdgUp ? (st.heading - acHdgS) : st.heading;
                let sRad = (visSHdg - 90.0) * Math.PI / 180.0;
                let cR = Math.cos(sRad), sR = Math.sin(sRad);
                let pX = -sR, pY = cR;

                let tooClose = false;
                for (let j = 0; j < drawnStandBoxes.length; j++) {
                    let [ox, oy] = drawnStandBoxes[j];
                    let ddx = sx - ox, ddy = sy - oy;
                    let dAlong = Math.abs(ddx * cR + ddy * sR);
                    let dAcross = Math.abs(ddx * pX + ddy * pY);
                    if (dAcross < latThr && dAlong < lonThr) {
                        tooClose = true;
                        break;
                    }
                }
                if (tooClose) continue;
                drawnStandBoxes.push([sx, sy]);

                let [bx0, by0, bx1, by1] = this.drawLidoStandTag(
                    ctx, sx, sy, st.disp, visSHdg,
                    pal.standBg, pal.standStroke, pal.standFg,
                    1.0, 1.6, st.airlines, fast.airlineStyles, pal.twyCenter
                );
                this.standHitboxes.push({
                    x0: bx0 - pad, y0: by0 - pad, x1: bx1 - pad, y1: by1 - pad,
                    ref: st.ref, airlines: st.airlines, terminal: st.terminal || "", isAssigned: false, stylesMap: fast.airlineStyles
                });
            }
        }

        // 5b. Draw Terminal / Pier Names & Apron Names (ORLY 1, ORLY 2, ORLY 3, ORLY 4, APRON B, etc.)
        let drawnAreaLabels = [];
        if (this.metersPerPixel <= 4.2) {
            let allTermLabels = termPolyLabels.slice();
            Object.keys(standTermGroups).forEach(tName => {
                let grp = standTermGroups[tName];
                if (grp.length < 2) return;
                let avgX = 0, avgY = 0, avgCr = 0, avgSr = 0;
                for (let i = 0; i < grp.length; i++) {
                    avgX += grp[i][0]; avgY += grp[i][1]; avgCr += grp[i][2]; avgSr += grp[i][3];
                }
                avgX /= grp.length; avgY /= grp.length; avgCr /= grp.length; avgSr /= grp.length;
                let normLen = Math.hypot(avgCr, avgSr) || 1.0;
                let shiftPx = Math.max(24.0, Math.min(52.0, 36.0 / Math.max(0.4, this.metersPerPixel)));
                allTermLabels.push([tName, avgX + (avgCr / normLen) * shiftPx, avgY + (avgSr / normLen) * shiftPx]);
            });

            ctx.font = "bold 10px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            for (let i = 0; i < allTermLabels.length; i++) {
                let [tLbl, txL, tyL] = allTermLabels[i];
                if (txL < pad + 35 || txL > bw - pad - 35 || tyL < pad + 25 || tyL > bh - pad - 25) continue;
                let dup = false;
                for (let j = 0; j < drawnAreaLabels.length; j++) {
                    if (drawnAreaLabels[j][0] === tLbl || Math.hypot(txL - drawnAreaLabels[j][1], tyL - drawnAreaLabels[j][2]) < 85.0) {
                        dup = true;
                        break;
                    }
                }
                if (dup) continue;
                drawnAreaLabels.push([tLbl, txL, tyL]);
                ctx.fillStyle = "#000000";
                ctx.fillText(tLbl, txL + 1, tyL + 1);
                ctx.fillStyle = pal.termText;
                ctx.fillText(tLbl, txL, tyL);
            }
        }

        if (this.metersPerPixel <= 3.0) {
            Object.keys(standApronGroups).sort().forEach(apLetter => {
                let grp = standApronGroups[apLetter];
                if (grp.length < 2) return;
                let apLbl = "APRON " + apLetter;
                let avgX = 0, avgY = 0, avgCr = 0, avgSr = 0;
                for (let i = 0; i < grp.length; i++) {
                    avgX += grp[i][0]; avgY += grp[i][1]; avgCr += grp[i][2]; avgSr += grp[i][3];
                }
                avgX /= grp.length; avgY /= grp.length; avgCr /= grp.length; avgSr /= grp.length;
                let normLen = Math.hypot(avgCr, avgSr) || 1.0;
                let backPx = Math.max(22.0, Math.min(44.0, 28.0 / Math.max(0.45, this.metersPerPixel)));
                let axL = avgX - (avgCr / normLen) * backPx;
                let ayL = avgY - (avgSr / normLen) * backPx;
                for (let j = 0; j < drawnStandBoxes.length; j++) {
                    if (Math.hypot(axL - drawnStandBoxes[j][0], ayL - drawnStandBoxes[j][1]) < 20.0) {
                        axL -= (avgCr / normLen) * 16.0;
                        ayL -= (avgSr / normLen) * 16.0;
                        break;
                    }
                }
                apronLabelCandidates.push([apLbl, axL, ayL]);
            });

            ctx.font = "bold 8px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            for (let i = 0; i < apronLabelCandidates.length; i++) {
                let [apLbl, axL, ayL] = apronLabelCandidates[i];
                if (axL < pad + 35 || axL > bw - pad - 35 || ayL < pad + 25 || ayL > bh - pad - 25) continue;
                let dup = false;
                for (let j = 0; j < drawnAreaLabels.length; j++) {
                    if (drawnAreaLabels[j][0] === apLbl || Math.hypot(axL - drawnAreaLabels[j][1], ayL - drawnAreaLabels[j][2]) < 70.0) {
                        dup = true;
                        break;
                    }
                }
                if (dup) continue;
                drawnAreaLabels.push([apLbl, axL, ayL]);
                ctx.fillStyle = "#090D14";
                ctx.fillText(apLbl, axL + 1, ayL + 1);
                ctx.fillStyle = pal.apronText;
                ctx.fillText(apLbl, axL, ayL);
            }
        }

        // 6. Active Taxi Route & Rollout + Directional Arrows
        let tr = apt.taxi_route || {};
        let rolloutPts = tr.rollout_points || [];
        if (rolloutPts.length >= 2) {
            ctx.beginPath();
            for (let i = 0; i < rolloutPts.length; i++) {
                let [x, y] = toXY(rolloutPts[i][0], rolloutPts[i][1]);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.setLineDash([8, 6]);
            ctx.strokeStyle = pal.rollout;
            ctx.lineWidth = 3.5;
            ctx.stroke();
            ctx.setLineDash([]);
        }

        let routePts = tr.route_points || [];
        if (routePts.length >= 2) {
            let xyPts = [];
            ctx.beginPath();
            for (let i = 0; i < routePts.length; i++) {
                let [x, y] = toXY(routePts[i][0], routePts[i][1]);
                xyPts.push([x, y]);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            let rw = Math.max(5.0, Math.min(11.0, 14.0 * invMpp));
            ctx.strokeStyle = pal.routeGlow;
            ctx.lineWidth = rw + 3.5;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.stroke();

            ctx.strokeStyle = pal.routeMain;
            ctx.lineWidth = rw;
            ctx.stroke();

            // Batched Directional Chevrons along Route
            ctx.beginPath();
            let accum = 0.0;
            for (let i = 0; i < xyPts.length - 1; i++) {
                let [x1, y1] = xyPts[i];
                let [x2, y2] = xyPts[i + 1];
                let seg = Math.hypot(x2 - x1, y2 - y1);
                accum += seg;
                if (accum >= 70.0 && seg > 4.0) {
                    accum = 0.0;
                    let mx = (x1 + x2) * 0.5;
                    let my = (y1 + y2) * 0.5;
                    let ang = Math.atan2(y2 - y1, x2 - x1);
                    let sz = 5.8;
                    ctx.moveTo(mx + sz * Math.cos(ang), my + sz * Math.sin(ang));
                    ctx.lineTo(mx + sz * Math.cos(ang + 2.4), my + sz * Math.sin(ang + 2.4));
                    ctx.lineTo(mx + sz * Math.cos(ang - 2.4), my + sz * Math.sin(ang - 2.4));
                    ctx.closePath();
                }
            }
            ctx.fillStyle = pal.routeArrow;
            ctx.fill();
        }

        // 7. Taxiway Labels (Lido AMM bold white designators with dark halo)
        if (this.metersPerPixel < 5.2) {
            ctx.font = "bold 8.5px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            for (let i = 0; i < fast.twyLabels.length; i++) {
                let lbl = fast.twyLabels[i];
                let [mx, my] = mToXY(lbl.xM, lbl.yM);
                if (mx < 16 || mx > bw - 16 || my < 16 || my > bh - 16) continue;
                let rw = lbl.halfW;
                ctx.fillStyle = pal.twyLabelBg;
                ctx.fillRect(mx - rw, my - 6, rw * 2, 12);
                ctx.fillStyle = pal.twyLabelFg;
                ctx.fillText(lbl.ref, mx, my);
            }
        }

        // 7b. Interactive Circular Runway Badges (Lido AMM Cyan-Ringed Circles) anchored at exact threshold coordinates
        for (let i = 0; i < rwyThresholdBadges.length; i++) {
            let b = rwyThresholdBadges[i];
            let ex = b.ex, ey = b.ey;
            let radC = b.isActive ? 16 : 14;
            let fillC = b.isActive ? cam.s1 : pal.rwyCircleFill;
            let ringC = pal.rwyCircleRing;

            if (b.isActive) {
                ctx.beginPath();
                ctx.arc(ex, ey, radC + 4, 0, Math.PI * 2);
                ctx.strokeStyle = ringC;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            ctx.beginPath();
            ctx.arc(ex, ey, radC, 0, Math.PI * 2);
            ctx.fillStyle = fillC;
            ctx.fill();
            ctx.strokeStyle = ringC;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            let visRHdg = useHdgUp ? (b.heading - acHdgS) : b.heading;
            let rRad = (visRHdg - 90.0) * Math.PI / 180.0;
            let txtRad = Math.atan2(Math.sin(rRad), Math.cos(rRad));
            if (txtRad > Math.PI * 0.5) txtRad -= Math.PI;
            else if (txtRad < -Math.PI * 0.5) txtRad += Math.PI;

            ctx.save();
            ctx.translate(ex, ey);
            ctx.rotate(txtRad);
            ctx.font = "bold 10px sans-serif";
            ctx.fillStyle = "#FFFFFF";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(String(b.endId), 0, 0);
            ctx.restore();

            this.rwyHitboxes.push({
                x0: ex - radC - pad, y0: ey - radC - pad,
                x1: ex + radC - pad, y1: ey + radC - pad,
                endId: b.endId, isActive: b.isActive
            });
        }

        // 8. Assigned Gate Marker (Highlighted Lido AMM Directional Stand Tag + Airline Icon in front of tip)
        if (gxPin !== null && gyPin !== null) {
            let gateLbl = String(apt.gate || "GATE");
            let gDisp = gateLbl.replace(/^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*/i, "").replace(/\s+/g, "").toUpperCase() || gateLbl;
            let gHdg = apt.heading;
            let heroAl = String(apt.airline_code || "").trim().toUpperCase();
            if (!heroAl && this.currentData && this.currentData.airline) {
                let rawAl = String(this.currentData.airline);
                heroAl = rawAl.indexOf("-") !== -1 ? rawAl.split("-")[0].trim().toUpperCase() : rawAl.trim().toUpperCase().slice(0, 3);
            }
            let heroAls = (heroAl && heroAl !== "AIR" && heroAl !== "ANY") ? [heroAl] : [];
            let heroTerm = String(apt.terminal || "");

            for (let i = 0; i < standsAll.length; i++) {
                let st = standsAll[i];
                let stNorm = st.clean.replace(/^([A-Z]*)0+(\d+)/, "$1$2");
                if (st.clean === assignedGate || stNorm === assignedNorm || (assignedDigits && st.clean === assignedDigits)) {
                    if (gHdg == null && st.heading != null) gHdg = st.heading;
                    if (!heroTerm && st.terminal) heroTerm = st.terminal;
                    (st.airlines || []).forEach(a => {
                        let au = String(a).toUpperCase();
                        if (au && heroAls.indexOf(au) === -1) heroAls.push(au);
                    });
                    break;
                }
            }

            let visGHdg = (gHdg != null) ? (useHdgUp ? (parseFloat(gHdg) - acHdgS) : parseFloat(gHdg)) : 0.0;
            let [gx0, gy0, gx1, gy1] = this.drawLidoStandTag(
                ctx, gxPin, gyPin, gDisp, visGHdg,
                cam.s1, "#FFFFFF", "#FFFFFF",
                1.22, 2.4, heroAls, fast.airlineStyles, pal.twyCenter
            );
            this.standHitboxes.push({
                x0: gx0 - pad, y0: gy0 - pad, x1: gx1 - pad, y1: gy1 - pad,
                ref: gateLbl, airlines: heroAls, terminal: heroTerm, isAssigned: true, stylesMap: fast.airlineStyles
            });
        }

        // 9. Live SimConnect User Aircraft Icon (only on ground)
        if (!isAirborne && uAc && uAc.connected && uAc.lat != null && uAc.lon != null) {
            let [ax, ay] = toXY(uAc.lat, uAc.lon);
            ctx.save();
            ctx.beginPath();
            ctx.arc(ax, ay, 18, 0, Math.PI * 2);
            ctx.setLineDash([4, 3]);
            ctx.strokeStyle = "#38BDF8";
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.translate(ax, ay);
            let visHdg = useHdgUp ? 0.0 : (uAc.heading || 0);
            ctx.rotate((visHdg * Math.PI) / 180.0);
            ctx.beginPath();
            ctx.moveTo(0, -14);
            ctx.lineTo(3, -4);
            ctx.lineTo(13, 2);
            ctx.lineTo(13, 5);
            ctx.lineTo(3, 3);
            ctx.lineTo(2, 11);
            ctx.lineTo(6, 13);
            ctx.lineTo(6, 14);
            ctx.lineTo(0, 13);
            ctx.lineTo(-6, 14);
            ctx.lineTo(-6, 13);
            ctx.lineTo(-2, 11);
            ctx.lineTo(-3, 3);
            ctx.lineTo(-13, 5);
            ctx.lineTo(-13, 2);
            ctx.lineTo(-3, -4);
            ctx.closePath();
            ctx.fillStyle = "#38BDF8";
            ctx.fill();
            ctx.restore();
        }
    }
}

window.customElements.define("gsx-gatefinder-panel", GSXGateFinderPanel);
checkAutoload();
