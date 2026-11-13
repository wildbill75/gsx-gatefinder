import os
import json
import sys

def find_msfs_community_folders():
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    
    paths_all = [
        # MSFS 2024 Store
        os.path.join(local_appdata, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
        # MSFS 2024 Steam
        os.path.join(appdata, "Microsoft Flight Simulator 2024", "UserCfg.opt"),
        # MSFS 2020 Store
        os.path.join(local_appdata, "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
        # MSFS 2020 Steam
        os.path.join(appdata, "Microsoft Flight Simulator", "UserCfg.opt"),
    ]
    
    found_folders = []
    
    for p in paths_all:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip().startswith("InstalledPackagesPath"):
                            parts = line.split('"', 2)
                            if len(parts) >= 2:
                                base_p = parts[1]
                                main_comm = os.path.join(base_p, "Community")
                                comm_2024 = os.path.join(base_p, "Community2024")
                                if os.path.exists(main_comm) and main_comm not in found_folders:
                                    found_folders.append(main_comm)
                                if os.path.exists(comm_2024) and comm_2024 not in found_folders:
                                    found_folders.append(comm_2024)
                                break
            except Exception:
                pass

    primary = found_folders[0] if len(found_folders) > 0 else ""
    secondary = found_folders[1] if len(found_folders) > 1 else ""
    return primary, secondary

def find_all_possible_community_folders():
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    
    cfg_paths = [
        # MSFS 2024 Store
        os.path.join(local_appdata, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
        # MSFS 2024 Steam
        os.path.join(appdata, "Microsoft Flight Simulator 2024", "UserCfg.opt"),
        # MSFS 2020 Store
        os.path.join(local_appdata, "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "UserCfg.opt"),
        # MSFS 2020 Steam
        os.path.join(appdata, "Microsoft Flight Simulator", "UserCfg.opt"),
    ]
    
    candidates = []
    
    for p in cfg_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip().startswith("InstalledPackagesPath"):
                            parts = line.split('"', 2)
                            if len(parts) >= 2:
                                base_p = parts[1]
                                for sub in ["Community", "Community2024", "Community2020"]:
                                    cp = os.path.join(base_p, sub)
                                    if os.path.exists(cp) and cp not in candidates:
                                        candidates.append(cp)
                                break
            except Exception:
                pass

    default_fallbacks = [
        os.path.join(local_appdata, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "Packages", "Community"),
        os.path.join(local_appdata, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "Packages", "Community2024"),
        os.path.join(appdata, "Microsoft Flight Simulator 2024", "Packages", "Community"),
        os.path.join(local_appdata, "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "Packages", "Community"),
        os.path.join(appdata, "Microsoft Flight Simulator", "Packages", "Community"),
    ]
    for df in default_fallbacks:
        if os.path.exists(df) and df not in candidates:
            candidates.append(df)
            
    return candidates

def find_msfs_community_folder():
    c20, c24 = find_msfs_community_folders()
    return c20 or c24

def find_sayintentions_api_key():
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if not local_appdata:
        return ""
    fj_path = os.path.join(local_appdata, "SayIntentionsAI", "flight.json")
    if os.path.exists(fj_path):
        try:
            with open(fj_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            fd = data.get("flight_details") or {}
            key = str(fd.get("api_key") or "").strip()
            if key:
                return key
        except Exception:
            pass
    return ""

class Config:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.settings_file = os.path.join(base_dir, "settings.json")
        default_gsx = os.path.join(os.environ.get("APPDATA", ""), "Virtuali", "GSX", "MSFS")
        if not os.path.exists(default_gsx):
            default_gsx = ""
            
        c20_def, c24_def = find_msfs_community_folders()
        si_key_def = find_sayintentions_api_key()
            
        self._default_gsx = default_gsx
        self._default_c20 = c20_def
        self._default_c24 = c24_def
        self._default_si_key = si_key_def
            
        self.settings = {
            "gsx_profile_path": default_gsx,
            "msfs_community_path": c20_def,
            "msfs_community2024_path": c24_def,
            "simbrief_username": "",
            "auto_start": False,
            "auto_quit_with_msfs": True,
            "fenix_efb_enabled": True,
            "auto_fetch": True,
            "map_style": "Satellite Imagery",
            "check_online_traffic": True,
            "auto_lock_turnaround": True,
            "ignored_gates": "",
            "show_maps": True,
            "hibernate_map_in_flight": True,
            "exclude_cargo": False,
            "exclude_ga_ramp": False,
            "show_wingspan": True,
            "auto_clear_ai": True,
            "mars_overlap_protection": True,
            "prioritize_ai_atc": True,
            "auto_inject_gsx": True,
            "gsx_request_follow_me": False,
            "vatsim_tod_refresh_nm": 180.0,
            "sayintentions_api_key": si_key_def,
            "map_follow_refresh_hz": 10,
            "suppress_popups_in_cockpit": False,
            "default_mismatch_action": "ask",
            "last_seen_changelog_version": "",
            "send_crash_reports": True,
            "share_flight_stats": True
        }
        self.load()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data.pop("auto_quit_on_takeoff", None)
                    if not data.get("_v2_hib_default_migrated"):
                        data["hibernate_map_in_flight"] = True
                        data["_v2_hib_default_migrated"] = True
                    if not data.get("_v201_autofetch_migrated"):
                        data["auto_fetch"] = True
                        data["_v201_autofetch_migrated"] = True
                        needs_resave_af = True
                    else:
                        needs_resave_af = False
                    if not data.get("_v204_autoquit_migrated"):
                        data["auto_quit_with_msfs"] = True
                        data["_v204_autoquit_migrated"] = True
                        needs_resave_af = True
                    # Always enforce V2.0 non-deprecated defaults for retired V1 toggles
                    data["show_maps"] = True
                    data["show_wingspan"] = True
                    data["exclude_cargo"] = False
                    data["exclude_ga_ramp"] = False
                    data["ignored_gates"] = ""

                    # Sanitize foreign PC paths if settings.json was copied from another machine
                    cur_win_user = os.environ.get("USERNAME", "").strip().lower()
                    needs_resave = False
                    if cur_win_user and cur_win_user != "bertrand":
                        has_foreign_path = any(
                            "\\users\\bertrand\\" in str(data.get(k, "")).lower()
                            for k in ("gsx_profile_path", "msfs_community_path", "msfs_community2024_path")
                        )
                        if has_foreign_path:
                            data["gsx_profile_path"] = self._default_gsx
                            data["msfs_community_path"] = self._default_c20
                            data["msfs_community2024_path"] = self._default_c24
                            data["sayintentions_api_key"] = self._default_si_key
                            if str(data.get("simbrief_username", "")).strip().lower() == "wildbill75":
                                data["simbrief_username"] = ""
                            needs_resave = True

                    for k, local_def in (
                        ("gsx_profile_path", self._default_gsx),
                        ("msfs_community_path", self._default_c20),
                        ("msfs_community2024_path", self._default_c24),
                    ):
                        stored_p = str(data.get(k, "")).strip()
                        if stored_p and not os.path.exists(stored_p) and local_def:
                            data[k] = local_def
                            needs_resave = True

                    # Auto-populate SayIntentions SAPI key from local SayIntentionsAI installation if blank
                    if not str(data.get("sayintentions_api_key") or "").strip() and self._default_si_key:
                        data["sayintentions_api_key"] = self._default_si_key
                        needs_resave = True

                    self.settings.update(data)
                    if needs_resave or needs_resave_af:
                        self.save()
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
