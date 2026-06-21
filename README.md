GateFinder V1.0 for MSFS 2024 / MSFS 2020
=======================================

English
-------
Welcome to GateFinder! 

Why GateFinder? 
Have you ever landed at a massive airport after a long flight and wondered: 
"Which gate should I taxi to?" or "Where does my airline actually park here?" 
GateFinder was born from this exact frustration. It eliminates the guesswork by 
automatically importing your current SimBrief flight plan and assigning you the 
most realistic gates for both your departure and arrival, perfectly matched to 
your aircraft type and airline.

How it works (GSX & OSM)
GateFinder uses a smart dual-system to find your gates:
- GSX Profiles (Primary): If you use FSDreamTeam GSX, GateFinder scans your GSX 
  profiles to find parking spots with ultra-precise wingspan limits and airline 
  codes. 
- OpenStreetMap (Fallback): Don't have GSX? No problem! GateFinder will 
  automatically fall back to OpenStreetMap (OSM), a massive community-driven map 
  of the world. It pulls live data directly from OSM to map out the gates and 
  assign you one that fits your airliner.

Installation:
1. The App Folder: You can place the `GateFinder_V1.0` folder containing the 
   application (`GateFinder.exe`) absolutely anywhere on your PC (Desktop, 
   Documents, etc.).
2. The "Community" Addon: Inside this folder, you will find a folder named 
   `wildbill75-gatefinder`. Copy this folder into your MSFS `Community` 
   folder. This adds the GateFinder panel directly into the simulator's in-game 
   toolbar.
   *Note: Due to a current MSFS interface quirk, the GateFinder icon in the 
   simulator toolbar currently appears as a generic "Gear" (cogwheel) icon. 
   This is normal!*

First Launch (Settings):
- Simbrief Username / Pilot ID: Enter your SimBrief username or Pilot ID.
- GSX Profile Path: If you use GSX, point this to your GSX Profiles folder 
  (e.g., %APPDATA%\Virtuali\GSX\MSFS). If you don't use GSX, leave it blank.
- Auto-Start: Launch GateFinder automatically when MSFS starts.
- Auto-Fetch: Automatically import your flight plan as soon as the app opens.
- Scan Installed Airports: Click this to build a local database of your GSX 
  profiles so they load instantly. You must do this first before contributing!

How to Contribute (Community Database):
GateFinder relies on a community database. If you scan your installed airports 
and GateFinder notices you have GSX profiles that are missing from the global 
database, the "Contribute Missing" button will unlock. 
Clicking this button will automatically generate a JSON file containing your 
local gate data and open a GitHub web page. Simply drag-and-drop the generated 
file into the GitHub page to share your data with the rest of the community!

Usage:
Once running, click "Import SimBrief Flight Plan". The app will display your 
Departure and Arrival gates. You can also view this directly inside the 
simulator by clicking the "Gear" icon in your MSFS Toolbar.

---

Français
--------
Bienvenue sur GateFinder !

Pourquoi GateFinder ?
Vous êtes-vous déjà posé sur un aéroport gigantesque après un long vol en vous 
demandant : "À quelle porte dois-je aller ?" ou "Où se gare ma compagnie 
aérienne ici ?" GateFinder est né précisément de cette frustration. Il élimine 
toutes les devinettes en importing automatiquement votre plan de vol SimBrief et 
en vous assignant les portes les plus réalistes pour votre départ et votre 
arrivée, en fonction de votre type d'avion et de votre compagnie.

Comment ça marche (GSX et OSM)
GateFinder utilise un système intelligent à deux niveaux pour trouver vos portes:
- Profils GSX (Principal) : Si vous utilisez FSDreamTeam GSX, GateFinder scanne 
  vos profils GSX pour trouver des places de parking avec des limites 
  d'envergure et des codes de compagnies ultra-précis.
- OpenStreetMap (Solution de secours) : Vous n'avez pas GSX ? Aucun problème ! 
  GateFinder utilisera automatiquement OpenStreetMap (OSM), une carte du monde 
  collaborative massive. Il extrait les données en direct d'OSM pour 
  cartographier les portes et vous en attribuer une adaptée à votre avion.

Installation :
1. Le dossier de l'application : Vous pouvez placer le dossier 
   `GateFinder_V1.0` contenant le logiciel (`GateFinder.exe`) n'importe où sur 
   votre PC (Bureau, Documents, etc.).
2. L'Addon "Community" : À l'intérieur de ce dossier, vous trouverez un 
   sous-dossier nommé `wildbill75-gatefinder`. Copiez ce dossier dans votre 
   dossier `Community` de MSFS. Cela ajoute le panneau GateFinder directement 
   dans la barre d'outils du simulateur.
   *Note : En raison d'une particularité de l'interface actuelle de MSFS, 
   l'icône de GateFinder dans la barre d'outils du simulateur apparaît pour le 
   moment sous la forme d'une "Roue crantée" (engrenage). C'est normal !*

Premier Lancement (Settings) :
- Simbrief Username / Pilot ID : Entrez votre nom d'utilisateur ou ID Pilote.
- GSX Profile Path : Si vous utilisez GSX, indiquez le chemin vers vos profils 
  GSX (ex: %APPDATA%\Virtuali\GSX\MSFS). Sinon, laissez ce champ vide.
- Auto-Start : Lance GateFinder automatiquement au démarrage de MSFS.
- Auto-Fetch : Importe automatiquement votre plan de vol dès l'ouverture de 
  l'application.
- Scan Installed Airports : Cliquez ici pour construire une base de données 
  locale de vos profils GSX pour un chargement instantané. Vous devez 
  obligatoirement faire cela avant de pouvoir contribuer !

Comment Contribuer (Base de données Communautaire) :
GateFinder s'appuie sur une base de données communautaire. Si vous scannez vos 
aéroports et que GateFinder remarque que vous possédez des profils GSX absents 
de la base mondiale, le bouton "Contribute Missing" se débloquera.
En cliquant sur ce bouton, GateFinder générera automatiquement un fichier JSON 
contenant vos données locales et ouvrira une page web GitHub. Il vous suffira 
de glisser-déposer le fichier généré sur la page GitHub pour partager vos 
données avec le reste de la communauté !

Utilisation :
Une fois lancé, cliquez sur "Import SimBrief Flight Plan". L'application 
affichera vos portes de départ et d'arrivée. Vous pouvez également consulter 
ces informations directement dans le simulateur en cliquant sur l'icône 
"Roue crantée" dans la barre d'outils MSFS.
