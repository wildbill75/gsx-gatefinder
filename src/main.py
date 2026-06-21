import threading
import pystray
from PIL import Image, ImageDraw
import sys
import ctypes

from config import Config
from autostart import AutoStartManager
from backend import GateFinderBackend
from gui import GUIApp

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def create_icon_image():
    # Dynamically draw the icon to guarantee pystray compatibility on Windows
    img = Image.new('RGB', (64, 64), (30, 58, 138))
    draw = ImageDraw.Draw(img)
    def s(val): return int(val * 0.64)
    
    draw.line([(s(20), s(15)), (s(20), s(90)), (s(80), s(90)), (s(80), s(15))], fill=(255,255,255), width=max(1, s(2)))
    draw.line([(s(35), s(15)), (s(65), s(15))], fill=(255,255,255), width=max(1, s(4)))
    for y in range(s(5), s(95), s(10)):
        draw.line([(s(50), y), (s(50), min(y+s(6), s(95)))], fill=(200,200,200), width=max(1, s(3)))
        
    plane_points = [
        (s(50), s(20)), (s(53), s(22)), (s(54), s(28)), (s(54), s(35)),
        (s(85), s(55)), (s(85), s(60)), (s(54), s(60)),
        (s(54), s(75)), (s(65), s(80)), (s(65), s(83)), (s(50), s(81)),
        (s(35), s(83)), (s(35), s(80)), (s(46), s(75)),
        (s(46), s(60)), (s(15), s(60)), (s(15), s(55)), (s(46), s(35)),
        (s(46), s(28)), (s(47), s(22))
    ]
    draw.polygon(plane_points, fill=(255,255,255))
    return img

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

    icon = pystray.Icon("GateFinder", create_icon_image(), "GateFinder", menu)
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
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\GateFinderMutex")
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
