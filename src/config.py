import os
import json
import sys

class Config:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.settings_file = os.path.join(base_dir, "settings.json")
        self.settings = {
            "gsx_profile_path": os.path.join(os.environ.get("APPDATA", ""), "Virtuali", "GSX", "MSFS"),
            "simbrief_username": "",
            "auto_start": False
        }
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
