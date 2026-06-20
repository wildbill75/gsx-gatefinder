import os
import json
import time

pkg_dir = r"D:\GateFinder_New\MSFS_Package\wildbill75-gsx-gatefinder"
layout_path = os.path.join(pkg_dir, "layout.json")

def get_file_time(path):
    # MSFS layout uses Windows file time (100-nanosecond intervals since Jan 1, 1601)
    # 11644473600 is seconds between 1601 and 1970
    return int((os.path.getmtime(path) + 11644473600) * 10000000)

content = []
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        if f in ['layout.json', 'manifest.json']:
            continue
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, pkg_dir).replace('\\', '/')
        content.append({
            "path": rel_path,
            "size": os.path.getsize(full_path),
            "date": get_file_time(full_path)
        })

with open(layout_path, "w", encoding="utf-8") as f:
    json.dump({"content": content}, f, indent=4)

print("layout.json updated successfully!")
