import os
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
    try:
        png_path = get_resource_path("icon.png")
        if os.path.exists(png_path):
            return Image.open(png_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        ico_path = get_resource_path("icon.ico")
        if os.path.exists(ico_path):
            return Image.open(ico_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    except Exception:
        pass
    img = Image.new('RGB', (64, 64), (249, 87, 15))
    return img

def setup_tray(app, backend):
    def show_main(icon, item):
        app.after(0, app.show_main_window)
        
    def show_settings(icon, item):
        def _open_settings():
            app.show_settings()
            app.show_main_window()
        app.after(0, _open_settings)

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
    app._tray_icon = icon
    icon.run()

def check_loopback_exemption():
    import subprocess
    try:
        subprocess.run('CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.Limitless_8wekyb3d8bbwe"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run('CheckNetIsolation.exe LoopbackExempt -a -n="Microsoft.FlightSimulator_8wekyb3d8bbwe"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        ans = messagebox.askyesno(
            "Uninstall GateFinder?",
            "This will completely remove the GateFinder In-Game Panel from all detected MSFS Community folders and clean auto-start entries.\n\n"
            "Make sure Microsoft Flight Simulator is closed before continuing.\n\n"
            "Do you want to proceed with uninstallation?"
        )
        if ans:
            config = Config()
            backend = GateFinderBackend(config)
            res = backend.uninstall_app()
            if not res.get("success"):
                failed_str = "\n".join([f"- {path}: {err}" for path, err in res.get("failed_paths", [])])
                messagebox.showerror(
                    "Uninstall Error",
                    f"Failed to delete the package from some folder(s):\n{failed_str}\n\n"
                    "Please ensure MSFS is completely closed and try again."
                )
            else:
                removed = res.get("removed_paths", [])
                if removed:
                    removed_str = "\n".join([f"• {p}" for p in removed])
                    msg = (
                        "GateFinder has been successfully uninstalled!\n\n"
                        f"Removed In-Game Panel from:\n{removed_str}\n\n"
                        "• MSFS Auto-start (exe.xml) entries cleaned.\n\n"
                        "You can now delete the GateFinder folder."
                    )
                else:
                    msg = (
                        "GateFinder uninstall complete.\n\n"
                        "• Checked all standard MSFS Community folders (no existing 'gatefinder-ingame-panel' or 'wildbill75-gatefinder' package was found).\n"
                        "• MSFS Auto-start (exe.xml) entries have been cleaned.\n\n"
                        "Note: If you use MSFS Addon Linker, make sure GateFinder is unlinked from within Addon Linker.\n\n"
                        "You can now delete the GateFinder folder."
                    )
                messagebox.showinfo("Uninstall Complete", msg)
        root.destroy()
        sys.exit(0)

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GateFinder.EFB.V2.GF2")
    except Exception:
        pass

    # Prevent multiple instances — if already running in background/System Tray, wake up the existing window
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\GateFinderMutex")
    if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        already_alive = False
        for p_port in (8125, 8420):
            try:
                import urllib.request
                api_ep = "status" if "--silent" in sys.argv else "show_window"
                urllib.request.urlopen(f"http://127.0.0.1:{p_port}/api/{api_ep}", timeout=0.5).read()
                already_alive = True
                break
            except Exception:
                pass
        if not already_alive:
            try:
                hwnd = (
                    ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.8")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.6")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.5")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.4")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.3")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.2")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0.1")
                    or ctypes.windll.user32.FindWindowW(None, "MSFS 2024 - GateFinder V2.0")
                )
                if hwnd:
                    already_alive = True
                    if "--silent" not in sys.argv:
                        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        if already_alive:
            sys.exit(0)

    config = Config()
    autostart = AutoStartManager()

    # Initialize Backend immediately (heavy DB/GSX/cache init deferred until splash screen is on screen)
    from legal_and_diagnostics import LegacyMigrationManager, CrashReporter
    backend = GateFinderBackend(config, defer_heavy_init=True)
    backend.migration_summary = {}
    crash_reporter = CrashReporter(config=config, backend=backend)
    crash_reporter.install_hooks()
    backend.crash_reporter = crash_reporter
    backend.start_server()

    def _bg_startup_housekeeping():
        try:
            check_loopback_exemption()
        except Exception:
            pass
        try:
            migration_mgr = LegacyMigrationManager(config, autostart)
            backend.migration_summary = migration_mgr.run_startup_migration()
        except Exception:
            pass
        try:
            if config.settings.get("auto_start", False):
                autostart.enable()
        except Exception:
            pass
        try:
            backend.ensure_initialized()
        except Exception:
            pass

    threading.Thread(target=_bg_startup_housekeeping, daemon=True).start()

    # Initialize GUI
    app = GUIApp(config, autostart, backend)

    # Start Tray Icon in background thread
    tray_thread = threading.Thread(target=setup_tray, args=(app, backend), daemon=True)
    tray_thread.start()

    # If username is missing, force settings popup
    if not config.settings.get("simbrief_username"):
        app.show_settings()

    app.mainloop()
