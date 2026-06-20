import os
import shutil
import json

base_dir = r"D:\GateFinder_New\MSFS_Package\wildbill75-gsx-gatefinder"
if os.path.exists(base_dir):
    shutil.rmtree(base_dir)

os.makedirs(base_dir)

# 1. manifest.json
manifest = {
  "dependencies": [],
  "content_type": "UI",
  "title": "GSX Gate Finder",
  "manufacturer": "",
  "creator": "wildbill75",
  "package_version": "2.2.0",
  "minimum_game_version": "1.0.0",
  "release_notes": {
    "neutral": {
      "LastUpdate": "GSX Gate Finder MSFS Panel Release",
      "OlderHistory": ""
    }
  }
}
with open(os.path.join(base_dir, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

# 2. InGamePanels/InGamePanel_CustomPanel.spb
igp_dir = os.path.join(base_dir, "InGamePanels")
os.makedirs(igp_dir)

template_spb = r"D:\GateFinder_New\MSFS_Template\msfs2020-toolbar-window-template-master\maximus-ingamepanels-custom\InGamePanels\maximus-ingamepanels-custom.spb"
shutil.copy(template_spb, os.path.join(igp_dir, "InGamePanel_CustomPanel.spb"))

# 3. html_UI/ingamePanels/CustomPanel/
html_dir = os.path.join(base_dir, "html_UI", "ingamePanels", "CustomPanel")
os.makedirs(html_dir)

# Read the HTML, CSS, JS from the old V2 package
old_base = r"D:\GateFinder\MSFS_Package\wildbill75-gsx-gatefinder"
old_html = r"D:\GateFinder\MSFS_Package\wildbill75-gsx-gatefinder\html_ui\InGamePanels\GSXGateFinder\GSXGateFinder.html"
old_css = r"D:\GateFinder\MSFS_Package\wildbill75-gsx-gatefinder\html_ui\InGamePanels\GSXGateFinder\GSXGateFinder.css"
old_js = r"D:\GateFinder\MSFS_Package\wildbill75-gsx-gatefinder\html_ui\InGamePanels\GSXGateFinder\GSXGateFinder.js"

# Copy them, but rename them to CustomPanel.html, CustomPanel.css, CustomPanel.js
with open(old_html, "r", encoding="utf-8") as f:
    html_content = f.read()

# Replace references in HTML
html_content = html_content.replace("GSXGateFinder.css", "CustomPanel.css")
html_content = html_content.replace("GSXGateFinder.js", "CustomPanel.js")

with open(os.path.join(html_dir, "CustomPanel.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

shutil.copy(old_css, os.path.join(html_dir, "CustomPanel.css"))

# Modify JS so the custom element matches the HTML
with open(old_js, "r", encoding="utf-8") as f:
    js_content = f.read()

# The original HTML uses <gsx-gatefinder-panel> so we leave it as is, because CustomPanel.html still has <gsx-gatefinder-panel>.
with open(os.path.join(html_dir, "CustomPanel.js"), "w", encoding="utf-8") as f:
    f.write(js_content)

# 4. Icon
# The SPB expects "ICON_TOOLBAR_MAXIMUS_CUSTOM_PANEL" which translates to an SVG. Wait, if it translates to an SVG, we need to supply the SVG at the path expected by the SPB?
# No, MSFS maps the icon ID if it's defined in an XML somewhere else.
# But wait, in the template, where is ICON_TOOLBAR_MAXIMUS_CUSTOM_PANEL defined?
# Usually, if it's an ID, MSFS uses it directly or it's hardcoded to a standard icon. We can just skip custom icons for now.

# Wait, let's look at the template's SVG paths.
shutil.copytree(os.path.join(old_base, "html_ui", "Icons"), os.path.join(base_dir, "html_UI", "Icons"))

# 5. layout.json
layout_entries = []
for root, _, files in os.walk(base_dir):
    for file in files:
        if file == "layout.json": continue
        filepath = os.path.join(root, file)
        rel_path = os.path.relpath(filepath, base_dir).replace("\\", "/")
        size = os.path.getsize(filepath)
        date = int(os.path.getmtime(filepath)) * 10000000 + 116444736000000000 # Windows file time
        layout_entries.append({
            "path": rel_path,
            "size": size,
            "date": date
        })

layout = {"content": layout_entries}
with open(os.path.join(base_dir, "layout.json"), "w") as f:
    json.dump(layout, f, indent=2)

print("Hack MSFS Panel Built successfully in D:\\GateFinder_New\\MSFS_Package\\wildbill75-gsx-gatefinder")
