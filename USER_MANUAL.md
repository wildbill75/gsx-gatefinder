# GateFinder V2.0.7 — User Manual (MSFS 2020 & MSFS 2024)

**GateFinder V2.0.7** is an all-in-one airport surface navigation, intelligent stand assignment, GSX Pro integration, and AI ATC ground companion for **Microsoft Flight Simulator 2020 & 2024**. It operates as:
- A standalone **Desktop Application** (with 4K / high-DPI support, scrollable Settings, and persistent window geometry),
- A native **MSFS 2024 Tablet EFB App** & **MSFS 2020/2024 In-Game Toolbar Panel (`GATEFINDER V2.0.7`)** optimized for 2D monitors and **Virtual Reality (VR)**,
- A native **Fenix A319 / A320 / A321 Cockpit EFB App** (on both Captain and First Officer tablets),
- A **Live Web EFB** accessible on any iPad, Android tablet, or smartphone via QR code.

---

## Table of Contents

1. [Key Features Overview](#1-key-features-overview)
2. [Installation & Initial Setup](#2-installation--initial-setup)
3. [Interface, 4K DPI Scaling & Resizable Workspace](#3-interface-4k-dpi-scaling--resizable-workspace)
4. [Flight Dispatch, Direct Live MSFS Mode & Turnaround Workflow](#4-flight-dispatch-direct-live-msfs-mode--turnaround-workflow)
5. [Airline, Cargo, Military (`Mil`), Business Jet & GA Operations](#5-airline-cargo-military-mil-business-jet--ga-operations)
6. [Position Selector Modal, Map Stand Selection & Native SimConnect Warp](#6-position-selector-modal-map-stand-selection--native-simconnect-warp)
7. [ATC Taxi Clearance & Interactive Taxiway Route Editing (VATSIM / IVAO / VR)](#7-atc-taxi-clearance--interactive-taxiway-route-editing-vatsim--ivao--vr)
8. [Interactive Lido Surface Chart & `Follow + Hdg Up` Smart Zoom](#8-interactive-lido-surface-chart--follow--hdg-up-smart-zoom)
9. [Live Traffic, Multi-Column Stand Status & MARS Stand Protection](#9-live-traffic-multi-column-stand-status--mars-stand-protection)
10. [MSFS 2024 EFB App, In-Game Toolbar Panel (`GATEFINDER V2.0.7`), VR & Fenix EFB](#10-msfs-2024-efb-app-in-game-toolbar-panel-gatefinder-v207-vr--fenix-efb)
11. [External Tablet & Smartphone Web EFB (QR Code)](#11-external-tablet--smartphone-web-efb-qr-code)
12. [Settings Reference](#12-settings-reference)
13. [Troubleshooting & Uninstallation](#13-troubleshooting--uninstallation)

---

## 1. Key Features Overview

- **Intelligent Multi-Category Stand Dispatch (Airlines, Cargo, Military, Business Jets & GA)**: Automatically selects the most realistic departure and arrival stands for your flight by cross-referencing your **SimBrief OFP** or **Live MSFS Aircraft** (airline ICAO, spoken ATC callsign, exact aircraft wingspan, freighter livery, military airframe, business jet, or light GA) with your local **FSDreamTeam GSX Pro profiles**, MSFS BGL scenery data, and OpenStreetMap airport layouts.
- **Direct Live MSFS Flight Mode (No SimBrief Required)**: Fly VFR or IFR directly in MSFS without generating a SimBrief OFP. GateFinder automatically detects your live aircraft type, wingspan, and GPS airport in MSFS (including small VFR airfields) and offers to load your live flight with a single click.
- **Native Cockpit Tablet Integrations (MSFS 2024 EFB + Fenix A320 Family EFB + Toolbar Panel)**: Embedded directly as a dedicated app inside the **native MSFS 2024 EFB tablet** and the **Fenix A319/A320/A321 EFB tablet** (Captain & First Officer screens), alongside the universal **MSFS In-Game Toolbar Panel** for 2D & VR.
- **Real-Time AI ATC Integration (BeyondATC & SayIntentions.AI Full Taxiway Sync)**: Automatically detects your pre-assigned gate, cleared departure runway, full progressive taxiway routing (`taxi via ...`), holding point, landing runway, and arrival gate directly from **BeyondATC** or **SayIntentions.AI** (including VFR & CTAF self-announce traffic)—updating the phase source indicator, taxi clearance pills, and green ground route in real time.
- **Interactive Taxiway Route Editing (VATSIM / IVAO / VR Visual Notepad)**: Click any taxiway badge directly on the Lido map (or click taxiway pills in the sidebar) to build, toggle, or override your ground taxi route on the fly—acting both as an instant visual ATC notepad (ideal in VR) and a live A* route calculator.
- **GSX Pro Two-Way Sync & Native SimConnect Reposition (`Warp`) Fallback**: Automatically arms and syncs your assigned gate with **GSX Pro**. When using **Reposition Aircraft Here (Warp)**, GateFinder uses GSX Pro when active or seamlessly falls back to **direct native SimConnect aircraft teleportation** if GSX Pro is not installed, not running, or unresponsive.
- **4K / High-DPI Ready & Resizable Workspace**: DPI-aware window sizing with a smooth scrollable Settings view so bottom controls are never cut off on 4K displays at 200%–250%+ Windows scaling.
- **VATSIM, IVAO & MARS Multi-Stand AI Traffic Protection**: Checks live online network traffic (VATSIM & IVAO) and local SimConnect AI aircraft so you are never assigned an occupied gate, and actively clears conflicting MSFS AI aircraft—including overlapping adjacent **MARS** sub-stands (e.g., `41L`/`41R` or `A 4`/`A 41`).

---

## 2. Installation & Initial Setup

1. **Extract & Launch**:
   - Place the `GateFinder` folder anywhere on your PC and launch `GateFinder.exe`.
   - A fast native startup splash screen appears immediately while GateFinder initializes and fetches your active SimBrief flight plan.
2. **Open Settings**:
   - Click the **Settings** button in the top-right corner of the main window.
3. **Configure SimBrief**:
   - Enter your **SimBrief Username or Pilot ID** in the *Dispatch & Stand Selection* card and click **Test Connection** to verify your account.
4. **Verify MSFS & GSX Paths**:
   - In the *MSFS Paths & In-Game Toolbar Panel* card:
     - Click **Auto-Detect** next to **GSX Profile Path** (default: `%APPDATA%\Virtuali\GSX\MSFS`).
     - Verify your **Primary Community Folder** and/or **Secondary / MSFS 2024 Folder** (automatically detected from your MSFS `UserCfg.opt`).
5. **Install the MSFS In-Game Panel / MSFS 2024 EFB / Fenix EFB**:
   - Click **Install Panel**. GateFinder deploys the `gatefinder-ingame-panel` package (`GATEFINDER V2.0.7`) into your Community folder(s), enabling both the **MSFS Toolbar Panel**, the **native MSFS 2024 EFB App**, and (when enabled) the **Fenix A320 EFB App**.
6. **Return to Main View**:
   - Click **Back** in the top-right corner—all settings are saved automatically.

---

## 3. Interface, 4K DPI Scaling & Resizable Workspace

### Window Sizing, 4K DPI Scaling & Persistence
- On first launch, GateFinder opens in a wide 16:9 landscape layout (`1600x870`) with full **4K / High-DPI scaling support (200%–250%+)**.
- The **Settings** panel features smooth mouse-wheel vertical scrolling so that bottom buttons (such as the In-Game Panel / EFB installers) are always accessible regardless of screen resolution or Windows scaling level.
- Whenever you move, resize, or maximize the GateFinder window, its exact dimensions and screen coordinates are saved to `settings.json` and restored on your next launch.

### Top Flight Strip
- **Airline / Operation Logo & Camaïeu Badges**: Once a SimBrief OFP or Live MSFS flight is loaded, the top bar displays:
  1. **Airline Logo or Vector Badge (`MIL`, `CAR`, `BIZ`, `GA`)** on a crisp badge.
  2. **Operator Code & Name** (e.g., `BEL - Brussels Airlines`, `FDX - FedEx Express`, `CTM - Armée de l'Air (COTAM)`, `BIZ - Business Aviation`).
  3. **Flight Callsign** (e.g., `BEL3033`, `FDX5012`, `COTAM01`, or aircraft tail number).
  4. **Aircraft Registration** (e.g., `OO-SNL`).
  5. **Exact Aircraft & Engine Variant** (e.g., `FENIX A320 - CFM56-5B4/P`).
- **Action Buttons**:
  - **Import SimBrief**: Fetches your latest active SimBrief OFP (or prompts to load your Live MSFS flight if parked at a different airport/aircraft) and computes gates and taxi routes.
  - **Settings**: Opens the configuration view (including the Tablet/Phone Web EFB QR Code).

### Phase Selector Bar (`DEPARTURE` / `ARRIVAL`)
- Two large interactive cards let you switch between your **DEPARTURE** airport and **ARRIVAL** airport at any stage of the flight (while airborne, the view automatically locks onto **ARRIVAL**).
- Each card displays three status pills:
  - **Airport ICAO** (e.g., `LFPO` / `EBBR`)
  - **Assigned Stand** (e.g., `STAND A 41` / `STAND B 214`)
  - **Active Runway** (e.g., `RWY 20` / `RWY 07R`)

### Resizable Left Sidebar Splitter
- Drag the **vertical splitter handle** between the left dispatch column and the right Lido map left or right to adjust the sidebar width (`sidebar_width` is saved automatically).
- All three left cards (**Airport & Stand Hero Card**, **ATC Taxi Clearance**, and **Traffic & Stand Status**) dynamically widen and reflow their text and pills in real time.

---

## 4. Flight Dispatch, Direct Live MSFS Mode & Turnaround Workflow

### Phase Source Indicator Pill (`GateFinder`, `BeyondATC`, `SayIntentions.AI`, `Manual Selection`)
In the Airport & Stand Hero Card on the left sidebar, the source pill clearly indicates which system is currently controlling the active phase (`DEPARTURE` or `ARRIVAL`):
- **`GateFinder`** *(Default)*: GateFinder's dispatch engine (using your SimBrief OFP or Live MSFS aircraft, GSX profile, airline/cargo/military/GA rules, and online traffic checks) is managing the stand and runway for this phase.
- **`BeyondATC`** / **`SayIntentions.AI`**: Automatically displayed as soon as BeyondATC or SayIntentions.AI pre-assigns a stand or issues an active runway, full `taxi via ...` clearance, or arrival gate assignment for that phase (including when you manually pick a gate from the BeyondATC in-game dropdown menu).
- **`Manual Selection`**: Displayed when you manually pick a stand from the GateFinder map or Stand Selector modal.

### Direct Live MSFS Flight Mode (VFR / IFR without SimBrief)
If you spawn in MSFS at a different airport or in a different aircraft than your last SimBrief OFP (for example, hopping into a Cessna 172, TBM 930, Falcon, or Rafale for a spontaneous flight):
- GateFinder automatically detects the mismatch via SimConnect and displays a prompt allowing you to **Load Live MSFS Flight** (with an optional destination ICAO field for point-to-point flights, or leave blank for local pattern/VFR flights) or **Import Latest SimBrief OFP**.

### Turnaround & Live Parked Stand Detection
When you click **Import SimBrief** (or on startup), GateFinder cross-checks your SimBrief OFP with your aircraft's live SimConnect position in MSFS:
- **Keep Current Stand**: Locks GateFinder onto the exact stand where your aircraft is physically parked in MSFS (or your previous compatible arrival stand on a turnaround) and computes the taxi route from that stand.
- **New Stand**: Assigns a new stand or opens the Stand Selector modal so you can pick another gate.

---

## 5. Airline, Cargo, Military (`Mil`), Business Jet & GA Operations

GateFinder V2.0.7 automatically adapts its stand selection engine to five distinct aviation categories without requiring manual mode switching:

1. **Commercial Passenger Airlines**:
   - Matches your airline ICAO code to real-world terminal rules (`airlines_terminals.json`), GSX `.ini` gate assignments, and MSFS scenery airline codes, prioritizing jetway-equipped gates with realistic wingspan margins (including automatic **MARS multi-stand bay resolution** for narrowbody vs. widebody variants).
2. **Automatic Cargo & Freighter Operations (`CAR` / Cargo Airlines)**:
   - Automatically detects **60+ dedicated cargo airlines** (`FDX`, `UPS`, `CLX`, `DHK`, `GEC`, `BOX`, `GTI`, `CKS`, `SQC`, `AZG`, `TAY`, `ABR`, `BCS`, `CMA`, `CJT`, etc.), spoken MSFS ATC callsigns (`"FEDEX"`, `"CARGOLUX"`, `"GIANT"`, etc.), and **freighter aircraft/liveries** (`B77L`, `B748F`, `MD11F`, `BCF`, `P2F`, `BDSF`, `777F`, `SkyCargo`, etc.).
   - Automatically assigns **Cargo Apron / Freighter Ramps** (`RAMP_CARGO`), prioritizing stands matching your cargo carrier and excluding passenger jetway gates—even when *Force Cargo Mode* is left unchecked.
3. **Military Aviation (`MIL` — Fighters, Trainers & Heavy Military Transports)**:
   - Automatically detects military fighter/trainer aircraft (`Rafale`, `Mirage 2000`, `Eurofighter Typhoon`, `F-16`, `F/A-18`, `F-35`, `F-15`, `A-10`, `Hawk`, `Alpha Jet`, `PC-21`, `T-6`, `T-38`, etc.), heavy military transports & tankers (`A400M Atlas`, `C-17 Globemaster`, `C-130J Hercules`, `C-160 Transall`, `CN-235`/`C-295`, `A330 MRTT Phénix/Voyager`, `KC-135`, `KC-46`, `E-3 AWACS`, `P-8 Poseidon`), and Air Force callsigns (`COTAM`/`FAF`, `FNY`, `RCH`, `RRR`/`ASCOT`, `GAF`, `BAF`, etc.).
   - **Priority 1 (`Mil` Stands)**: Assigns stands tagged **`Mil` / `Military`** (`RAMP_MIL_CARGO`, `RAMP_MIL_COMBAT`, or GSX/OSM Military Aprons) and displays the **`MIL`** tactical badge on the map.
   - **Priority 2 (Smart Civilian Airport Fallback)**: If the arrival or departure airport has no dedicated `Mil` stands, GateFinder automatically assigns a **Cargo / Remote Heavy Ramp** for heavy military transports ($\ge 24\text{ m}$ wingspan) or a **GA / FBO Ramp** for fighters and trainers ($< 24\text{ m}$ wingspan).
4. **Business Aviation (`BIZ`) & General Aviation (`GA`)**:
   - Automatically detects Business Jets (`Falcon`, `Global`, `Challenger`, `Gulfstream`, `Citation`, `Phenom`, `Pilatus PC-24`, `HondaJet`) and Light GA aircraft (`C172`, `DA40`, `DA62`, `SR22`, `TBM`, `PC-12`, `King Air`, `Kodiak`) and assigns **FBO / General Aviation Ramps** (`RAMP_GA`), matching your aircraft's exact wingspan instead of commercial airliner gates.

---

## 6. Position Selector Modal, Map Stand Selection & Native SimConnect Warp

You can change your departure or arrival stand at any time:
- **From the Left Sidebar**: Click the **large Stand badge** (e.g., `A 41` or `B 214`) or the stand pill in the ATC Taxi Clearance card to open the **Terminal / Gate Selector** modal (stands are organized by Terminal, Gate Prefix, Cargo Apron, Military Apron `(Mil)`, and GA Apron).
- **Directly on the Lido Map**:
  - **Left-Click** any stand tag on the map to open the stand action menu (**Select Stand** or **Reposition Aircraft Here (Warp)**).
- **Native SimConnect Reposition (`Warp`) Fallback**:
  - Selecting **Reposition Aircraft Here (Warp)** teleports your aircraft to the chosen stand. If **GSX Pro** is running, GateFinder triggers GSX's native reposition workflow; if GSX Pro is not installed, not running, or unresponsive, GateFinder automatically uses its **built-in direct SimConnect teleportation** to place and align your aircraft precisely on the stand.
- **GSX Pro Map Confirmation Toast**:
  - Every time you select a gate manually or when `BeyondATC` / `SayIntentions.AI` updates your stand, a compact borderless toast pops in the center of the map (e.g., `Stand 229R • GSX Pro Armed`) confirming that GateFinder has registered the choice and armed **GSX Pro**.

---

## 7. ATC Taxi Clearance & Interactive Taxiway Route Editing (VATSIM / IVAO / VR)

The **ATC TAXI CLEARANCE** card on the left sidebar displays your ground route as a sequence of color-coded camaïeu pills:

- **Departure Sequence**:
  - `[Stand Pill]` ➔ `[Taxiway Pills (e.g., W2, LJS, W22, W21)]` ➔ `[Runway Dropdown Pill (e.g., RWY 20 ▾)]`
- **Arrival Sequence**:
  - `[Runway Dropdown Pill (e.g., RWY 07R ▾)]` ➔ `[EXIT : C2]` ➔ `[Taxiway Pills (e.g., W1, F3, E5, S, M, INN 5)]` ➔ `[Stand Pill]`
- **Interactive Taxiway Route Editing (Click on Map or Sidebar — Ideal for VATSIM / IVAO / VR)**:
  - **Click any Taxiway Badge on the Lido Map**: Starts or appends that taxiway to your custom taxi clearance—acting as an instant visual notepad in the cockpit or VR while simultaneously recalculating the green A* route through your selected taxiways!
  - **Click any Taxiway Pill in the Sidebar (`×` hover)**: Removes that taxiway from your route.
  - **`Auto` & `Clear` Header Buttons**: Click **`Clear`** to clear all intermediate taxiways and click your ATC taxi instructions step-by-step on the map, or click **`Auto`** to return to automatic A* shortest-path routing.
- **Changing the Active Runway**:
  - Click the **`RWY XX ▾`** dropdown pill (or click any runway threshold circle directly on the Lido chart) to switch runways. Selecting a different runway immediately recalculates the taxi route and updates the chart.

---

## 8. Interactive Lido Surface Chart & `Follow + Hdg Up` Smart Zoom

The right workspace houses a custom-rendered **Lido Vector Surface Chart** engineered for high situational awareness on the ground.

### Default Whole-Airport Centering
- By default, the **`Route`** view frames and centers on the **entire airport** (all airport runways, terminal buildings, and active taxi route), ensuring that multi-runway airports (such as LFPO, EBBR, LFPG, EGLL) are completely visible and balanced in the center of the map pane.

### Top Map Control Bar
- **`Gate Secured (Auto-Clear Active)`**: Status pill showing SimConnect connection and AI traffic stand protection state.
- **`+` / `-`**: Zoom in and out (or use the **Mouse Scroll Wheel** anywhere on the map, and **Left-Click + Drag** to pan).
- **`Gate`**: Instant **Apron Parking Chart** view—zooms tightly onto your assigned stand, showing nearby gates, airline/military badges, and terminal layout.
- **`Route`**: Instant **Airport Ground Chart** overview—centers and frames the full airport layout and active taxi route.
- **`Follow + Hdg Up`**:
  - Locks the camera onto your live aircraft position at the exact geometric center of the map viewport with dynamic **Heading-Up** chart rotation (all labels and stand tags counter-rotate to stay upright).
  - **Heading-Invariant Radial Smart Zoom**: Smoothly and progressively zooms in as you approach your departure holding point or arrival stand without zoom jumps during 90° taxi turns.
  - Automatically engages on touchdown (`LANDING_ROLL` / `TAXI_IN`) on arrival, with intelligent forward-cone high-speed runway exit tracking.
- **`Map Day` / `Map Night`**:
  - Switches between **Lido Night** (dark slate cockpit EFB theme) and **Lido Day** (authentic paper chart theme).

---

## 9. Live Traffic, Multi-Column Stand Status & MARS Stand Protection

At the bottom of the left sidebar, the **TRAFFIC & STAND STATUS** card monitors airport stand occupancy in real time:
- **Multi-Column Responsive Grid**: Occupied stands are stacked in a clean multi-column grid (**at least 3 columns wide**, automatically expanding to **4, 5, or 6+ columns** as you widen the left panel with the splitter).
- **Internal Scrollbar**: When busy hubs have dozens of occupied stands on VATSIM/IVAO, an internal vertical scrollbar lets you scroll smoothly through all occupied gates with the mouse wheel without ever overflowing the window.
- **MARS Overlapping / Double Stand Protection**: Automatically protects overlapping multi-aircraft ramp stands (e.g., `41L`/`41R` or widebody `A 4` / narrowbody `A 41`) from AI traffic collisions and selects the sub-stand variant matching your aircraft's wingspan.
- **Network Tags**:
  - **`(VATSIM)`** — Occupied by a live pilot on VATSIM.
  - **`(IVAO)`** — Occupied by a live pilot on IVAO.
  - **`(AI/LIVE)`** — Occupied by an MSFS SimConnect AI or multiplayer aircraft.

---

## 10. MSFS 2024 EFB App, In-Game Toolbar Panel (`GATEFINDER V2.0.7`), VR & Fenix EFB

### 1. Native MSFS 2024 Tablet EFB Integration
- When installed into your MSFS 2024 Community folder, GateFinder appears as a **dedicated native app icon directly inside the MSFS 2024 EFB tablet** (`GateFinder`), featuring a tailored cockpit tablet layout and full real-time synchronization with the desktop app.

### 2. Fenix A320 Family Cockpit EFB Integration (`A319` / `A320` / `A321`)
- Enable **Enable GateFinder app on Fenix A320 series EFB tablet** in Settings (and click **Install Panel**).
- GateFinder appears directly on the **Fenix tablet home screen** (both Captain and First Officer EFBs) and behaves like a native Fenix app (respecting the Fenix Home button and tablet power/boot states).

### 3. MSFS In-Game Toolbar Panel (MSFS 2020 & 2024 — 2D & VR)
1. Load a flight in **MSFS 2020** or **MSFS 2024**.
2. Open the **MSFS Top Toolbar** and click the **GateFinder** icon (`GATEFINDER V2.0.7`).
3. **VR & Cockpit Ergonomics**:
   - Features the same resizable left sidebar splitter, full-airport default centering, interactive taxiway builder, GSX Pro confirmation toast, and `Follow + Hdg Up` Lido vector map as the desktop app, with enlarged hitboxes for VR controllers and head-tracked cursors.

---

## 11. External Tablet & Smartphone Web EFB (QR Code)

You can use GateFinder V2.0.7 on an external **iPad, Android tablet, or smartphone** over your local Wi-Fi network:
1. Open **Settings** in the GateFinder desktop app and click **Open Tablet / Web EFB (QR Code)** (or scan the QR code displayed in the modal).
2. Your tablet or phone browser will open `http://<YOUR_PC_LAN_IP>:8420/efb` with the full interactive GateFinder V2.0.7 Lido EFB synchronized in real time.
3. **Important Note for VPN Users (ProtonVPN, NordVPN, etc.)**:
   - GateFinder automatically detects your PC's physical Wi-Fi/Ethernet LAN IP (`192.168.x.x`) even if a VPN is running on your PC.
   - However, if a **VPN app is active on your tablet or smartphone**, the mobile VPN may block local Wi-Fi (`192.168.x.x`) traffic. Either enable **"Allow LAN connections"** (Split Tunneling) in your mobile VPN settings or disconnect the VPN on your tablet/phone while using the Web EFB.

---

## 12. Settings Reference

### 1. Dispatch & Stand Selection
| Option | Description |
| :--- | :--- |
| **SimBrief Username or Pilot ID** | Your SimBrief Pilot ID or username used to download your latest OFP. Use **Test Connection** to validate. |
| **Auto-fetch latest SimBrief OFP on startup** | Automatically imports your active SimBrief flight plan as soon as GateFinder launches. |
| **Prompt to keep arrival or live MSFS parked stand on Turnaround** | Asks whether to keep your current physical stand or pick a new one when importing an OFP while already parked at an airport. |
| **Suppress desktop popups (Cockpit / VR mode)** | Prevents automatic blocking modals (Live Stand Selection, Turnaround & SimBrief Mismatch) from stealing desktop/simulator focus, replacing them with a discreet inline desktop bar and in-sim EFB resolution. |
| **Auto-select 'Use MSFS Aircraft' on SimBrief mismatch** | Automatically applies your spawned MSFS aircraft in the background whenever a SimBrief aircraft/airport mismatch is detected, bypassing the mismatch prompt. |
| **Force Cargo Mode** | Optional manual override to force cargo ramps even when flying a passenger aircraft (freighter aircraft and cargo airlines are already detected automatically). |

### 2. ATC, GSX Pro & Online Traffic
| Option | Description |
| :--- | :--- |
| **Auto-sync gate & active runway assigned by AI ATC** | Automatically syncs pre-assigned gates, active runways, full `taxi via ...` routes, and arrival gate assignments from **BeyondATC** and **SayIntentions.AI**. |
| **Enable GSX Pro Arrival Auto-Sync** | Automatically arms and communicates your selected gate to GSX Pro so marshallers and jetways are pre-configured. |
| **Filter occupied stands on VATSIM & IVAO** | Excludes stands currently occupied by online pilots on VATSIM/IVAO during automatic gate assignment (with automatic Pre-TOD & Approach re-checks). |
| **Auto-clear MSFS AI traffic at assigned stands** | Automatically despawns conflicting MSFS AI traffic parked at your assigned departure or arrival gate. |
| **Protect overlapping / double stands (MARS) from AI & traffic collisions** | Clears AI traffic on overlapping adjacent sub-stands (e.g., `41L`/`41R` or `A 4`/`A 41`) so widebody/narrowbody multi-bay stands are completely free. |
| **SayIntentions.AI SAPI Key** | Automatically detected and displayed from your local SayIntentions.AI installation (`%LOCALAPPDATA%\SayIntentionsAI\flight.json`). Can also be edited manually if needed. |

### 3. Performance & System
| Option | Description |
| :--- | :--- |
| **Auto-Start GateFinder silently when MSFS launches** | Registers GateFinder in MSFS `exe.xml` so the background service starts automatically with the simulator. |
| **Auto-Quit GateFinder automatically when MSFS closes** | Closes GateFinder cleanly a few seconds after Microsoft Flight Simulator exits. |
| **Enable GateFinder app on Fenix A320 series EFB tablet** | One-click toggle to enable or disable the native GateFinder app on the Fenix A319/A320/A321 cockpit EFB tablet. |
| **Auto-suspend Lido chart rendering while airborne** | Pauses high-frequency map redraws during cruise flight to guarantee zero CPU/GPU impact while airborne, automatically resuming on approach/touchdown. |
| **Map Follow Refresh Rate (`Follow + Hdg Up`)** | Select **`5 Hz (Eco)`**, **`10 Hz (Balanced)`** *(default)*, or **`20 Hz (Ultra Smooth)`** for live aircraft tracking on the Lido map. |

### 4. MSFS Paths & In-Game Toolbar Panel
| Option | Description |
| :--- | :--- |
| **GSX Profile Path** | Path to your FSDreamTeam GSX `.ini` airport profiles (`%APPDATA%\Virtuali\GSX\MSFS`). Click **Auto-Detect** to locate automatically. |
| **Primary Community Folder** | Path to your primary MSFS `Community` folder. |
| **Secondary / MSFS 2024 Folder** | Optional path to a second `Community` folder (if you have both MSFS 2020 and MSFS 2024 installed). |
| **MSFS In-Game Toolbar Panel & EFB** | Click **Install Panel** or **Uninstall Panel** to add or remove `gatefinder-ingame-panel` (`GATEFINDER V2.0.7`) from your Community folder(s). |
| **Uninstall GateFinder** *(Red Button)* | Completely removes the MSFS In-Game Panel & EFB hooks from all Community folders, cleans up `exe.xml` auto-start entries, and prepares GateFinder for removal. |

---

## 13. Troubleshooting & Uninstallation

- **In-Game Panel / Cockpit EFB shows "GateFinder is not running"**:
  - Ensure `GateFinder.exe` is running on your PC (check your Windows system tray). If you enable **Auto-Start GateFinder silently when MSFS launches** in Settings, it will launch automatically with MSFS.
- **Tablet / Smartphone QR Code Web EFB does not load**:
  - Make sure your tablet/phone is connected to the same local network as your PC, and check that any VPN on your tablet/phone (such as ProtonVPN) is either disabled or has **"Allow LAN connections"** enabled.
- **Uninstalling GateFinder**:
  - Open **Settings** and click the red **Uninstall GateFinder** button at the bottom-right (or run `Uninstall_GateFinder.bat`). This cleanly removes the `gatefinder-ingame-panel` package from all MSFS Community folders and removes the `exe.xml` auto-start hook.
