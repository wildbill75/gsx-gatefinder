# GateFinder — Changelog

## Version 2.0.7 (Latest Release)

### 🚀 New Features, UX Enhancements & Bug Fixes
- **Enhanced Aircraft Type Normalization & Persistent Default Mismatch Choice (`default_mismatch_action`):**
  - Expanded ICAO airframe normalization to handle Boeing 2-character alphanumeric customer codes (e.g., `737-8AS (RYR)`, `737-7H4`, `747-4R7F`), Airbus engine/subseries codes (`320-214`, `A320-251N`), parenthetical livery suffixes (`BOEING 738 (AUA)`), and manufacturer prefixes without false mismatch prompts.
  - Added a **`Make this default choice for 'Use MSFS Aircraft'`** checkbox directly inside the SimBrief/MSFS mismatch modal (both Desktop and MSFS In-Game Panel / EFB), plus a toggle in **Settings** (`Auto-select 'Use MSFS Aircraft' on SimBrief mismatch`) to automatically apply your spawned MSFS aircraft silently in the background on future flights.
- **SimBrief Auto-Import Arrival Airport Validation Fix (`dep == arr` Bug Fix):**
  - Strictly validated SimBrief XML/JSON route parsing (`origin` vs. `destination`, empty `{}` XML tag sanitization, ICAO FPL `-ADES` recovery, and active/session destination preservation) so auto-loads and blank-destination `Use MSFS Aircraft` resolutions never overwrite the arrival airport with the departure ICAO (`dep == arr`).
- **Full Cockpit / VR Popup Suppression Coverage (`suppress_popups_in_cockpit`):**
  - Extended `Suppress desktop popups (Cockpit / VR mode)` across all automatic desktop modals (Live Stand Selection, Turnaround Stand Prompt, SimBrief Mismatch, and live-flight reload splash), keeping desktop focus untouched for VR and home-cockpit setups while maintaining full interactive control in the MSFS EFB / In-Game Panel.
- **Enhanced Global OSM + Native MSFS BGL Airport Geometry Fallback:**
  - Upgraded the worldwide surface geometry loader (`taxi_router.py`) to close wide unclosed OSM apron ways, synthesize bounding apron hulls even on sparse airports with zero OSM stands/aprons, and automatically bridge disconnected stand clusters (`> 185 m` from OSM taxiways) via native MSFS BGL networks—eliminating truncated airport charts globally (including `LICC`).

---

## Version 2.0.6

### 🚀 New Features & Reliability Improvements
- **Intelligent Aircraft Type Normalization (SimBrief vs. MSFS Mismatch Fix):**
  - Normalized live MSFS aircraft telemetry against SimBrief ICAO codes—automatically stripping livery suffixes in parentheses (e.g., `(AUA)`), manufacturer prefixes (`BOEING`, `AIRBUS`, `EMBRAER`, `BOMBARDIER`, `CESSNA`), and mapping Neo/MAX/engine aliases (`BOEING 738 (AUA)` ↔ `B738`, `A20N` ↔ `A320`, `B38M` ↔ `B738`) to eliminate false mismatch alerts.
- **Cockpit / VR Desktop Popup Suppression Mode:**
  - Added a persistent **`Suppress desktop popups (Cockpit / VR mode)`** setting (`suppress_popups_in_cockpit`, default `False`).
  - When enabled, automatic blocking modals (**Live Stand Selection** and **SimBrief Mismatch**) never force-open over the desktop or simulator window; instead, a non-intrusive inline action bar is displayed directly on the desktop header while keeping full interactive resolution inside the MSFS In-Game Panel / EFB.
- **Global OSM + Native MSFS BGL Airport Geometry Fallback (Zero Truncated Charts Worldwide):**
  - Eliminated airport-by-airport geometry patches (such as `LICC`) by adding automatic open-ring stitching for OSM apron ways/multipolygons, native MSFS BGL runway/taxiway/parking/apron graph fusion when OSM coverage is incomplete, backtrack runway connectivity validation, and automatic oriented bounding apron synthesis around orphan stands.

---

## Version 2.0.5

### 🚀 Improvements & Performance Overhaul
- **Built-in One-Click Automatic GitHub Updater:**
  - Added an integrated automatic updater directly in the main chart bar that checks GitHub Releases, downloads updates with live progress, updates the MSFS In-Game/EFB package in `Community`, preserves user settings/session files, and restarts `GateFinder.exe` automatically.
- **SimBrief / MSFS Aircraft & Airport Mismatch Modal:**
  - Added a minimalist 3-option mismatch modal on both Desktop and MSFS In-Game Panel / EFB (`Open SimBrief` with automatic new-OFP polling, `Use MSFS Aircraft`, `Keep SimBrief OFP`) whenever your spawned MSFS aircraft or airport differs from your SimBrief OFP.
