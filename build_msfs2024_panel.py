import os
import shutil
import subprocess

base_dir = r"D:\GateFinder_New\MSFS_Package\wildbill75-gsx-gatefinder-compiled"
if os.path.exists(base_dir):
    shutil.rmtree(base_dir)

os.makedirs(base_dir)

# Create the project structure
build_dir = os.path.join(base_dir, "Build")
os.makedirs(build_dir)

packages_dir = os.path.join(base_dir, "Packages")
os.makedirs(packages_dir)

pkg_sources_dir = os.path.join(base_dir, "PackageSources")
os.makedirs(pkg_sources_dir)

# 1. Main Project XML
project_xml = """<Project Version="2" Name="wildbill75-gsx-gatefinder" FolderName="Packages">
	<OutputDirectory>.</OutputDirectory>
	<TemporaryOutputDirectory>_Temp</TemporaryOutputDirectory>
	<Packages>
		<Package>PackageDefinitions\\wildbill75-gsx-gatefinder.xml</Package>
	</Packages>
</Project>"""
with open(os.path.join(base_dir, "wildbill75-gsx-gatefinder.xml"), "w") as f:
    f.write(project_xml)

# 2. Package Definition
pkg_def_dir = os.path.join(base_dir, "PackageDefinitions")
os.makedirs(pkg_def_dir)
pkg_def_xml = """<AssetPackage Name="wildbill75-gsx-gatefinder" Version="2.0.0">
	<ItemSettings>
		<ContentType>UI</ContentType>
		<Title>GSX Gate Finder</Title>
		<Manufacturer>wildbill75</Manufacturer>
		<Creator>wildbill75</Creator>
	</ItemSettings>
	<Flags>
		<VisibleInStore>false</VisibleInStore>
		<CanBeReferenced>false</CanBeReferenced>
	</Flags>
	<AssetGroups>
		<AssetGroup Name="InGamePanels">
			<Type>SPB</Type>
			<Flags>
				<FSXCompatibility>false</FSXCompatibility>
			</Flags>
			<AssetDir>PackageSources\\InGamePanels\\</AssetDir>
			<OutputDir>InGamePanels\\</OutputDir>
		</AssetGroup>
        <AssetGroup Name="html_ui">
			<Type>BGL</Type>
			<Flags>
				<FSXCompatibility>false</FSXCompatibility>
			</Flags>
			<AssetDir>PackageSources\\html_ui\\</AssetDir>
			<OutputDir>html_ui\\</OutputDir>
		</AssetGroup>
	</AssetGroups>
</AssetPackage>"""
with open(os.path.join(pkg_def_dir, "wildbill75-gsx-gatefinder.xml"), "w") as f:
    f.write(pkg_def_xml)

# 3. Package Sources
# InGamePanels
igp_dir = os.path.join(pkg_sources_dir, "InGamePanels")
os.makedirs(igp_dir)
igp_xml = """<?xml version="1.0" encoding="Windows-1252"?>
<SimBase.Document Type="InGamePanels" version="1,0">
  <Filename>GSXGateFinder.spb</Filename>
  <InGamePanels.InGamePanelDefinition id="GSXGateFinderPanel" Name="GSX Gate Finder" url="html_ui/InGamePanels/GSXGateFinder/GSXGateFinder.html" resizeDirections="Both" minWidth="600" minHeight="400" defaultWidth="800" defaultHeight="600" defaultTop="100" defaultRight="100" icon="html_ui/Icons/toolbar/GSXGateFinder.svg" buttonVisible="true">
  </InGamePanels.InGamePanelDefinition>
</SimBase.Document>"""
with open(os.path.join(igp_dir, "GSXGateFinder.xml"), "w") as f:
    f.write(igp_xml)

# Copy the HTML/JS/CSS from our uncompiled folder
import shutil
old_base = r"D:\GateFinder_New\MSFS_Package\wildbill75-gsx-gatefinder"
shutil.copytree(os.path.join(old_base, "html_ui"), os.path.join(pkg_sources_dir, "html_ui"))

print("Project generated. Running fspackagetool...")
# Compile
fspackagetool = r"C:\MSFS 2024 SDK\Tools\bin\fspackagetool.exe"
cmd = f'"{fspackagetool}" "{os.path.join(base_dir, "wildbill75-gsx-gatefinder.xml")}"'
print(cmd)
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("ERRORS:")
    print(result.stderr)
