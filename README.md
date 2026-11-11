GateFinder V2.0.6 for MSFS 2024 / MSFS 2020
===========================================

English
-------
Welcome to **GateFinder V2.0.6**! GateFinder is an all-in-one airport surface navigation, intelligent stand assignment, GSX Pro integration, and AI ATC ground companion for **Microsoft Flight Simulator 2020 & 2024**. It runs as a standalone **Desktop App**, a native **MSFS 2024 Tablet EFB App**, a native **Fenix A319/A320/A321 Cockpit EFB App**, an **MSFS In-Game Toolbar Panel (`GATEFINDER V2.0.6`)** (2D & VR), and a **Live Web EFB** for tablets and smartphones via QR code.

### What's New in V2.0.6:
- **Intelligent Aircraft Type Normalization:** Eliminates false SimBrief vs. MSFS aircraft mismatch popups by normalizing manufacturer prefixes, livery tags (e.g., `BOEING 738 (AUA)` ↔ `B738`), and Neo/MAX airframe families.
- **Cockpit / VR Desktop Popup Suppression Mode:** Optional setting (`Suppress desktop popups (Cockpit / VR mode)`) that replaces intrusive full-screen desktop modals with a discreet inline bar and in-sim EFB resolution to protect VR and home-cockpit immersion.
- **Global OSM + Native MSFS BGL Geometry Fallback:** Automatically repairs unclosed OSM apron polygons, merges native MSFS BGL runway/taxiway/parking networks when OSM data is sparse, and synthesizes bounding aprons globally for any airport worldwide (such as `LICC`) without manual patches.
- **Built-in Automatic GitHub Updater:** Integrated one-click GitHub Releases auto-updater right in the main chart bar—downloads updates, syncs your MSFS In-Game/EFB package, preserves user settings, and restarts automatically.
- **World's 50 Largest Airports Pre-Cached (`geom_v=4`) & High-Speed Moving Map:** Pre-cached full-extent vector surface charts for the 50 largest airports worldwide, localized GDI route rendering, `0.002°` spatial-grid A* routing, and clean MSFS `RECV_QUIT` shutdown.
- **Native MSFS 2024 EFB, Fenix A320 Family EFB, Interactive Taxiway Builder & Multi-Category Dispatch:** Full support for MSFS 2024 & Fenix cockpit tablets, interactive VATSIM/IVAO/VR taxiway route clicking, **SayIntentions.AI** & **BeyondATC** live sync, and automatic **Airline, Cargo (`CAR`), Military (`MIL`), Business Jet (`BIZ`) & GA** stand dispatch.

### Quick Start:
1. Launch `GateFinder.exe`.
2. Open **Settings**, enter your **SimBrief Username or Pilot ID**, verify your **GSX Profile Path** and **MSFS Community Folder**, and click **Install Panel**.
3. Click **Import SimBrief** (or fly directly in MSFS) to load your flight, gates, and Lido taxi charts!
