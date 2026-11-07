import os
import xml.etree.ElementTree as ET

class AutoStartManager:
    def __init__(self):
        self.exe_xml_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "exe.xml")
        self.app_name = "GateFinder"

    def get_exe_path(self):
        # Prefer the frozen executable or GateFinder.exe in project root if running from source
        import sys
        if getattr(sys, 'frozen', False):
            return os.path.abspath(sys.executable)
        root_exe = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "GateFinder.exe"))
        if os.path.isfile(root_exe):
            return root_exe
        return os.path.abspath(sys.argv[0])

    def _detect_encoding(self, xml_path: str) -> str:
        if os.path.exists(xml_path):
            try:
                with open(xml_path, "rb") as f:
                    head = f.read(200).decode("ascii", errors="ignore").lower()
                if "utf-8" in head:
                    return "utf-8"
            except Exception:
                pass
        return "Windows-1252"

    def is_enabled(self) -> bool:
        all_paths = self.get_all_exe_xml_paths()
        if not all_paths:
            return False
        target_exe = self.get_exe_path().lower()
        for xml_p in all_paths:
            try:
                tree = ET.parse(xml_p)
                root = tree.getroot()
                found = False
                for launch in root.findall("Launch.Addon"):
                    name_node = launch.find("Name")
                    path_node = launch.find("Path")
                    dis_node = launch.find("Disabled")
                    n_txt = name_node.text.strip() if (name_node is not None and name_node.text) else ""
                    p_txt = path_node.text.strip().lower() if (path_node is not None and path_node.text) else ""
                    d_txt = dis_node.text.strip().lower() if (dis_node is not None and dis_node.text) else "false"
                    if (n_txt in (self.app_name, "GSX GateFinder", "GateFinder") or "gatefinder.exe" in p_txt):
                        if d_txt == "false" and p_txt == target_exe:
                            found = True
                            break
                if not found:
                    return False
            except Exception:
                return False
        return True

    def enable(self):
        all_paths = self.get_all_exe_xml_paths()
        if not all_paths:
            all_paths = [self.exe_xml_path]

        any_ok = False
        exe_path_val = self.get_exe_path()
        for xml_p in all_paths:
            enc = self._detect_encoding(xml_p)
            if not os.path.exists(xml_p):
                os.makedirs(os.path.dirname(xml_p), exist_ok=True)
                root = ET.Element("SimBase.Document", Type="SimConnect", version="1,0")
                des = ET.SubElement(root, "Descr")
                des.text = "SimConnect"
                fname = ET.SubElement(root, "Filename")
                fname.text = "SimConnect.xml"
                ET.SubElement(root, "Disabled").text = "False"
            else:
                try:
                    tree = ET.parse(xml_p)
                    root = tree.getroot()
                except Exception:
                    continue

            updated_existing = False
            for launch in root.findall("Launch.Addon"):
                name_node = launch.find("Name")
                path_node = launch.find("Path")
                n_txt = name_node.text.strip() if (name_node is not None and name_node.text) else ""
                p_txt = path_node.text.strip().lower() if (path_node is not None and path_node.text) else ""
                if n_txt in (self.app_name, "GSX GateFinder", "GateFinder") or "gatefinder.exe" in p_txt:
                    if name_node is not None:
                        name_node.text = self.app_name
                    else:
                        ET.SubElement(launch, "Name").text = self.app_name
                    if path_node is not None:
                        path_node.text = exe_path_val
                    else:
                        ET.SubElement(launch, "Path").text = exe_path_val
                    disabled_node = launch.find("Disabled")
                    if disabled_node is not None:
                        disabled_node.text = "False"
                    else:
                        ET.SubElement(launch, "Disabled").text = "False"
                    cmd_node = launch.find("CommandLine")
                    if cmd_node is not None:
                        cmd_node.text = "--silent"
                    else:
                        ET.SubElement(launch, "CommandLine").text = "--silent"
                    updated_existing = True
                    break

            if not updated_existing:
                launch = ET.SubElement(root, "Launch.Addon")
                ET.SubElement(launch, "Name").text = self.app_name
                ET.SubElement(launch, "Disabled").text = "False"
                ET.SubElement(launch, "Path").text = exe_path_val
                ET.SubElement(launch, "CommandLine").text = "--silent"

            try:
                self._save(root, xml_p, encoding=enc)
                any_ok = True
            except Exception as e:
                print(f"[AutoStartManager] Error saving {xml_p}: {e}")

        return any_ok

    def get_all_exe_xml_paths(self):
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        candidates = [
            # MSFS 2024 Store
            os.path.join(local_appdata, "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "exe.xml"),
            # MSFS 2024 Steam
            os.path.join(appdata, "Microsoft Flight Simulator 2024", "exe.xml"),
            # MSFS 2020 Store
            os.path.join(local_appdata, "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "exe.xml"),
            # MSFS 2020 Steam
            os.path.join(appdata, "Microsoft Flight Simulator", "exe.xml"),
        ]
        return [p for p in candidates if os.path.exists(p)]

    def disable(self):
        all_paths = self.get_all_exe_xml_paths()
        if not all_paths and os.path.exists(self.exe_xml_path):
            all_paths = [self.exe_xml_path]

        success = True
        for xml_p in all_paths:
            try:
                tree = ET.parse(xml_p)
                root = tree.getroot()
                modified = False
                for launch in list(root.findall("Launch.Addon")):
                    name_node = launch.find("Name")
                    path_node = launch.find("Path")
                    name_text = name_node.text.strip() if (name_node is not None and name_node.text) else ""
                    path_text = path_node.text.strip().lower() if (path_node is not None and path_node.text) else ""

                    is_match = (
                        name_text in (self.app_name, "GSX GateFinder", "GateFinder") or
                        "gatefinder.exe" in path_text
                    )
                    if is_match:
                        root.remove(launch)
                        modified = True

                if modified:
                    enc = self._detect_encoding(xml_p)
                    self._save(root, xml_p, encoding=enc)
            except Exception as e:
                print(f"[AutoStartManager] Error cleaning {xml_p}: {e}")
                success = False

        return success
        
    def _save(self, root, xml_path=None, encoding="Windows-1252"):
        target = xml_path or self.exe_xml_path
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(target, encoding=encoding, xml_declaration=True)