- **World's 50 Largest Airports Full Geometry Audit & Repair (`geom_v=4`):**
  - Audited, repaired, and pre-cached complete `geom_v=4` Lido vector surface charts for the **50 largest airports worldwide by surface area** (`OEDF`, `OMDW`, `KDEN`, `OEJN`, `WMKK`, `KATL`, `LTFM`, `KDFW`, `OERK`, `KMCO`, `KIAD`, `ZBAD`, `KIAH`, `KMCI`, `ZSPD`, `HECA`, `VTBS`, `LFPG`, `KSLC`, `LEMD`, `OMDB`, `KORD`, `LIRF`, `EHAM`, `CYMX`, `KMEM`, `UUDD`, `OTHH`, `EDDF`, `RJTT`, `ESSA`, `KMSP`, `CYYZ`, `YSSY`, `YBBN`, `VIDP`, `KDTW`, `KSFO`, `ZBAA`, `KCLT`, `KJFK`, `WSSS`, `WMKP`, `LEBL`, `EDDM`, `FAOR`, `RCTP`, `RPLL`, `VHHH`, `LOWW`, `LSZH`, `LFPO`, `RKSI`).
  - Guaranteed 100% full-field runway extents, remote satellite aprons, perimeter taxiways, and terminal footprints—shipped ready-to-fly offline in `taxi_charts_cache.json`.
- **Major Desktop UI & Moving-Map Performance Optimization:**
  - **Localized GDI Route Rendering:** Split active taxi route rendering into a static route tail and a localized dynamic nose segment (`~40×40 px`), eliminating full-canvas Windows GDI repaints during taxiing (`~38×` faster map updates on dense hubs like `EDDF`, `LFPG`, and `KORD`).
  - **Spatial-Grid A\* Router & Wide-Apron Hysteresis:** Added `0.002°` spatial-grid node lookup, pre-indexed taxiway edges, parked/rollout route memoization, background SimBrief graph pre-warming, and `28 m` off-node hysteresis on wide aprons to completely eliminate periodic multi-second moving-map freezes.
  - **Zero-Blocking Airport Resolution & Low-Overhead SimConnect Drain:** Resolved distant runways (e.g., `EHAM` `18R` Polderbaan) locally in `< 0.5 ms` without blocking Overpass HTTP calls, added stationary SimConnect anti-jitter stabilization (`0 %` idle CPU at the gate), and switched SimConnect to non-blocking bounded packet draining.

### 🐛 Bug Fixes (from v2.0.4)
- **Clean MSFS 2020 / 2024 Shutdown (`RECV_QUIT` & Handle Release):** Fixed an issue where MSFS or Gaming Services could remain stuck running on exit by actively handling SimConnect `RECV_QUIT` and immediately closing the native `SimConnect.dll` handle when the simulator exits.
- **Passenger Airliner `WF` Suffix Cargo Fix:** Fixed a false Cargo (`CAR`) classification when spawning passenger airliners with `WF` (Wingtip Fence) model titles such as `FENIXA320 CFM WF`, and added MSFS 2024 `LIVERY NAME` airline extraction.
- **SayIntentions.AI Progressive Taxi Stability:** Prevented SayIntentions breadcrumb prefix trimming from triggering redundant UI re-renders while taxiing.

---

## Version 2.0.4

### 🚀 New Features & Roadmap Additions
- **Native MSFS 2024 Tablet EFB Integration:**
  - GateFinder is now embedded as a dedicated app right inside the **native MSFS 2024 tablet EFB**, featuring a tailored cockpit layout and full real-time synchronization with the desktop and web apps.
- **Fenix A320 Family Cockpit EFB Integration (A319 / A320 / A321):**
  - GateFinder can now be launched directly from the **Fenix tablet home screen** (both Captain and First Officer EFBs), behaving like a native Fenix app (including the tablet Home button and power/boot states).
- **Dedicated EFB & Lifecycle Controls in Settings:**
  - Added one-click Install/Uninstall and Enable/Disable controls for both the MSFS EFB/In-Game Panel and the Fenix EFB, plus a new **"Auto-Quit GateFinder automatically when MSFS closes"** option.
- **Interactive Taxiway Route Editing (VATSIM / IVAO / VR Mode):**
  - Click directly on taxiway labels on the Lido chart (or pills in the sidebar) to build, toggle, or override your taxi clearance on the fly (`Auto` / `Clear` modes). Recalculates the green A* taxi route through your selected taxiways in real time and acts as an instant visual notepad so you never have to scramble to write down ATC taxi instructions (especially in VR!).
