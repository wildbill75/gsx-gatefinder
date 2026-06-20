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

    def disable(self):
        if not os.path.exists(self.exe_xml_path):
            return True
            
        try:
            tree = ET.parse(self.exe_xml_path)
            root = tree.getroot()
        except Exception:
            return False

        modified = False
        for launch in root.findall("Launch.Addon"):
            name_node = launch.find("Name")
            if name_node is not None and name_node.text == self.app_name:
                root.remove(launch)
                modified = True
                
        if modified:
            self._save(root)
        return True
        
    def _save(self, root):
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(self.exe_xml_path, encoding="Windows-1252", xml_declaration=True)
