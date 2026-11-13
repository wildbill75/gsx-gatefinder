# GateFinder — Référentiel Complet de Développement & d'Architecture (V2.0.0 → V2.0.8)

> **Usage prévu de ce document :** Ce fichier sert de **base de connaissances exhaustive (System Context)** à fournir à **Gemini** afin qu'il dispose de 100 % de l'historique fonctionnel, de l'architecture du code, des API internes, des conventions UI/UX et des contraintes techniques de **GateFinder** pour rédiger des prompts chirurgicaux destinés à l'agent de code (**Antigravity**).

---

## 1. Identité du Projet & Écosystème d'Exécution

- **Nom :** GateFinder (édité par *Sidestick Priority* — dépôt GitHub : `wildbill75/gsx-gatefinder`)
- **Version actuelle en production :** `V2.0.8` (`V2.0.5` étant la dernière version uploadée manuellement sur `flightsim.to` ; `V2.0.6+` sont distribuées automatiquement via l'Auto-Updater GitHub intégré).
- **Simulateurs cibles :** Microsoft Flight Simulator 2020 & Microsoft Flight Simulator 2024 (Store & Steam, 2D & VR).
- **Rôle :** Compagnon tout-en-un d'assignation intelligente de portes/postes de stationnement, de cartographie vectorielle sol type Lido (Moving Map), de routage taxiway A* temps réel, et de synchronisation bidirectionnelle **SimBrief + GSX Pro + BeyondATC + SayIntentions.AI + VATSIM/IVAO + SimConnect**.
- **5 Surfaces d'Affichage Synchronisées en Temps Réel** (alimentées par le même moteur Python local sur le port HTTP `8420`) :
  1. **Application Desktop Windows (`GateFinder.exe`)** : CustomTkinter + Canvas vectoriel GDI haute performance (`src/gui.py`), icône System Tray (`pystray`), support 4K / High-DPI (200 %–250 %+).
  2. **MSFS In-Game Toolbar Panel (`GATEFINDER V2.0.8`)** : Panneau barre d'outils natif MSFS 2020 & 2024 (2D et VR) via CoherentGT (`GateFinderPanel.html` + `GateFinderPanel.js`).
  3. **Application Native Tablette EFB MSFS 2024** : App dédiée intégrée directement dans l'EFB natif de MSFS 2024 (`GateFinderEfbApp.js` → `GateFinderEfbFrame.html`).
  4. **Application Native Cockpit EFB Fenix A320 Series (`A319` / `A320` / `A321`)** : App intégrée sur l'écran d'accueil des tablettes Captain et First Officer du Fenix (`EfbHost_Captain.html`, `EfbHost_FO.html` → `GateFinderFenixFrame.html`).
  5. **Web EFB Externe (iPad / Tablette Android / Smartphone)** : Accessible en Wi-Fi local via QR code (`http://<LAN_IP>:8420/` avec modes adaptatifs `Phone`, `Tablet`, `PC`).

---

## 2. Historique Complet du Développement depuis la Version 2.0

### Phase A — Socle V2.0.0 à V2.0.3 (Refonte Architecturale V2)
Passage de l'architecture V1 (simples cartes/tuiles statiques) à une suite EFB vectorielle temps réel complète :
1. **Moteur Cartographique Vectoriel Lido (`LidoVectorChart` dans `src/gui.py` & Canvas HTML5 dans `GateFinderPanel.js`)** :
   - Rendu vectoriel complet des pistes, seuils, taxiways, tabliers (aprons), bâtiments terminaux, points d'arrêt et badges de portes orientés.
   - Double thème **Lido Night** (fond sombre `#0B1120` cockpit) et **Lido Day** (charte papier claire).
   - Cadrage initial centré sur l'aéroport complet (`Route`) ou zoom serré sur le poste assigné (`Gate`), panoramique souris/tactile et zoom molette/pincement.
2. **Routeur Sol A\* & Géométrie OSM/BGL (`TaxiRouter` dans `src/taxi_router.py`)** :
   - Extraction, fusion et mise en cache locale (`taxi_charts_cache.json`) de la géométrie aéroportuaire OpenStreetMap (Overpass) enrichie par les données scènes MSFS BGL (`default_airports_db.bin` + scan `Community`) et profils `.ini` GSX Pro.
   - Calcul d'itinéraire sol optimal A\* du stand au seuil de piste (Départ) et de la sortie de piste rapide au stand (Arrivée), avec détection automatique de la sortie de piste empruntée après l'atterrissage (`locked_arrival_exit` / `arr_vacated_runway`).
3. **Hub d'Interopérabilité Temps Réel (`InteroperabilityHub` dans `src/interoperability_hub.py`)** :
   - Machine à états (`HubState` / `GateDecision` / `GateSource`) arbitrant les priorités entre GateFinder, **BeyondATC**, **SayIntentions.AI**, **GSX Pro**, **VATSIM/IVAO** et la sélection manuelle pilote.
   - Synchronisation automatique avec **GSX Pro** (armement automatique de la porte d'arrivée/départ sans manipulation fastidieuse du menu GSX) + toast de confirmation sur la carte.
   - Filtrage des postes occupés sur **VATSIM & IVAO** (avec revérification automatique avant le Top of Descent à `180 NM` et en approche) et suppression automatique du trafic IA SimConnect MSFS sur le poste assigné (`auto_clear_ai`).
4. **Identité Visuelle Camaïeu & Conformité (`src/backend.py`, `src/legal_and_diagnostics.py`)** :
   - Extraction des logos compagnies (`cache/airline_logos/`) et génération automatique d'une palette camaïeu (`s1` à `s4` + `accent`) dérivée des couleurs de la compagnie aérienne active.
   - Interface 100 % *borderless* (`border_width=0`), coins arrondis cohérents, séparateur latéral redimensionnable (`sidebar_width` persisté), hibernation automatique du rendu carte en croisière (`hibernate_map_in_flight`), et module légal/diagnostic (`EULA`, rapports de crash locaux/opt-in).

---

### Phase B — Version 2.0.4 (Intégrations Tablettes Cockpit, Multi-Aviation & Contrôle Taxi Interactif)
1. **Intégration Native Tablette EFB MSFS 2024** :
   - Ajout de l'application native `GateFinderEfbApp` dans `gatefinder-ingame-panel`, directement accessible depuis l'icône GateFinder de la tablette EFB MSFS 2024 avec mise à l'échelle adaptée cockpit/VR.
2. **Intégration Native Cockpit EFB Fenix (`A319` / `A320` / `A321`)** :
   - Injection propre dans `EfbHost_Captain.html` et `EfbHost_FO.html` permettant d'ouvrir GateFinder depuis l'écran d'accueil des deux tablettes Fenix (respectant le bouton Home et l'état d'alimentation de l'EFB), contrôlable via un switch dédié dans `Settings` (`fenix_efb_enabled`).
3. **Éditeur Interactif de Route Taxiway (Mode VATSIM / IVAO / Bloc-Notes Visuel VR)** :
   - Clic direct sur n'importe quel badge de taxiway sur la carte Lido (ou sur les pastilles de la colonne de gauche) pour construire, basculer ou modifier son autorisation de roulage à la volée (`set_custom_taxi_via`, boutons `Auto` et `Clear`), recalculant instantanément le tracé vert A\*.
4. **Synchronisation Complète SayIntentions.AI & Améliorations BeyondATC** :
   - Parsing complet des instructions `"taxi via ..."` de SayIntentions.AI, portes pré-assignées, pistes actives, trafic VFR/CTAF auto-annoncé, et auto-détection de la clé SAPI locale (`%LOCALAPPDATA%\SayIntentionsAI\flight.json`).
   - Détection précoce de la porte d'arrivée BeyondATC et synchronisation immédiate si l'utilisateur change manuellement de porte dans le menu déroulant BeyondATC.
5. **Dispatch Multi-Catégories Automatique (5 Catégories d'Aviation)** :
   - **Passagers (`PAX`)** : Règles terminaux réels (`airlines_terminals.json`), profils GSX `.ini`, codes compagnies BGL et marges d'envergure exactes.
   - **Cargo Automatique (`CAR`)** : Détection de 60+ compagnies cargo (`FDX`, `UPS`, `CLX`, `DHK`, `GEC`, `BOX`, `GTI`, `CKS`, `SQC`, etc.), indicatifs ATC parlés et avions cargos (`B77F`, `B748F`, `MD11F`, `BCF`, `P2F`, `BDSF`) → assignation automatique des rampes Cargo sans avoir à cocher *Force Cargo Mode*.
   - **Militaire (`MIL`)** : Détection des chasseurs/entraîneurs (`Rafale`, `Mirage 2000`, `Eurofighter`, `F-16`, `F/A-18`, `F-35`, `PC-21`, `Alpha Jet`), transports/ravitailleurs lourds (`A400M`, `C-17`, `C-130J`, `A330 MRTT`, `KC-135`, `KC-46`, `AWACS`) et indicatifs (`COTAM`/`FAF`, `RCH`, `RRR`/`ASCOT`, `GAF`, `BAF`). Priorité 1 : postes `Mil` ; Priorité 2 (fallback aéroport civil) : rampe Cargo/Heavy si envergure `>= 24 m`, rampe GA/FBO si `< 24 m`.
   - **Aviation d'Affaires (`BIZ`) & Aviation Générale (`GA`)** : Détection des jets d'affaires (`Falcon`, `Global`, `Challenger`, `Gulfstream`, `Citation`, `Phenom`, `PC-24`) et avions légers/turboprops (`C172`, `TBM9`, `PC12`, `DA62`, `SR22`, `King Air`) → priorité aux rampes FBO / GA adaptées à l'envergure.
6. **Mode Vol Direct Live MSFS (Sans SimBrief) & Warp SimConnect Natif** :
   - Possibilité de voler en VFR/IFR libre sans OFP SimBrief (`load_live_msfs_flight`), incluant les petits aérodromes VFR via fallback OpenStreetMap.
   - **Warp SimConnect natif** : La fonction *Reposition Aircraft Here (Warp)* utilise GSX Pro s'il tourne, ou bascule automatiquement sur une téléportation + alignement cap direct via `SimConnect` natif si GSX Pro est absent ou inactif.
7. **Protection Multi-Postes MARS, `Follow + Hdg Up` & Ergonomie 4K** :
   - Résolution automatique des sous-postes **MARS** selon l'envergure (ex. `A 4` gros-porteur vs `A 41` monocouloir) et nettoyage IA des postes adjacents chevauchants (`mars_overlap_protection`).
   - Centrage géométrique exact de l'avion en `Follow + Hdg Up`, Smart Zoom radial invariant au cap (zéro saut de zoom en virage à 90°), sélecteur de fluidité (`5 Hz` / `10 Hz` / `20 Hz`), désambiguïsation des sorties rapides proches à l'atterrissage.
   - Support 4K / DPI Windows extrême (200 %–250 %+) avec vue `Settings` entièrement scrollable à la molette, et option `Auto-Quit GateFinder automatically when MSFS closes`.

---

### Phase C — Version 2.0.5 (Optimisation Mega-Hubs, 50 Plus Grands Aéroports, Auto-Updater GitHub & Modale Mismatch)
1. **Audit, Réparation & Pré-Cache Hors-Ligne des 50 Plus Grands Aéroports Mondiaux (`geom_v=4`)** :
   - Vérification et reconstruction intégrale des géométries vectorielles (toutes les pistes sur toute leur longueur, satellites distants, taxiways périphériques, empreintes terminaux) pour les 50 plus vastes aéroports du monde (`OEDF`, `OMDW`, `KDEN`, `OEJN`, `WMKK`, `KATL`, `LTFM`, `KDFW`, `OERK`, `KMCO`, `KIAD`, `ZBAD`, `KIAH`, `KMCI`, `ZSPD`, `HECA`, `VTBS`, `LFPG`, `KSLC`, `LEMD`, `OMDB`, `KORD`, `LIRF`, `EHAM`, `CYMX`, `KMEM`, `UUDD`, `OTHH`, `EDDF`, `RJTT`, `ESSA`, `KMSP`, `CYYZ`, `YSSY`, `YBBN`, `VIDP`, `KDTW`, `KSFO`, `ZBAA`, `KCLT`, `KJFK`, `WSSS`, `WMKP`, `LEBL`, `EDDM`, `FAOR`, `RCTP`, `RPLL`, `VHHH`, `LOWW`, `LSZH`, `LFPO`, `RKSI`), livrées prêtes à l'emploi hors-ligne dans `taxi_charts_cache.json`.
2. **Refonte Majeure des Performances Desktop & Moving-Map (Zéro Freeze / Zéro Saccade)** :
   - **Rendu GDI localisé sur Tkinter (`src/gui.py`)** : Séparation de la route verte en une queue statique et un segment dynamique court au nez de l'avion (`~40x40 px`), évitant à Windows GDI de repeindre tout le canvas à chaque tick (`~38x` plus rapide sur `EDDF`/`LFPG`/`KORD`).
   - **Indexation spatiale `0.002°` & Hystérésis A\* (`src/taxi_router.py`)** : Grille spatiale rapide pour la recherche de nœuds, arêtes pré-indexées, hystérésis de `28 m` sur les grands tabliers, mémoïsation des routes à l'arrêt/roulage et pré-chauffage asynchrone du graphe dès l'import SimBrief.
   - **Résolution GPS Locale Instantanée & SimConnect Non-Bloquant (`src/backend.py`)** : Détection locale `< 0.5 ms` des pistes éloignées (ex. `EHAM` `18R` Polderbaan) sans requête HTTP Overpass bloquante, stabilisation anti-jitter à l'arrêt (`0 %` CPU au parking) et drainage borné non-bloquant des paquets SimConnect.
3. **Fermeture Propre de MSFS 2020 / 2024 (`RECV_QUIT`)** :
   - Interception active du paquet `SIMCONNECT_RECV_ID_QUIT` et fermeture immédiate du handle natif `SimConnect.dll` dès que le simulateur se ferme, empêchant MSFS ou Gaming Services de rester bloqués en tâche de fond.
4. **Suppression de la Promo & Auto-Updater GitHub 1-Clic Intégré (`src/gui.py`, `src/main.py`)** :
   - Suppression complète de l'ancienne bannière promo dans la fenêtre principale et dans le menu System Tray.
   - Remplacement dans `LidoVectorChart.header_bar` par un bouton **Auto-Updater GitHub** sobre et sans icône interrogeant `https://api.github.com/repos/wildbill75/gsx-gatefinder/releases/latest` :
     - À jour : **`No update available`** en gris discret (`fg_color="#232730"`, `text_color="#64748B"`).
     - Mise à jour disponible : **`Update V2.X.X available`** en bleu (`fg_color="#0A86C2"`, `text_color="#FFFFFF"`).
     - Au clic : téléchargement streamé avec progression (`Updating XX%...`), contrôle d'intégrité `.zip`, exclusion/suppression stricte de `settings.json` et `last_flight_session.json` du staging, mise à jour automatique de `gatefinder-ingame-panel` dans `Community` et `Community2024`, remplacement du binaire verrouillé via un script détaché `apply_update.bat` (boucle retry jusqu'à libération du bootloader PyInstaller `--onefile`), et relance automatique de `GateFinder.exe`.
5. **Correction Définitive du Faux Positif Cargo (`WF`) & Modale Épurée de Mismatch SimBrief / MSFS** :
   - **Fix Cargo (`is_freighter_aircraft` & `get_live_msfs_aircraft_profile`)** : Suppression de la règle générique `endswith("F")` qui classait à tort `FENIXA320 CFM WF` (*Wingtip Fence*) en Cargo (`CAR`). Ajout de la souscription SimVar optionnelle MSFS 2024 `LIVERY NAME` (`def_id = 852`, isolée dans un `try/except` pour compatibilité totale MSFS 2020), extraction intelligente de la compagnie/immatriculation depuis la livrée/titre (ex. `Brussels Airlines` → `BEL`), et fallback garanti **`PAX - Commercial Passenger`** (jamais `CAR`) pour tout avion de ligne passagers sans livrée reconnue.
   - **Modale Mismatch SimBrief / MSFS (`_show_msfs_simbrief_mismatch_modal` dans `src/gui.py` + `syncSimbriefMismatchModal` dans `GateFinderPanel.js`)** : Dès que l'avion spawné et/ou l'aéroport de départ dans MSFS ne correspondent pas à l'OFP SimBrief (`check_simbrief_vs_msfs_mismatch`), une modale minimaliste sans bordure ni icône s'affiche sur PC **et** dans l'EFB/In-Game Panel avec 3 choix synchronisés :
     1. **`Open SimBrief`** → ouvre SimBrief Dispatch dans le navigateur et scrute automatiquement l'apparition d'un nouvel OFP toutes les `3.5 s` (le bouton devient **`Import New OFP`**).
     2. **`Use MSFS Aircraft`** → ignore SimBrief et charge directement l'avion et l'aéroport MSFS en mode passager/compagnie (avec champ optionnel `Arrival ICAO`).
     3. **`Keep SimBrief OFP`** → conserve/importe l'OFP SimBrief malgré la différence d'avion ou d'aéroport.

---

### Phase D — Versions 2.0.6 & 2.0.7 (Normalisation Avion Intelligente, Préférence Mismatch Persistante, Correctif `dep == arr`, Mode Cockpit/VR Sans Popups & Fallback Géométrique Global OSM + BGL)
1. **Normalisation Intelligente des Types Avions SimBrief ↔ MSFS & Préférence Mismatch par Défaut (`src/backend.py`, `src/config.py`, `src/gui.py`, `GateFinderPanel.js`)** :
   - Suppression des faux positifs de mismatch entre les codes ICAO SimBrief (ex. `B738`, `A20N`) et les chaînes télémétriques MSFS brutes (ex. `BOEING 738 (AUA)`, `737-8AS (RYR)`, `AIRBUS 320-214`, `FENIXA320 CFM WF`) par nettoyage des suffixes livrées entre parenthèses, retrait des préfixes constructeurs, support des codes clients alphanumériques Boeing/Airbus et équivalence des sous-familles Neo/MAX/motorisations.
   - Ajout de la préférence persistante `default_mismatch_action` (`"ask"` ou `"use_msfs"`) via la case `Make this default choice for 'Use MSFS Aircraft'` dans la modale mismatch (Desktop & EFB) et le switch `Auto-select 'Use MSFS Aircraft' on SimBrief mismatch` dans `Settings` pour appliquer automatiquement l'avion MSFS en tâche de fond sans ouvrir la modale.
   - Correctif PyInstaller `--onefile` sur `start_github_self_update` (`PYTHONHOME`/`PYTHONPATH` nettoyés + `PYINSTALLER_RESET_ENVIRONMENT=1` dans `apply_update.bat`) empêchant l'héritage de l'ancien dossier temporaire `_MEIxxxxx` au redémarrage post-update.
2. **Validation Stricte de l'Aéroport d'Arrivée SimBrief (`dep == arr` Fix dans `src/backend.py`)** :
   - Parsing unifié JSON + XML (`_parse_simbrief_payload` assainissant les balises XML vides `{}`) et validation croisée `_extract_validated_simbrief_route_icaos` (vérification `origin != destination`, extraction de secours `-ADES` depuis le texte FPL ATC ICAO, conservation de la destination active/session et `resolve_default_live_dest`) empêchant tout auto-import ou action `Use MSFS Aircraft` sans destination d'écraser l'arrivée avec l'aéroport de départ (`dep == arr`).
3. **Option de Suppression Complète des Popups Desktop en Cockpit / VR (`suppress_popups_in_cockpit` dans `src/config.py`, `src/gui.py`, `src/backend.py`, `GateFinderPanel.js`)** :
   - Réglage persistant `Suppress desktop popups (Cockpit / VR mode)` (`False` par défaut). Lorsqu'il est activé, aucune modale bloquante (**Live Stand Selection**, **Turnaround Stand**, **SimBrief Mismatch**, ni splash de rechargement live) ne s'ouvre par-dessus MSFS/Windows : une barre d'action discrète sans icône apparaît dans le bandeau Desktop tandis que l'EFB / In-Game Panel cockpit conserve la résolution interactive complète.
4. **Fallback Géométrique Global OSM + MSFS BGL Natif (`src/taxi_router.py`, `src/backend.py`, `GateFinderPanel.js`)** :
   - Fin des correctifs aéroport par aéroport (ex. `LICC` Catane) grâce à un pipeline global en 3 niveaux : (a) couture topologique et fermeture automatique des ways/multipolygones OSM d'apron ouverts ou tronqués + rendu Canvas `beginPath()` par anneau, (b) fusion automatique du réseau natif MSFS BGL (`runways`, `taxiways`, `parkings`, `aprons` via `bgl_geometry_provider`) et pontage des îlots de stands déconnectés (`> 185 m`) dès qu'OSM est incomplet, et (c) génération automatique d'enveloppes d'apron orientées autour des stands/bretelles orphelins + support des pistes à remontée (*backtrack*).

---

### Phase E — Version 2.0.8 (Changement d'Arrivée / Déroutement Alternate SimBrief 1-Clic, Correctif `auto_fetch`, Élagage des Taxiways en Impasse & Pastilles QFU Dynamiques)
1. **Changement d'Aéroport d'Arrivée Cliquable & Déroutement Alternate SimBrief en 1 Clic (`src/backend.py`, `src/gui.py`, `GateFinderPanel.js`)** :
   - Clic direct sur la pastille ICAO d'arrivée (`ARRIVAL`) ou sur le titre d'aéroport d'arrivée de la sidebar (Desktop, In-Game Panel, EFB MSFS 2024, EFB Fenix et Web EFB) + bouton `Set Arrival` sur l'écran d'attente EFB : ouvre la modale sans bordure `CHANGE ARRIVAL AIRPORT` (`change_arrival_airport` / `GET /api/set_arrival?icao=XXXX`).
   - Support complet avec ou sans SimBrief (VFR / plan de vol saisi au MCDU via la télémétrie avion SimConnect live) et boutons 1-clic **`SimBrief Alternate: XXXX`** (`_extract_simbrief_alternates`) + **`Scheduled Arrival: YYYY`** en conservant l'`ofp_id` initial pour éviter tout faux prompt de nouveau plan de vol en croisière.
2. **Respect Strict de `Auto-fetch latest SimBrief OFP on startup` (`src/gui.py`, `src/backend.py`)** :
   - Correction des 3 chemins qui forçaient encore le téléchargement de l'OFP SimBrief lorsque `auto_fetch = False` (`GUIApp.__init__` via `os.path.getmtime`, retour de `Settings` dans `show_main_view`, et peek SimBrief dans `check_simbrief_vs_msfs_mismatch` / `/api/resolve_mismatch`).
3. **Élagage Topologique Global des Taxiways en Impasse & Lisibilité Carte (`src/taxi_router.py`, `src/gui.py`, `GateFinderPanel.js`)** :
   - `_prune_dangling_taxiway_stubs` (`_deadend_pruned_v = 2`) éliminant les impasses OSM et points d'arrêt orphelins dans l'herbe (ex. `EGCC`, `EBBR`) tout en préservant les peignes de parkings parallèles et sorties d'aprons ; pastilles QFU de pistes glissant dynamiquement le long des bords de l'écran quel que soit le zoom (au repos comme au pan) et badges logos compagnies agrandis.

---

## 3. Architecture Technique & Cartographie du Codebase

### 3.1 Modules Python (`D:\GateFinder\src\`)

| Fichier | Lignes approx. | Responsabilité Principale & Classes / Fonctions Clés |
| :--- | :---: | :--- |
| `src/main.py` | ~190 | Point d'entrée, mutex d'instance unique, exemption loopback UWP (`CheckNetIsolation`), System Tray `pystray` (`setup_tray`), mode `--uninstall`, lancement `GateFinderBackend` + `GUIApp`. |
| `src/config.py` | ~230 | Classe `Config`, chargement/sauvegarde de `settings.json`, auto-détection `UserCfg.opt` (`Community` & `Community2024`), auto-détection clé SAPI SayIntentions, migrations automatiques et nettoyage de chemins étrangers. |
| `src/backend.py` | ~11 230 | Cœur métier `GateFinderBackend`, `SimConnectManager` (télémétrie avion, trafic IA, éviction IA, Warp SimConnect, `RECV_QUIT`), dispatch des portes (PAX/CAR/MIL/BIZ/GA, MARS), parsing BGL/GSX `.ini`/SimBrief XML, détection mismatch SimBrief/MSFS, extraction logos/camaïeu, et serveur HTTP local `APIHandler` (`port 8420`). |
| `src/gui.py` | ~8 750 | Application Desktop `GUIApp(ctk.CTk)` + composant carte `LidoVectorChart(ctk.CTkFrame)`. Rendu vectoriel GDI optimisé, barre d'outils carte + Auto-Updater GitHub, sidebar redimensionnable, modales (Sélecteur de stand, Mismatch SimBrief/MSFS, Live Stand, ATC Override, QR Code Web EFB, Settings scrollable 4K). |
| `src/taxi_router.py` | ~4 050 | Classe `TaxiRouter` : requêtes/cache géométrique Overpass OSM (`taxi_charts_cache.json`), assainissement géométrique (`geom_v=4`), graphe de roulage indexé spatialement (`0.002°`), routage A\* départ/arrivée, routes personnalisées (`via`), détection live de sortie de piste. |
| `src/interoperability_hub.py` | ~4 660 | Classe `InteroperabilityHub` : intégration temps réel **BeyondATC**, **SayIntentions.AI**, **GSX Pro** (injection mémoire/menu/commandes), arbitrage `GateSource` / `GateDecision`, surveillance processus Win32 sans sous-processus (`is_process_running_win32`). |
| `src/legal_and_diagnostics.py` | ~780 | EULA, politique de confidentialité, licences tierces, capture structurée des rapports de crash (`%APPDATA%\GateFinder\crashes`) et statistiques anonymes opt-in. |
| `src/autostart.py` | ~160 | Classe `AutoStartManager` : enregistrement/retrait propre de `GateFinder.exe` dans le fichier `exe.xml` de MSFS 2020 et MSFS 2024. |
| `src/network.py` | ~120 | Classe `OnlineNetworkChecker` : récupération et cache des pilotes connectés sur **VATSIM** et **IVAO** pour la détection d'occupation des portes. |
| *(Hérités V1 — ne pas modifier)* | — | `src/core.py` et `src/build_msfs_panel.py` sont d'anciens scripts hérités de la V1 non utilisés par le runtime V2 (`main.py` utilise exclusivement `backend.py`, `gui.py`, `taxi_router.py`, `interoperability_hub.py` et `MSFS_Package/gatefinder-ingame-panel`). |

---

### 3.2 Package MSFS (`D:\GateFinder\MSFS_Package\gatefinder-ingame-panel\`)

| Chemin relatif dans le package | Rôle |
| :--- | :--- |
| `html_ui/InGamePanels/GateFinderPanel/GateFinderPanel.js` | Logique complète du client JS/Canvas (`~4 180` lignes) partagée par les **4 vues web/sim** : Toolbar Panel MSFS, App EFB MSFS 2024, App EFB Fenix et Web EFB externe iPad/Mobile. Rendu Lido Canvas 2D, `Follow + Hdg Up`, interactions taxiways/stands, et modales synchronisées (`AtcRunwayModal`, `LiveStandModal`, `SimbriefMismatchModal`). |
| `html_ui/InGamePanels/GateFinderPanel/GateFinderPanel.html` | Conteneur HTML du panneau barre d'outils MSFS 2020/2024 (`ingame-ui`). |
| `html_ui/InGamePanels/GateFinderPanel/GateFinderPanel.css` | Feuille de style principale du panneau et des composants partagés. |
| `html_ui/InGamePanels/GateFinderPanel/GateFinderEfbFrame.html` | Cadre HTML/CSS optimisé pour l'application native tablette EFB MSFS 2024. |
| `html_ui/InGamePanels/GateFinderPanel/GateFinderFenixFrame.html` | Cadre HTML/CSS optimisé pour les tablettes cockpit Fenix A319/A320/A321 (`IS_FENIX_EFB_APP = true`). |
| `html_ui/efb_ui/efb_apps/GateFinderEfbApp/GateFinderEfbApp.js` | Wrapper d'application native MSFS 2024 EFB (`efb_ui`). |
| `html_ui/Pages/VCockpit/Instruments/FNX32X/EFB/EfbHost_Captain.html` & `EfbHost_FO.html` | Hôtes EFB Fenix intégrant l'icône et l'iframe GateFinder sur les tablettes Captain & FO (installés uniquement si `fenix_efb_enabled == True`). |
| `InGamePanels/InGamePanel_GateFinder.spb` | Définition binaire SimProp du panneau barre d'outils MSFS. |
| `layout.json` & `manifest.json` | Index MSFS obligatoire des fichiers (`size` + timestamp Windows `FILETIME` 64 bits). **Attention :** dans `layout.json`, conserver impérativement la casse existante `"html_ui/ingamePanels/GateFinderPanel/..."` attendue par le `.spb`. |

---

### 3.3 API HTTP Locale (`http://127.0.0.1:8420` / LAN `:8420` dans `src/backend.py`)

Tous les clients (In-Game Panel, EFB MSFS 2024, EFB Fenix, iPad/Mobile Web EFB) communiquent avec `GateFinderBackend` via ces routes GET :
- `/` , `/efb` , `/phone` , `/tablet` : Sert l'application Web EFB responsive autonome.
- `/fenix_efb` , `/GateFinderEfbFrame.html` , `/GateFinderFenixFrame.html` , `/GateFinderPanel.js` , `/GateFinderPanel.css` : Sert les assets du panel avec cache-busting dynamique (`?v=...` réécrit avec le timestamp courant).
- `/api/current?have_dep=XXXX&have_arr=YYYY` : Retourne l'état temps réel complet (`get_dynamic_flight_data()`), en omettant `chart_data` si le client possède déjà la géométrie de `have_dep`/`have_arr` pour économiser la bande passante. Retourne également `pending_simbrief_mismatch` même lorsqu'aucun vol n'est encore chargé.
- `/api/simbrief?username=...` : Déclenche l'import de l'OFP SimBrief actif.
- `/api/peek_simbrief` : Vérifie légèrement (`peek_latest_simbrief_ofp`) l'`ofp_id`, l'origine, la destination et le type avion du dernier OFP SimBrief sans écraser la session active.
- `/api/open_simbrief_dispatch` : Ouvre `https://dispatch.simbrief.com/home` dans le navigateur du PC.
- `/api/resolve_mismatch?action=use_msfs|keep_simbrief|import_simbrief&live_icao=...&dest=...&key=...` : Résout la modale de mismatch SimBrief/MSFS depuis l'EFB et ferme simultanément la modale côté Desktop (`_gui_close_mismatch_modal = True`).
- `/api/resolve_live_stand?action=keep_live|keep_assigned` : Résout la modale de stand MSFS détecté au démarrage.
- `/api/set_gate?phase=departure|arrival&gate=...` : Sélection manuelle d'un stand + synchronisation GSX Pro.
- `/api/reposition_aircraft?phase=departure|arrival&gate=...` : Téléporte l'avion sur le stand choisi (GSX Pro ou fallback Warp SimConnect natif).
- `/api/set_runway?phase=departure|arrival&rwy=...` : Change la piste active et recalcule la route A\*.
- `/api/set_taxi_via?phase=...&action=auto|clear&toggle=...&remove=...&via=...` : Édition interactive des taxiways (`ATC TAXI CLEARANCE`).
- `/api/trigger_gsx?phase=departure|arrival` : Force une synchronisation manuelle GSX Pro.
- `/api/airline_logo?code=XXX&size=...&width=...&radius=...` : Sert le badge PNG haute résolution de la compagnie (ou badge vectoriel `CAR` / `MIL` / `BIZ` / `GA`).
- `/api/show_window` : Demande l'affichage au premier plan de la fenêtre Desktop depuis un client externe.

---

### 3.4 Fichiers de Données, Caches & Build (`D:\GateFinder\`)

- `settings.json` : Configuration utilisateur locale (**NE JAMAIS inclure dans un `.zip` de release ni écraser lors d'une mise à jour**).
- `last_flight_session.json` : Dernière session de vol sauvegardée pour la détection de *Turnaround* (**NE JAMAIS inclure dans un `.zip` de release**).
- `taxi_charts_cache.json` : Cache vectoriel pré-généré contenant notamment les **50 plus grands aéroports vérifiés (`geom_v=4`)** (**INCLUS** dans le `.zip` de release pour fonctionnement hors-ligne immédiat).
- `default_airports_db.bin` : Base binaire compressée de tous les aéroports mondiaux (coordonnées, noms, pistes).
- `airlines_terminals.json` : Base de règles réelles d'affectation compagnies ↔ terminaux/jetées sur les grands hubs.
- `cache/airline_logos/` : Logos compagnies pré-cachés (**INCLUS** dans le `.zip` de release).
- `GateFinder.spec` : Spécification **PyInstaller** (`--onefile`, `console=False`, embarquant `icon.png`, `icon.ico`, `default_airports_db.bin`, `SimConnect_MSFS.dll`, `airlines_terminals.json`, `MSFS_Package\gatefinder-ingame-panel` et `SimConnect`).

---

## 4. Charte UI/UX & Règles d'Ingénierie Strictes (À Respecter dans Tous les Prompts Gemini)

### 4.1 Direction Artistique & UI/UX
1. **Style Épuré, Minimaliste et Non Bavard** :
   - **Zéro icône superflue et zéro emoji** dans les boutons, barres d'outils et modales de l'application.
   - Textes courts, directs, techniques (style EFB aéronautique Lido), en **anglais** dans l'interface (`GateFinder` est distribué internationalement).
2. **Design Tokens & Palette Sombre Borderless** :
   - **Zéro bordure** (`border_width=0` partout sur CustomTkinter, cartes CSS sans bordures lourdes).
   - Fonds principaux : `#0F172A` (fond modales), `#111827` / `#1B1E24` (cartes & barres), `#0B1120` (fond carte Lido Night), `#1E293B` (champs de saisie).
   - Boutons neutres / discrets : `#232730` ou `#2B303B` (hover `#383E4C`), texte secondaire `#64748B` ou `#94A3B8`, texte primaire `#FFFFFF`.
   - Bleu d'action primaire (ex. `Update available`, `Open SimBrief`, `Import SimBrief`) : `#0A86C2` (hover `#0A6E9E`).
   - Palette dynamique de vol : camaïeu `cam["s1"]..cam["s4"]` et `cam["accent"]` calculé selon la compagnie active.
3. **Parité Systématique Desktop ↔ EFB Cockpit** :
   - Lorsqu'une fonctionnalité touche l'expérience de vol ou une modale interactive, toujours préciser si elle doit s'appliquer à la fois au **Desktop (`src/gui.py`)** et au **Panel/EFB (`GateFinderPanel.js` + endpoints `src/backend.py`)**, avec fermeture/synchronisation croisée.

### 4.2 Contraintes Techniques & Pièges Connus (Gotchas)
1. **Principe Absolu de Non-Régression & Modifications Chirurgicales** :
   - Ne jamais réécrire une classe ou un fichier entier quand un patch localisé suffit.
   - Toute nouvelle option dans `Config.settings` (`src/config.py`) doit avoir une valeur par défaut rétrocompatible qui préserve le comportement existant.
2. **Compatibilité SimConnect MSFS 2020 vs MSFS 2024** :
   - Certains SimVars (comme `"LIVERY NAME"`) n'existent que sur MSFS 2024. Ne **jamais** les ajouter au bloc `AddToDataDefinition` principal (`def_id = 851`), sinon MSFS 2020 rejette toute la définition ; toujours utiliser un `def_id` séparé (ex. `852`) encapsulé dans son propre `try/except`.
3. **Cache-Busting Web / CoherentGT / Fenix CEF** :
   - Toute modification de `GateFinderPanel.js` ou `GateFinderPanel.css` nécessite d'incrémenter le paramètre `?v=...` dans `GateFinderPanel.html` (et vérifier la réécriture dynamique `?v=` dans `src/backend.py`) + régénérer `layout.json` et `manifest.json` (`total_package_size`) avec des timestamps Windows `FILETIME` à jour **sans altérer la casse des chemins `html_ui/ingamePanels/...`**.
4. **Pipeline de Build & Packaging Release** :
   - Toujours régénérer `MSFS_Package/gatefinder-ingame-panel/layout.json` & `manifest.json` **avant** de lancer `pyinstaller GateFinder.spec --noconfirm` (car `GateFinder.spec` embarque `MSFS_Package` dans `GateFinder.exe`).
   - Synchroniser `MSFS_Package/gatefinder-ingame-panel` vers les dossiers `Community` et `Community2024` locaux pour test immédiat.
   - Pour publier une mise à jour auto-updatable (`V2.0.6+`), incrémenter la version partout (`src/gui.py` `current_ver`, titres fenêtre/HTML `manifest.json`, `src/legal_and_diagnostics.py` `APP_VERSION`), compiler `GateFinder.exe`, et générer `GateFinder_V2.X.X.zip` **sans** `settings.json`, `last_flight_session.json` ni fichiers `.log`, puis publier une Release GitHub (`wildbill75/gsx-gatefinder`, tag `v2.X.X`) avec le `.zip` en *Release Asset*.

---

## 5. Modèle Recommandé pour que Gemini Rédige un Prompt à Antigravity

Lorsque Gemini génère un prompt d'implémentation ou de correction pour Antigravity, la structure idéale est la suivante :

```markdown
### Contexte & Objectif
[Description claire et concise du besoin fonctionnel ou du bug constaté en simu]

### Fichiers & Composants Ciblés
- Backend : `src/backend.py` / `src/taxi_router.py` / `src/interoperability_hub.py`
- Desktop UI : `src/gui.py`
- MSFS Panel / EFB / Web : `MSFS_Package/gatefinder-ingame-panel/html_ui/InGamePanels/GateFinderPanel/GateFinderPanel.js`

### Spécifications Précises
1. [Comportement attendu côté logique/données, cas limites, rétrocompatibilité]
2. [Comportement UI/UX : style épuré borderless, zéro icône, couleurs exactes, textes courts en anglais]
3. [Synchronisation Desktop <-> EFB si applicable]

### Contraintes & Livrables
- Modification chirurgicale stricte sans régression sur l'existant.
- Vérification syntaxique (`py_compile` + `node --check`) et test unitaire sur les cas limites.
- Mise à jour `layout.json` / `manifest.json`, synchronisation `Community` / `Community2024`, recompilation `GateFinder.exe` (et packaging `.zip` si nouvelle version).
```
