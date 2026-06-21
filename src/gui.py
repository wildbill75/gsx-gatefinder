import customtkinter as ctk
from tkinter import messagebox
from config import Config
from autostart import AutoStartManager
import os
import sys

# Configuration du thème moderne et chic
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, config: Config, autostart: AutoStartManager, backend, on_save_callback, on_close_callback):
        super().__init__(parent, fg_color="transparent")
        self.config = config
        self.autostart = autostart
        self.backend = backend
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback
        
        ctk.CTkLabel(self, text="GateFinder Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(0, 20))
        
        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(form_frame, text="Simbrief Username / Pilot ID:").grid(row=0, column=0, sticky="w", pady=10)
        self.simbrief_entry = ctk.CTkEntry(form_frame, width=120)
        self.simbrief_entry.grid(row=0, column=1, sticky="w", padx=10, pady=10)
        self.simbrief_entry.insert(0, self.config.settings.get("simbrief_username", ""))
        
        ctk.CTkLabel(form_frame, text="GSX Profile Path:").grid(row=1, column=0, sticky="w", pady=10)
        
        gsx_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        gsx_frame.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.gsx_entry = ctk.CTkEntry(gsx_frame, width=300)
        self.gsx_entry.pack(side="left", fill="x", expand=True)
        self.gsx_entry.insert(0, self.config.settings.get("gsx_profile_path", ""))
        
        from tkinter import filedialog
        
        def browse_gsx():
            d = filedialog.askdirectory(title="Select GSX Profile Folder")
            if d:
                self.gsx_entry.delete(0, 'end')
                self.gsx_entry.insert(0, d)
                
        def auto_scan():
            appdata = os.environ.get("APPDATA", "")
            d = os.path.join(appdata, "Virtuali", "GSX", "MSFS")
            self.gsx_entry.delete(0, 'end')
            self.gsx_entry.insert(0, d)
            
        ctk.CTkButton(gsx_frame, text="...", width=30, command=browse_gsx).pack(side="left", padx=5)
        ctk.CTkButton(gsx_frame, text="Auto-Scan", width=70, command=auto_scan).pack(side="left")
        
        # Checkboxes container
        chk_frame = ctk.CTkFrame(self, fg_color="transparent")
        chk_frame.pack(pady=10)
        
        self.autostart_var = ctk.BooleanVar(value=self.config.settings.get("auto_start", False))
        self.autostart_checkbox = ctk.CTkCheckBox(chk_frame, text="Auto-Start with MSFS 2024", variable=self.autostart_var)
        self.autostart_checkbox.pack(side="left", padx=10)
        
        self.autofetch_var = ctk.BooleanVar(value=self.config.settings.get("auto_fetch", False))
        self.autofetch_checkbox = ctk.CTkCheckBox(chk_frame, text="Auto-Fetch latest SimBrief", variable=self.autofetch_var)
        self.autofetch_checkbox.pack(side="left", padx=10)
        
        # Database Scan Section
        scan_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray17"))
        scan_frame.pack(fill="x", padx=20, pady=20)
        
        self.scan_lbl = ctk.CTkLabel(scan_frame, text="Synchronize with Community Database:", font=("Arial", 14, "bold"))
        self.scan_lbl.pack(pady=10)
        
        btn_frame = ctk.CTkFrame(scan_frame, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        ctk.CTkButton(btn_frame, text="Scan Installed Airports", command=self.run_scan, width=150).pack(side="left", padx=5)
        self.btn_contribute = ctk.CTkButton(btn_frame, text="Contribute Missing", command=self.run_contribute, width=150, fg_color="#10B981", hover_color="#059669")
        self.btn_contribute.pack(side="left", padx=5)
        self.btn_contribute.configure(state="disabled")
        
        self.unknown_files = []

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(pady=20)
        ctk.CTkButton(action_frame, text="Save & Close", command=self.save_settings).pack(side="left", padx=10)
        ctk.CTkButton(action_frame, text="Cancel", fg_color="gray", hover_color="darkgray", command=self.on_close_callback).pack(side="left", padx=10)

    def run_scan(self):
        self.config.settings["gsx_profile_path"] = self.gsx_entry.get().strip()
        self.config.save()
        
        self.scan_lbl.configure(text="Scanning...")
        self.update()
        
        res = self.backend.scan_gsx_profiles()
        supported = len(res["supported"])
        unknown = len(res["unknown"])
        self.unknown_files = res["unknown"]
        
        self.scan_lbl.configure(text=f"✅ {supported} airports synchronized with GateFinder.")
        
        if unknown > 0:
            self.scan_lbl.configure(text=f"✅ {supported} airports synchronized.\n\n🌟 You have {unknown} airports that can be added to the community DB!")
            self.btn_contribute.configure(text=f"Share {unknown} Airports", state="normal")
        else:
            self.btn_contribute.configure(text="Community DB is Up to Date", state="disabled")

    def run_contribute(self):
        if not self.unknown_files: return
        import webbrowser
        
        out_path = self.backend.generate_contribution_file(self.unknown_files)
        if out_path:
            messagebox.showinfo("Contribute", f"File generated on Desktop:\n{out_path}\n\nA browser will open to GitHub. Please drag and drop the JSON file into the issue body to submit your missing airports!")
            webbrowser.open("https://github.com/wildbill75/gsx-gatefinder/issues/new?title=GSX+Data+Contribution&body=Please+drag+and+drop+the+GateFinder_Contribution.json+file+here.")
        else:
            messagebox.showinfo("Contribute", "No valid airline data found to contribute.")

    def save_settings(self):
        self.config.settings["simbrief_username"] = self.simbrief_entry.get().strip()
        self.config.settings["gsx_profile_path"] = self.gsx_entry.get().strip()
        auto = self.autostart_var.get()
        self.config.settings["auto_start"] = auto
        self.config.settings["auto_fetch"] = self.autofetch_var.get()
        self.config.save()
        
        if auto:
            self.autostart.enable()
        else:
            self.autostart.disable()
            
        self.on_save_callback()
        self.on_close_callback()

class GUIApp(ctk.CTk):
    def get_resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

    def __init__(self, config, autostart, backend):
        super().__init__()
        self.title("MSFS 2024 - GateFinder V1.0")
        self.geometry("600x750")
        icon_path = self.get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        self.minsize(550, 700)
        
        # Hide window if started silently
        if "--silent" in sys.argv:
            self.withdraw()
            
        self.config = config
        self.autostart = autostart
        self.backend = backend
        
        # When clicking 'X', just minimize to tray instead of quitting
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        
        self.create_widgets()
        
        self.last_flight_data = None
        self.check_sync_loop()
        
        # Check if setup is needed
        if not self.config.settings.get("simbrief_username"):
            self.show_settings()
        else:
            self.show_main_view()
            if self.config.settings.get("auto_fetch"):
                self.after(500, self.fetch_simbrief)

    def check_sync_loop(self):
        if self.backend.current_flight_data and self.backend.current_flight_data != self.last_flight_data:
            self.last_flight_data = self.backend.current_flight_data
            self.render_results(self.last_flight_data)
        self.after(2000, self.check_sync_loop)

    def hide_to_tray(self):
        self.withdraw()

    def show_main_window(self):
        self.deiconify()
        self.lift()

    def create_widgets(self):
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(self.header_frame, text="GATEFINDER V1.0", font=ctk.CTkFont(size=30, weight="bold")).pack(side="left")
        self.btn_settings = ctk.CTkButton(self.header_frame, text="⚙ Settings", width=120, command=self.show_settings)
        self.btn_settings.pack(side="right")
        
        # Container for main content
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        # 1. Main View Frame
        self.main_view_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")
        
        self.sb_frame = ctk.CTkFrame(self.main_view_frame, corner_radius=15, fg_color=("gray85", "gray17"))
        self.sb_frame.pack(fill="x", padx=20, pady=10)
        
        self.btn_import = ctk.CTkButton(self.sb_frame, text="Import SimBrief Flight Plan", 
                                        font=ctk.CTkFont(size=20, weight="bold"), height=60,
                                        command=self.fetch_simbrief)
        self.btn_import.pack(fill="x", padx=20, pady=20)
        
        self.results_frame = ctk.CTkScrollableFrame(self.main_view_frame, corner_radius=10, fg_color=("white", "gray12"))
        self.results_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.placeholder_lbl = ctk.CTkLabel(self.results_frame, text="Waiting for SimBrief import...", text_color="gray")
        self.placeholder_lbl.pack(pady=50)

        # 2. Settings View Frame
        self.settings_view = SettingsView(self.content_container, self.config, self.autostart, self.backend, self.on_settings_saved, self.show_main_view)

    def show_settings(self):
        self.main_view_frame.pack_forget()
        self.btn_settings.configure(state="disabled")
        self.settings_view.pack(fill="both", expand=True, padx=20, pady=20)

    def show_main_view(self):
        self.settings_view.pack_forget()
        self.btn_settings.configure(state="normal")
        self.main_view_frame.pack(fill="both", expand=True)

    def on_settings_saved(self):
        self.backend.load_data()

    def fetch_simbrief(self):
        username = self.config.settings.get("simbrief_username", "").strip()
        if not username:
            messagebox.showerror("Error", "Please configure your Simbrief Username or Pilot ID in Settings.")
            self.show_settings()
            return
            
        self.btn_import.configure(text="Importing...", state="disabled")
        self.update()
        
        try:
            result = self.backend.get_flight_data(username)
            self.render_results(result)
        except Exception as e:
            messagebox.showerror("Simbrief Error", f"Unable to fetch flight plan.\nCheck your ID.\n{str(e)}")
        finally:
            self.btn_import.configure(text="Import SimBrief Flight Plan", state="normal")

    def render_results(self, result):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
            
        header_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        ac_badge = ctk.CTkFrame(header_frame, corner_radius=10, fg_color="#1E3A8A")
        ac_badge.pack(side="left", padx=(0, 10), fill="x", expand=True)
        ctk.CTkLabel(ac_badge, text=f"{result['aircraft']}", 
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack(padx=20, pady=15)
                     
        al_badge = ctk.CTkFrame(header_frame, corner_radius=10, fg_color="#1E3A8A")
        al_badge.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(al_badge, text=f"{result['airline']}", 
                     font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack(padx=20, pady=15)

        def render_section(title, airport_data):
            if not airport_data: return
            
            section_frame = ctk.CTkFrame(self.results_frame, corner_radius=10, fg_color=("gray90", "gray15"))
            section_frame.pack(fill="x", pady=10)
            
            title_text = f"{title} - {airport_data['icao']}"
            if airport_data['name']:
                title_text += f" ({airport_data['name']})"
                
            ctk.CTkLabel(section_frame, text=title_text, font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
            
            if airport_data.get('error'):
                color = "#F59E0B" if airport_data['osm'] else "#EF4444"
                msg = "🌐 GSX Profile not found. Fallback results (OSM):" if airport_data['osm'] else airport_data['error']
                ctk.CTkLabel(section_frame, text=msg, text_color=color, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(0, 10))
            
            if airport_data.get('gate'):
                t_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
                t_frame.pack(fill="x", padx=15, pady=(5, 15))
                
                if airport_data.get('terminal'):
                    ctk.CTkLabel(t_frame, text=airport_data['terminal'], font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=(0, 15))
                
                gateText = airport_data['gate']
                if airport_data.get('osm'):
                    gateText = "Stand " + gateText
                    
                color = "#374151" if airport_data.get('osm') else "#059669"
                ctk.CTkLabel(t_frame, text=f"{gateText}", fg_color=color, corner_radius=5, padx=20, pady=10, font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        render_section("DEPARTURE", result.get('departure'))
        render_section("ARRIVAL", result.get('arrival'))
        
        self.update_idletasks()
        req_height = min(self.winfo_reqheight() + 50, 950)
        self.geometry(f"600x{req_height}")
