/**
 * GateFinderEfbApp.js - MSFS 2024 Native EFB App for GateFinder V2.0.4
 *
 * Registers "GateFinder" in the MSFS 2024 EFB OS (window.EFB_API) and renders
 * the interactive Lido ground radar & stand/ATC interface inside a sandboxed
 * coui:// iframe so DOM IDs and CSS stay 100% isolated from the EFB OS.
 */
(function () {
    "use strict";

    if (typeof msfssdk === "undefined" || typeof EFB_API === "undefined") {
        return;
    }

    var APP_ROOT = "coui://html_ui/efb_ui/efb_apps/GateFinderEfbApp";
    var FRAME_URL = "coui://html_ui/ingamePanels/GateFinderPanel/GateFinderEfbFrame.html?v=204";

    var BootMode = { COLD: 0, WARM: 1, HOT: 2 };
    var SuspendMode = { SLEEP: 0, TERMINATE: 1 };

    var FSComponent = msfssdk.FSComponent;
    var DisplayComponent = msfssdk.DisplayComponent;
    var Subject = msfssdk.Subject;

    var cssLoaded = false;
    function ensureAppCss() {
        if (cssLoaded) return;
        cssLoaded = true;
        try {
            EFB_API.loadCss(APP_ROOT + "/GateFinderEfbApp.css").catch(function () {});
        } catch (e) {}
    }

    class GateFinderEfbAppView extends DisplayComponent {
        constructor() {
            super(...arguments);
            this.rootRef = FSComponent.createRef();
            this.frame = null;
            this.panelBound = false;
            this.resizeHandler = null;
        }

        render() {
            return FSComponent.buildComponent("div", {
                class: "gf-efb-root",
                ref: this.rootRef
            });
        }

        onAfterRender(node) {
            super.onAfterRender(node);
            ensureAppCss();
            this.ensureFrame();
            this.bindPanelSize();
            this.fitContentArea();
        }

        ensureFrame() {
            var root = this.rootRef.instance;
            if (this.frame || !root) return;
            var frame = document.createElement("iframe");
            frame.className = "gf-efb-frame";
            frame.src = FRAME_URL + "&t=" + Date.now();
            frame.setAttribute("frameBorder", "0");
            frame.setAttribute("allowFullScreen", "true");
            root.appendChild(frame);
            this.frame = frame;
        }

        bindPanelSize() {
            if (this.panelBound) return;
            this.panelBound = true;
            var self = this;

            var ps = window.PanelSize;
            if (ps && ps.width && ps.height) {
                var apply = function () {
                    self.fitContentArea();
                };
                try {
                    ps.width.sub(apply, true);
                    ps.height.sub(apply, true);
                } catch (e) {}
            }

            this.resizeHandler = function () {
                self.fitContentArea();
            };
            window.addEventListener("resize", this.resizeHandler);
        }

        fitContentArea() {
            var self = this;
            var run = function () {
                var f = self.frame;
                var root = self.rootRef.instance;
                if (!f || !root) return;
                var g = root.getBoundingClientRect();
                if (g.height <= 0 || g.width <= 0) return;

                var top = 0;
                var bottom = g.height;

                var header = document.querySelector(".efb-header");
                if (header) {
                    var hr = header.getBoundingClientRect();
                    if (hr.height > 0 && hr.bottom > g.top && hr.bottom < g.bottom) {
                        top = hr.bottom - g.top;
                    }
                }

                var dock = document.querySelector("dock, .dock");
                if (dock) {
                    var dr = dock.getBoundingClientRect();
                    if (dr.height > 0 && dr.top > g.top && dr.top < g.bottom) {
                        bottom = dr.top - g.top;
                    }
                }

                f.style.top = Math.round(top) + "px";
                f.style.left = "0px";
                f.style.width = Math.round(g.width) + "px";
                f.style.height = Math.round(Math.max(100, bottom - top)) + "px";
            };

            if (typeof window.requestAnimationFrame === "function") {
                window.requestAnimationFrame(run);
            } else {
                run();
            }
        }

        onOpen() {
            ensureAppCss();
            this.ensureFrame();
            this.bindPanelSize();
            this.fitContentArea();
        }

        onClose() {}

        onPause() {}

        onResume() {
            this.ensureFrame();
            this.bindPanelSize();
            this.fitContentArea();
        }

        onUpdate() {}

        routeGamepadInteractionEvent() {}

        destroy() {
            if (this.resizeHandler) {
                window.removeEventListener("resize", this.resizeHandler);
                this.resizeHandler = null;
            }
            if (this.frame && this.frame.parentNode) {
                this.frame.parentNode.removeChild(this.frame);
            }
            this.frame = null;
            super.destroy();
        }
    }

    class GateFinderEfbApp {
        constructor() {
            this._isInstalled = false;
            this._isReady = false;
            this._favoriteIndex = -1;
            this.available = Subject.create(true);
            this.BootMode = BootMode.COLD;
            this.SuspendMode = SuspendMode.SLEEP;
            this.options = {};
        }

        get internalName() { return "GateFinderEfbApp"; }
        get name() { return "GateFinder"; }
        get icon() { return APP_ROOT + "/Assets/app-icon.svg"; }
        get isReady() { return this._isReady; }
        get favoriteIndex() { return this._favoriteIndex; }
        set favoriteIndex(value) { this._favoriteIndex = value; }

        getVersion() { return "2.0.4"; }
        getIsSearchable() { return this.options.isSearchable !== false; }
        getIsFavoritable() { return this.options.isFavoritable !== false; }
        get compatibleAircraftModels() { return undefined; }

        _install(context) {
            if (this._isInstalled) {
                return Promise.reject("App already installed.");
            }
            this._isInstalled = true;
            this.bus = context.bus;
            this.options = context.options || {};
            if (typeof context.favoriteIndex === "number") {
                this._favoriteIndex = context.favoriteIndex;
            }
            ensureAppCss();
            this._isReady = true;
            if (typeof Coherent !== "undefined" && Coherent.trigger) {
                Coherent.trigger("EFB_APP_INSTALLED", this.name, this.internalName, "1.0.3", this.getVersion());
            }
            return Promise.resolve();
        }

        render() {
            return FSComponent.buildComponent(GateFinderEfbAppView, { bus: this.bus });
        }
    }

    EFB_API.use(GateFinderEfbApp, { isSearchable: true, isFavoritable: true });
})();
