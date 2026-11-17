GateFinder V2.1.0 for MSFS 2024 / MSFS 2020
===========================================

English
-------
Welcome to **GateFinder V2.1.0**! GateFinder is an all-in-one airport surface navigation, intelligent stand assignment, GSX Pro integration, and AI ATC ground companion for **Microsoft Flight Simulator 2020 & 2024**. It runs as a standalone **Desktop App**, a native **MSFS 2024 Tablet EFB App**, a native **Fenix A319/A320/A321 Cockpit EFB App**, an **MSFS In-Game Toolbar Panel (`GATEFINDER V2.1.0`)** (2D & VR), and a **Live Web EFB** for tablets and smartphones via QR code.

### What's New in V2.1.0:
- **MSFS In-Game Panel / EFB Arrival Sidebar Fix, Complete Pier/Taxilane Lead-Ins (`EHAM` & `ZGGG`) & Clearance Pill Wrapping:** Fixes the missing left sidebar on the `ARRIVAL` tab in the MSFS In-Game Panel/EFB, restores all pier feeder cul-de-sac taxiways & curved `parking_position` stand lead-in taxilanes (`A20`, `A3`, `A4W`, `A10`–`A17`, `S`/`S4`/`S10`, `Y` at `EHAM`), resolves hybrid `aeroway=gate` + unnamed tarmac stands (**447 stands across T1/T2/T3 & 5 runways at `ZGGG`**), and prevents sidebar taxi clearance pill clipping.
- **Headless GSX Pro Reposition (`Couatl Remote API v2`) & Zero-Reset SimVars Ground Warp:** Instantaneous stand warp with or without GSX Pro (zero external Couatl desktop popups, zero `DATA_INITPOSITION` flight reload) plus Per-Monitor High-DPI / 4K scaling across all map labels and Settings tooltips.
- **GSX Pro Neighboring-Airport Arrival Sync Guard & SayIntentions.AI Arrival Gate Lock:** Verifies Couatl's active `[GSX] onEnteredAirport` state on touchdown so neighboring airfields on short final (e.g., `HEAZ` next to `HECA` `RWY 05C`) never swallow arrival GSX stand activation, parses terminal-prefixed taxi clearances (`"Taxi to Terminal 1 Gate 10..."`), and prevents stale SayIntentions `flight.json` `assigned_gate` entries from overriding your cleared arrival stand or interrupting GSX deboarding.
- **Clickable Arrival Airport Switcher & 1-Click SimBrief Alternate Diversion:** Click the **Arrival ICAO pill** or **Arrival Airport title** on Desktop or any Cockpit/Web EFB to set or change your destination airport on the fly (including non-SimBrief VFR/MCDU flights via live SimConnect aircraft telemetry), or switch in 1 click to your **`SimBrief Alternate`** during an in-flight diversion.
- **`Auto-fetch latest SimBrief OFP on startup` Fix:** Strictly honors disabling `Auto-fetch latest SimBrief OFP on startup` across app startup, Settings navigation, and live SimConnect tarmac detection.
- **Worldwide Dead-End Taxiway Pruning, Apron Loop-Free A* Routing & Dynamic Runway QFU Pills:** Removes dangling dead-end OSM taxiway stubs globally (e.g., `EGCC`, `EBBR`), prevents A* from detouring through drive-through stand bays as roundabouts (`_strip_route_loops` + SayIntentions unnamed-apron projection fix, e.g., `LDDU`), keeps runway QFU pills dynamically clamped inside the viewport at any zoom level, enlarges airline stand badges, and adds `GWI` (`Germanwings`) sister fallback onto `EWG` (`Eurowings`).
- **Automatic "What's New" Changelog Popup:** Automatically presents release notes once after each version update (respecting Cockpit/VR popup suppression), with a **`Changelog`** button in Settings to review version history anytime.
- **Intelligent Aircraft Type Normalization, Cockpit/VR Popup Suppression & Global OSM+BGL Fallback:** Eliminates false SimBrief vs. MSFS aircraft mismatches (`default_mismatch_action`), offers `Suppress desktop popups (Cockpit / VR mode)`, and guarantees complete airport surface geometry worldwide.
- **Built-in Automatic GitHub Updater:** Integrated one-click GitHub Releases auto-updater right in the main chart bar—downloads updates, syncs your MSFS In-Game/EFB package, preserves user settings, and restarts automatically.
- **World's 50 Largest Airports Pre-Cached (`geom_v=4`) & High-Speed Moving Map:** Pre-cached full-extent vector surface charts for the 50 largest airports worldwide, localized GDI route rendering, `0.002°` spatial-grid A* routing, and clean MSFS `RECV_QUIT` shutdown.
- **Native MSFS 2024 EFB, Fenix A320 Family EFB, Interactive Taxiway Builder & Multi-Category Dispatch:** Full support for MSFS 2024 & Fenix cockpit tablets, interactive VATSIM/IVAO/VR taxiway route clicking, **SayIntentions.AI** & **BeyondATC** live sync, and automatic **Airline, Cargo (`CAR`), Military (`MIL`), Business Jet (`BIZ`) & GA** stand dispatch.

### Quick Start:
1. Launch `GateFinder.exe`.
2. Open **Settings**, enter your **SimBrief Username or Pilot ID**, verify your **GSX Profile Path** and **MSFS Community Folder**, and click **Install Panel**.
3. Click **Import SimBrief** (or fly directly in MSFS) to load your flight, gates, and Lido taxi charts!
