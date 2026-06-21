import glob
import os
import json

svg_content = """<?xml version="1.0" encoding="utf-8"?>
<svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px"
	 viewBox="0 0 100 100" style="enable-background:new 0 0 100 100;" xml:space="preserve">
<g>
  <path fill="none" stroke="#FFFFFF" stroke-width="2" stroke-dasharray="6 4" d="M 50 5 L 50 95" />
  <path fill="none" stroke="#FFFFFF" stroke-width="3" d="M 35 15 L 65 15" />
  <path fill="none" stroke="#FFFFFF" stroke-width="1" d="M 20 15 L 20 90 L 80 90 L 80 15" />
  <path fill="#FFFFFF" d="M 50 20 Q 54 20 54 35 L 85 55 L 85 60 L 54 60 L 54 75 L 65 80 L 65 83 L 50 81 L 35 83 L 35 80 L 46 75 L 46 60 L 15 60 L 15 55 L 46 35 Q 46 20 50 20 Z"/>
</g>
</svg>"""

for f in glob.glob('D:/GateFinder_New/MSFS_Package/wildbill75-gsx-gatefinder/html_UI/Icons/toolbar/*.svg'):
    with open(f, 'w', encoding='utf-8') as out:
        out.write(svg_content)
        
layout_path = 'D:/GateFinder_New/MSFS_Package/wildbill75-gsx-gatefinder/layout.json'
with open(layout_path, 'r', encoding='utf-8') as f:
    d = json.load(f)

# Ensure all SVGs are in the layout
existing_paths = set(x['path'] for x in d['content'])

for svg_file in glob.glob('D:/GateFinder_New/MSFS_Package/wildbill75-gsx-gatefinder/html_UI/Icons/toolbar/*.svg'):
    rel_path = "html_UI/Icons/toolbar/" + os.path.basename(svg_file)
    if rel_path not in existing_paths:
        d['content'].append({
            "path": rel_path,
            "size": os.path.getsize(svg_file),
            "date": 134265119747186304
        })

# Update all sizes
for x in d['content']:
    abs_path = os.path.join(os.path.dirname(layout_path), x['path'])
    if os.path.exists(abs_path):
        x['size'] = os.path.getsize(abs_path)

with open(layout_path, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=4)