- **SayIntentions.AI Full Taxiway Route Sync & BeyondATC Override Sync:**
  - Extended the **SayIntentions.AI** integration to automatically parse full `"taxi via ..."` clearances, pre-assigned departure/arrival stands, active runways, and VFR/CTAF self-announce traffic—matching the seamless **BeyondATC** workflow.
  - **Automatic SayIntentions.AI SAPI Key Detection:** Automatically detects your local SayIntentions SAPI key and displays it in Settings.
  - **BeyondATC Arrival Gate Pre-Assignment & Dropdown Sync:** Displays BeyondATC's pre-assigned arrival gate early and immediately updates GateFinder and GSX Pro if you manually choose a different gate from the BeyondATC dropdown menu.
- **General Aviation (`GA`), Business Aviation (`BIZ`) & Direct Live MSFS Flight Mode (No SimBrief Required):**
  - Dedicated support for GA props, turboprops (`C172`, `TBM9`, `PC12`, `DA62`, `SR22`, etc.), and business jets (`Falcon`, `Global`, `Challenger`, `Gulfstream`, `Citation`, `Phenom`, `PC-24`)—automatically prioritizing GA ramps, FBOs, and non-jetway stands matching your aircraft's exact wingspan instead of commercial airliner gates.
  - Fly directly in MSFS without generating a SimBrief OFP: GateFinder detects live airport/aircraft mismatches via SimConnect (including small VFR airfields via OpenStreetMap fallback) and lets you load your live MSFS flight in one click.
- **Bonus — Automatic Cargo (`CAR`) & Military (`Mil`) Stand Dispatch:**
  - **Automatic Cargo Detection:** Recognizes 60+ dedicated cargo airlines (`FDX`, `UPS`, `CLX`, `DHK`, `GEC`, `BOX`, `GTI`, `CKS`, `SQC`, `AZG`, `TAY`, `ABR`, `BCS`, `CMA`, etc.) and freighter aircraft/liveries (`777F`, `747-8F`, `BCF`, `P2F`, `BDSF`, `SkyCargo`, etc.), assigning Cargo Aprons automatically without needing to enable *Force Cargo Mode*.
  - **Automatic Military (`Mil`) Dispatch:** Recognizes military fighters/trainers (`Rafale`, `Mirage 2000`, `Eurofighter`, `F-16`, `F/A-18`, `F-35`, `PC-21`, `Alpha Jet`, etc.), heavy military transports/tankers (`A400M Atlas`, `C-17`, `C-130J`, `A330 MRTT`, `KC-135`, `KC-46`, `AWACS`), and Air Force callsigns (`COTAM`/`FAF`, `RCH`, `RRR`/`ASCOT`, `GAF`, `BAF`, etc.). Prioritizes **`Mil`** stands with smart fallback at civilian airports.
- **Native SimConnect Reposition (`Warp`) Fallback:**
  - Direct SimConnect aircraft teleportation and heading alignment to the selected stand if GSX Pro is not installed, not running, or unresponsive.
- **MARS Multi-Stand Bay Resolution & Overlap Protection:**
  - Automatically selects the sub-stand variant (`A 4` widebody vs. `A 41` narrowbody) matching your aircraft's wingspan and protects overlapping MARS stands from AI traffic collisions.
- **Configurable Map Follow Refresh Rate (`5 Hz / 10 Hz / 20 Hz`):**
  - Added a new refresh rate selector in Settings (`5 Hz Eco`, `10 Hz Balanced`, `20 Hz Ultra Smooth`) with sub-centimeter GPS precision and viewport frustum culling for ultra-smooth `Follow + Hdg Up` tracking with zero FPS impact.

### 🐛 Bug Fixes (from v2.0.3)
- **4K & Extreme Windows DPI Scaling Fix (200%–250%+):** Added DPI-aware window sizing and a smooth mouse-wheel scrollable Settings panel so that bottom controls (like the In-Game Panel / EFB installers and Uninstall button) never get cut off on heavily scaled 4K displays.
- **`Follow + Hdg Up` Aircraft Centering & Smart Zoom Stability:** Fixed viewport offset drift in `Follow + Hdg Up` mode so the aircraft symbol stays locked at the exact center of the map, and replaced bounding-box zoom with a heading-invariant radial smart zoom to eliminate erratic zoom jumps during 90° turns.
- **Arrival High-Speed Runway Exit Disambiguation:** Fixed an issue during landing roll where passing the first of two closely spaced runway exits (e.g., at EBBR) could leave both exits displayed until vacating the runway.
- **MARS Overlapping Stand AI Traffic Clearing:** Fixed an issue where MSFS AI aircraft parked on an overlapping adjacent sub-stand (`L`/`R` or widebody/narrowbody shared bay) were not cleared alongside the primary stand.
