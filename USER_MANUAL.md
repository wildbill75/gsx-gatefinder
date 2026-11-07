# GateFinder V2.0.4 — User Manual (MSFS 2020 & MSFS 2024)

**GateFinder V2.0.4** is an all-in-one airport surface navigation, intelligent stand assignment, GSX Pro integration, and AI ATC ground companion for **Microsoft Flight Simulator 2020 & 2024**. It operates as a standalone **Desktop Application**, a native **MSFS In-Game Toolbar Panel (`GATEFINDER V2.0.4`)** optimized for 2D monitors and **Virtual Reality (VR)**, and a **Live Web EFB** accessible on any iPad, Android tablet, or smartphone via QR code.

---

## Table of Contents

1. [Key Features Overview](#1-key-features-overview)
2. [Installation & Initial Setup](#2-installation--initial-setup)
3. [Interface & Resizable Workspace Overview](#3-interface--resizable-workspace-overview)
4. [Flight Dispatch, Source Indicators & Turnaround Workflow](#4-flight-dispatch-source-indicators--turnaround-workflow)
5. [Position Selector Modal & Interactive Map Stand Selection](#5-position-selector-modal--interactive-map-stand-selection)
6. [ATC Taxi Clearance & Route Editing](#6-atc-taxi-clearance--route-editing)
7. [Interactive Lido Surface Chart](#7-interactive-lido-surface-chart)
8. [Live Traffic & Multi-Column Stand Status](#8-live-traffic--multi-column-stand-status)
9. [MSFS In-Game Panel (`GATEFINDER V2.0.4`) & VR Mode](#9-msfs-in-game-panel-gatefinder-v203--vr-mode)
10. [External Tablet & Smartphone Web EFB (QR Code)](#10-external-tablet--smartphone-web-efb-qr-code)
11. [Settings Reference](#11-settings-reference)
12. [Troubleshooting & Uninstallation](#12-troubleshooting--uninstallation)

---

## 1. Key Features Overview

- **Intelligent Gate & Stand Assignment**: Automatically selects the most realistic departure and arrival stands for your flight by cross-referencing your **SimBrief OFP** (airline ICAO, aircraft wingspan, cargo vs. passenger mode) with your local **FSDreamTeam GSX Pro profiles**, MSFS scenery data, and OpenStreetMap airport layouts.
- **Airline Dynamic Camaïeu Theme**: Automatically extracts your operating airline's brand colors and applies a cohesive 6-shade color camaïeu across the top flight strip, departure/arrival phase selectors, stand hero card, taxi clearance pills, and traffic status pills.
- **Interactive Lido Vector Ground Chart**: High-contrast vector airport surface map centered by default on the **entire airport layout** (all runways, terminals, aprons, hold-short bars, airline logos on gates, and active green taxi routing).
- **Real-Time AI ATC Integration (BeyondATC & SayIntentions.AI)**: Automatically detects your cleared departure runway, taxiway routing, holding point, and arrival gate directly from **BeyondATC** or **SayIntentions.AI**—updating the phase source indicator, taxi clearance pills, and green ground route in real time.
- **GSX Pro Two-Way Sync & Map Confirmation Toast**: Automatically arms and syncs your assigned gate with **GSX Pro** (both on departure and arrival). Whenever you change your gate or receive an ATC gate/runway update, a sleek single-line confirmation toast (`Stand 229R • GSX Pro Armed`) pops in the center of the map to confirm that GSX Pro is armed and active.
- **Resizable Left Dispatch Panel & Persistent Window Geometry**: Drag the vertical splitter bar between the left sidebar and the map to resize all left cards smoothly; Traffic & Stand Status pills automatically reflow into 3, 4, 5+ columns with an internal scrollbar. GateFinder also remembers your exact window size, screen placement, and sidebar width across restarts.
- **VATSIM, IVAO & Live AI Traffic Filtering**: Checks live online network traffic (VATSIM & IVAO) and local SimConnect AI aircraft so you are never assigned an already occupied gate. Includes an active **AI Traffic Auto-Clear** shield that removes conflicting MSFS AI aircraft spawning on your assigned stand.

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
5. **Install the MSFS In-Game Toolbar Panel**:
   - Click **Install Panel**. GateFinder deploys the `gatefinder-ingame-panel` package (`GATEFINDER V2.0.4`) into your Community folder(s) and keeps it automatically synchronized on every startup.
6. **Return to Main View**:
   - Click **Back** in the top-right corner—all settings are saved automatically.

---

## 3. Interface & Resizable Workspace Overview

### Window Sizing & Persistence
- On first launch, GateFinder opens in a wide 16:9 landscape layout (`1600x870`) so all top map controls and sidebar cards have generous breathing room.
- Whenever you move, resize, or maximize the GateFinder window, its exact dimensions and screen coordinates are saved to `settings.json` and restored on your next launch.

### Top Flight Strip
- **Airline Logo & Camaïeu Badges**: Once a SimBrief flight plan is loaded, the top bar displays:
  1. **Airline Logo** on a crisp white badge.
  2. **Airline Code & Name** (e.g., `BEL - Brussels Airlines`).
  3. **Flight Callsign** (e.g., `BEL3033`).
  4. **Aircraft Registration** (e.g., `OO-SNL`).
  5. **Exact Aircraft & Engine Variant** (e.g., `FENIX A320 - CFM56-5B4/P`).
- **Action Buttons**:
  - **Import SimBrief**: Fetches your latest active SimBrief OFP and computes gates and taxi routes.
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

## 4. Flight Dispatch, Source Indicators & Turnaround Workflow

### Phase Source Indicator Pill (`GateFinder`, `BeyondATC`, `SayIntentions.AI`, `Manual Selection`)
In the Airport & Stand Hero Card on the left sidebar, the source pill clearly indicates which system is currently controlling the active phase (`DEPARTURE` or `ARRIVAL`):
- **`GateFinder`** *(Default)*: GateFinder's dispatch engine (using your SimBrief OFP, GSX profile, airline terminal rules, and online traffic checks) is managing the stand and runway for this phase.
- **`BeyondATC`** / **`SayIntentions.AI`**: Automatically displayed as soon as BeyondATC or SayIntentions.AI issues an active runway, taxi clearance, or gate assignment for that phase. For example, once you receive your departure clearance at the gate, **Departure** displays `BeyondATC` while **Arrival** remains on `GateFinder` until BeyondATC issues your arrival clearance.
- **`Manual Selection`**: Displayed when you manually pick a stand from the map or the Stand Selector modal.

### Turnaround & Live Parked Stand Detection
When you click **Import SimBrief** (or on startup), GateFinder cross-checks your SimBrief OFP with your aircraft's live SimConnect position in MSFS:
- **Keep Current Stand**: Locks GateFinder onto the exact stand where your aircraft is physically parked in MSFS (or your previous arrival stand on a turnaround) and computes the taxi route from that stand.
- **New Stand**: Assigns a new stand or opens the Stand Selector modal so you can pick another gate.

---

## 5. Position Selector Modal & Interactive Map Stand Selection

You can change your departure or arrival stand at any time:
- **From the Left Sidebar**: Click the **large Stand badge** (e.g., `A 41` or `B 214`) or the stand pill in the ATC Taxi Clearance card to open the **Terminal / Gate Selector** modal.
- **Directly on the Lido Map**:
  - **Left-Click** any stand tag on the map to select it as your active stand (or open the stand action menu).
  - **Right-Click** any stand tag on the map to open the context menu with **Select Stand** and **Reposition Aircraft Here (Warp)**.
- **GSX Pro Map Confirmation Toast**:
  - Every time you select a gate manually or when `BeyondATC` / `SayIntentions.AI` updates your stand, a compact borderless toast pops in the center of the map (e.g., `Stand 229R • GSX Pro Armed` or `BeyondATC • Stand A 41 • GSX Pro Armed`) confirming that GateFinder has registered the choice and armed **GSX Pro**.

---

## 6. ATC Taxi Clearance & Route Editing

The **ATC TAXI CLEARANCE** card on the left sidebar displays your ground route as a sequence of color-coded camaïeu pills:

- **Departure Sequence**:
  - `[Stand Pill]` ➔ `[Taxiway Pills (e.g., W2, LJS, W22, W21)]` ➔ `[Runway Dropdown Pill (e.g., RWY 20 ▾)]`
- **Arrival Sequence**:
  - `[Runway Dropdown Pill (e.g., RWY 07R ▾)]` ➔ `[EXIT : C2]` ➔ `[Taxiway Pills (e.g., W1, F3, E5, S, M, INN 5)]` ➔ `[Stand Pill]`
- **Changing the Active Runway**:
  - Click the **`RWY XX ▾`** dropdown pill (or click any runway threshold circle directly on the Lido chart) to switch runways. Selecting a different runway immediately recalculates the taxi route and updates the chart.

---

## 7. Interactive Lido Surface Chart

The right workspace houses a custom-rendered **Lido Vector Surface Chart** engineered for high situational awareness on the ground.

### Default Whole-Airport Centering
- By default, the **`Route`** view frames and centers on the **entire airport** (all airport runways, terminal buildings, and active taxi route), ensuring that multi-runway airports (such as LFPO, EBBR, LFPG, EGLL) are completely visible and balanced in the center of the map pane.

### Top Map Control Bar
- **`Gate Secured (Auto-Clear Active)`**: Status pill showing SimConnect connection and AI traffic stand protection state.
- **`+` / `-`**: Zoom in and out (or use the **Mouse Scroll Wheel** anywhere on the map, and **Left-Click + Drag** to pan).
- **`Gate`**: Instant **Apron Parking Chart** view—zooms tightly onto your assigned stand, showing nearby gates, airline logos, and terminal layout.
- **`Route`**: Instant **Airport Ground Chart** overview—centers and frames the full airport layout and active taxi route.
- **`Follow + Hdg Up`**:
  - Locks the camera onto your live aircraft position with dynamic **Heading-Up** chart rotation (all labels and stand tags counter-rotate to stay upright) and smart look-ahead zoom toward your target runway or stand.
  - Automatically engages on touchdown (`LANDING_ROLL` / `TAXI_IN`) on arrival.
- **`Map Day` / `Map Night`**:
  - Switches between **Lido Night** (dark slate cockpit EFB theme) and **Lido Day** (authentic paper chart theme).

---

## 8. Live Traffic & Multi-Column Stand Status

At the bottom of the left sidebar, the **TRAFFIC & STAND STATUS** card monitors airport stand occupancy in real time:
- **Multi-Column Responsive Grid**: Occupied stands are stacked in a clean multi-column grid (**at least 3 columns wide**, automatically expanding to **4, 5, or 6+ columns** as you widen the left panel with the splitter).
- **Internal Scrollbar**: When busy hubs have dozens of occupied stands on VATSIM/IVAO, an internal vertical scrollbar lets you scroll smoothly through all occupied gates with the mouse wheel without ever overflowing the window.
- **Network Tags**:
  - **`(VATSIM)`** — Occupied by a live pilot on VATSIM.
  - **`(IVAO)`** — Occupied by a live pilot on IVAO.
  - **`(AI/LIVE)`** — Occupied by an MSFS SimConnect AI or multiplayer aircraft.

---

## 9. MSFS In-Game Panel (`GATEFINDER V2.0.4`) & VR Mode

Once the panel is installed via Settings:
1. Load a flight in **MSFS 2020** or **MSFS 2024**.
2. Open the **MSFS Top Toolbar** and click the **GateFinder** icon.
3. The panel window title bar displays **`GATEFINDER V2.0.4`**, matching your desktop version.
4. **VR & Cockpit Ergonomics**:
   - Features the same resizable left sidebar splitter, full-airport default centering, GSX Pro confirmation toast, and interactive Lido vector map as the desktop app.
   - All top-bar controls and **ATC Taxi Clearance** pills feature enlarged hitboxes for effortless clicking with a VR controller or head-tracked mouse cursor.

---

## 10. External Tablet & Smartphone Web EFB (QR Code)

You can use GateFinder V2.0.4 on an external **iPad, Android tablet, or smartphone** over your local Wi-Fi network:
1. Open **Settings** in the GateFinder desktop app and click **Open Tablet / Web EFB (QR Code)** (or scan the QR code displayed in the modal).
2. Your tablet or phone browser will open `http://<YOUR_PC_LAN_IP>:8420/efb` with the full interactive GateFinder V2.0.4 Lido EFB synchronized in real time.
3. **Important Note for VPN Users (ProtonVPN, NordVPN, etc.)**:
   - GateFinder automatically detects your PC's physical Wi-Fi/Ethernet LAN IP (`192.168.x.x`) even if a VPN is running on your PC.
   - However, if a **VPN app is active on your tablet or smartphone**, the mobile VPN may block local Wi-Fi (`192.168.x.x`) traffic. Either enable **"Allow LAN connections"** (Split Tunneling) in your mobile VPN settings or disconnect the VPN on your tablet/phone while using the Web EFB.

---

## 11. Settings Reference

### 1. Dispatch & Stand Selection
| Option | Description |
| :--- | :--- |
| **SimBrief Username or Pilot ID** | Your SimBrief Pilot ID or username used to download your latest OFP. Use **Test Connection** to validate. |
| **Auto-fetch latest SimBrief OFP on startup** | Automatically imports your active SimBrief flight plan as soon as GateFinder launches. |
| **Prompt to keep arrival or live MSFS parked stand on Turnaround** | Asks whether to keep your current physical stand or pick a new one when importing an OFP while already parked at an airport. |
| **Force Cargo Mode** | Forces GateFinder to prioritize cargo ramps/freight stands regardless of aircraft passenger configuration. |

### 2. ATC, GSX Pro & Online Traffic
| Option | Description |
| :--- | :--- |
| **Auto-sync gate & active runway assigned by AI ATC** | Automatically syncs runway, taxi route, and gate assignments from **BeyondATC** and **SayIntentions.AI**. |
| **Enable GSX Pro Arrival Auto-Sync** | Automatically arms and communicates your selected gate to GSX Pro so marshallers and jetways are pre-configured. |
| **Filter occupied stands on VATSIM & IVAO** | Excludes stands currently occupied by online pilots on VATSIM/IVAO during automatic gate assignment. |
| **Auto-clear MSFS AI traffic at assigned stands** | Automatically despawns conflicting MSFS AI traffic parked at your assigned departure or arrival gate. |
| **SayIntentions.AI SAPI Key** | Optional manual API key override (leave blank to auto-detect directly from your local SayIntentions.AI logs). |

### 3. Performance & System
| Option | Description |
| :--- | :--- |
| **Auto-Start GateFinder silently when MSFS launches** | Registers GateFinder in MSFS `exe.xml` so the background service starts automatically with the simulator. |
| **Auto-suspend Lido chart rendering while airborne** | Pauses high-frequency map redraws during cruise flight to guarantee zero CPU/GPU impact while airborne, automatically resuming at touchdown. |

### 4. MSFS Paths & In-Game Toolbar Panel
| Option | Description |
| :--- | :--- |
| **GSX Profile Path** | Path to your FSDreamTeam GSX `.ini` airport profiles (`%APPDATA%\Virtuali\GSX\MSFS`). Click **Auto-Detect** to locate automatically. |
| **Primary Community Folder** | Path to your primary MSFS `Community` folder. |
| **Secondary / MSFS 2024 Folder** | Optional path to a second `Community` folder (if you have both MSFS 2020 and MSFS 2024 installed). |
| **MSFS In-Game Toolbar Panel** | Click **Install Panel** or **Uninstall Panel** to add or remove `gatefinder-ingame-panel` (`GATEFINDER V2.0.4`) from your Community folder(s). |
| **Uninstall GateFinder** *(Red Button)* | Completely removes the MSFS In-Game Panel from all Community folders, cleans up `exe.xml` auto-start entries, and prepares GateFinder for removal. |

---

## 12. Troubleshooting & Uninstallation

- **In-Game Panel shows "GateFinder is not running"**:
  - Ensure `GateFinder.exe` is running on your PC (check your Windows system tray). If you enable **Auto-Start GateFinder silently when MSFS launches** in Settings, it will launch automatically with MSFS.
- **Tablet / Smartphone QR Code Web EFB does not load**:
  - Make sure your tablet/phone is connected to the same local network as your PC, and check that any VPN on your tablet/phone (such as ProtonVPN) is either disabled or has **"Allow LAN connections"** enabled.
- **Uninstalling GateFinder**:
  - Open **Settings** and click the red **Uninstall GateFinder** button at the bottom-right (or run `Uninstall_GateFinder.bat`). This cleanly removes the `gatefinder-ingame-panel` package from all MSFS Community folders and removes the `exe.xml` auto-start hook.
