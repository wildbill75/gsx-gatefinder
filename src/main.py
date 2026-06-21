import threading
import pystray
from PIL import Image, ImageDraw
import sys
import ctypes

from config import Config
from autostart import AutoStartManager
from backend import GateFinderBackend
from gui import GUIApp

def create_icon_image():
    # Load the custom logo image instead of drawing it dynamically
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    # Fallback to dynamic drawing if file not found
    image = Image.new('RGB', (64, 64), color=(30, 58, 138))
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 24, 48, 40], fill="white")
    draw.polygon([(48, 24), (60, 32), (48, 40)], fill="white")
    draw.polygon([(24, 8), (32, 24), (16, 24)], fill="white")
    draw.polygon([(24, 56), (32, 40), (16, 40)], fill="white")
    return image

def setup_tray(app, backend):
    def show_main(icon, item):
        app.after(0, app.show_main_window)
        
    def show_settings(icon, item):
        app.after(0, app.show_settings)

    def quit_app(icon, item):
        icon.stop()
        app.after(0, app.quit)
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open GateFinder", show_main, default=True),
        pystray.MenuItem("Settings", show_settings),
        pystray.MenuItem("Quit", quit_app)
    )

    icon = pystray.Icon("GSX GateFinder", create_icon_image(), "GSX GateFinder", menu)
    icon.run()

def check_loopback_exemption():
    import subprocess
    try:
        subprocess.run('CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.Limitless_8wekyb3d8bbwe"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run('CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.FlightSimulator_8wekyb3d8bbwe"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

if __name__ == "__main__":
    check_loopback_exemption()
    # Prevent multiple instances
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\GSXGateFinderMutex")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        sys.exit(0)

    config = Config()
    autostart = AutoStartManager()
    
    # Initialize Backend
    backend = GateFinderBackend(config)
    backend.load_data()
    backend.start_server()

    # Initialize GUI
    app = GUIApp(config, autostart, backend)

    # Start Tray Icon in background thread
    tray_thread = threading.Thread(target=setup_tray, args=(app, backend), daemon=True)
    tray_thread.start()

    # If username is missing, force settings popup
    if not config.settings.get("simbrief_username"):
        app.show_settings()

    app.mainloop()
