import os
import xml.etree.ElementTree as ET

class AutoStartManager:
    def __init__(self):
        self.exe_xml_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Microsoft.Limitless_8wekyb3d8bbwe", "LocalCache", "exe.xml")
        self.app_name = "GSX GateFinder"

    def get_exe_path(self):
        # We assume the exe is in the same directory or we are running the exe
        import sys
        if getattr(sys, 'frozen', False):
            return sys.executable
        return os.path.abspath(sys.argv[0])

    def enable(self):
        if not os.path.exists(self.exe_xml_path):
            # Create a basic exe.xml if it doesn't exist
            root = ET.Element("SimBase.Document", Type="SimConnect", version="1,0")
            des = ET.SubElement(root, "Descr")
            des.text = "SimConnect"
            fname = ET.SubElement(root, "Filename")
            fname.text = "SimConnect.xml"
            ET.SubElement(root, "Disabled").text = "False"
        else:
            try:
                tree = ET.parse(self.exe_xml_path)
                root = tree.getroot()
            except Exception:
                return False

        # Check if already exists
        for launch in root.findall("Launch.Addon"):
            name_node = launch.find("Name")
            if name_node is not None and name_node.text == self.app_name:
                # Update path just in case
                path_node = launch.find("Path")
                if path_node is not None:
                    path_node.text = self.get_exe_path()
                # Ensure it's not disabled
                disabled_node = launch.find("Disabled")
                if disabled_node is not None:
                    disabled_node.text = "False"
                # Ensure CommandLine is set
                cmd_node = launch.find("CommandLine")
                if cmd_node is not None:
                    cmd_node.text = "--silent"
                else:
                    ET.SubElement(launch, "CommandLine").text = "--silent"
                self._save(root)
                return True

        # Add new entry
        launch = ET.SubElement(root, "Launch.Addon")
        ET.SubElement(launch, "Name").text = self.app_name
        ET.SubElement(launch, "Disabled").text = "False"
        ET.SubElement(launch, "Path").text = self.get_exe_path()
        ET.SubElement(launch, "CommandLine").text = "--silent"
        
        self._save(root)
        return True

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
                    tree = ET.ElementTree(root)
                    ET.indent(tree, space="  ", level=0)
                    tree.write(xml_p, encoding="Windows-1252", xml_declaration=True)
            except Exception as e:
                print(f"[AutoStartManager] Error cleaning {xml_p}: {e}")
                success = False

        return success
        
    def _save(self, root):
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(self.exe_xml_path, encoding="Windows-1252", xml_declaration=True)
