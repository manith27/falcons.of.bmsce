#!/usr/bin/env python3
"""
sync-drive.py — Generates photos-manifest.json from your Google Drive.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUICK SETUP (5 minutes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to https://console.cloud.google.com
2. Create a project (or use an existing one)
3. Search "Google Drive API" → Enable it
4. Go to Credentials → Create Credentials → API Key
5. Copy the key and paste it into API_KEY below

6. Open your Google Drive and navigate to your UTSAV 2026 root folder
7. The folder ID is the long string in the URL:
   drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz  ← this part
8. Paste it into ROOT_FOLDER_ID below

9. Make sure ALL folders (and sub-folders) are shared:
   Right-click → Share → "Anyone with the link" → Viewer

10. Run: python3 sync-drive.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPECTED DRIVE FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UTSAV 2026/                  ← ROOT_FOLDER_ID points here
├── Day 1/
├── Day 2/
├── Day 3/
├── Ethnic Day/
├── Moto Show/
└── Pre Utsav/
    ├── VC Meet/
    ├── Open Mic 1/
    ├── Open Mic 2/
    ├── Merch Reveal/
    ├── Jamming Session/
    └── Banner Drop/

Folder names must match exactly (case-sensitive).
Re-run this script any time you add new photos to Drive.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import sys
import requests
from datetime import datetime

# ─────────────────────────────────────────────
#  ⚙️  EDIT THESE TWO VALUES BEFORE RUNNING
# ─────────────────────────────────────────────
API_KEY        = "AIzaSyAi4GBNPitEXWu_fdzRpO8Gb99qxVqkMK0"
ROOT_FOLDER_ID = "1FdYFleiaDlyaJSBFNeF1B6xHgH93FldY"
# ─────────────────────────────────────────────

OUTPUT_FILE      = "photos-manifest.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".bmp", ".tiff"}
DRIVE_API        = "https://www.googleapis.com/drive/v3"

# Maps Drive folder names → manifest keys used by the website
TOP_LEVEL_MAP = {
    "Day 1":      "d1",
    "Day 2":      "d2",
    "Day 3":      "d3",
    "Ethnic Day": "ethnic",
    "Moto Show":  "moto",
    # "Pre Utsav" is handled specially below (nested)
}

PRE_UTSAV_MAP = {
    "VC Meet":         "pre_vc",
    "Open Mic 1":      "pre_openmic1",
    "Open Mic 2":      "pre_openmic2",
    "Merch Reveal":    "pre_merch",
    "Jamming Session": "pre_jam",
    "Banner Drop":     "pre_banner",
}


def drive_list(parent_id, mime_filter=None):
    """Paginate through a Drive folder and return all matching items."""
    items = []
    page_token = None
    query = f"'{parent_id}' in parents and trashed = false"
    if mime_filter:
        query += f" and mimeType = '{mime_filter}'"

    while True:
        params = {
            "key": API_KEY,
            "q": query,
            "fields": "nextPageToken, files(id, name, mimeType)",
            "pageSize": 1000,
            "orderBy": "name",
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            r = requests.get(f"{DRIVE_API}/files", params=params, timeout=30)
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else "?"
            if code == 403:
                print(f"\n❌  403 Forbidden — check your API key and that Drive API is enabled.")
            elif code == 404:
                print(f"\n❌  404 Not Found — check your ROOT_FOLDER_ID.")
            else:
                print(f"\n❌  HTTP {code}: {e}")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"\n❌  Network error: {e}")
            sys.exit(1)

        data = r.json()
        items.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return items


def is_image(name):
    return any(name.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


def get_photos(folder_id, _depth=0):
    """Return list of photo entries from a Drive folder, recursively scanning sub-folders."""
    items  = drive_list(folder_id)
    photos = []

    # Collect images directly in this folder
    for f in items:
        if is_image(f["name"]):
            photos.append({"id": f["id"], "name": f["name"]})

    # Recurse into any sub-folders (up to 3 levels deep)
    if _depth < 3:
        sub_folders = [f for f in items if f.get("mimeType") == "application/vnd.google-apps.folder"]
        for sub in sub_folders:
            print(f"{'         ' * (_depth+1)}📂  Sub-folder: {sub['name']}")
            photos.extend(get_photos(sub["id"], _depth + 1))

    return photos


def main():
    if "YOUR_GOOGLE_API_KEY_HERE" in API_KEY:
        print("❌  Please set your API_KEY in sync-drive.py and try again.")
        sys.exit(1)

    if "YOUR_ROOT_FOLDER_ID_HERE" in ROOT_FOLDER_ID:
        print("❌  Please set your ROOT_FOLDER_ID in sync-drive.py and try again.")
        sys.exit(1)

    print("🔄  Syncing UTSAV '26 from Google Drive...")
    print(f"    Root folder: {ROOT_FOLDER_ID}\n")

    # List all sub-folders in root
    root_folders = drive_list(ROOT_FOLDER_ID, mime_filter="application/vnd.google-apps.folder")

    if not root_folders:
        print("⚠️   No sub-folders found inside your root folder. Check the folder ID.")
        sys.exit(1)

    manifest = {}
    total_photos = 0

    for folder in root_folders:
        fname = folder["name"].strip()   # strip accidental spaces
        fid   = folder["id"]

        # ── Standard top-level albums (Day 1–3, Ethnic Day, Moto Show) ────────
        if fname in TOP_LEVEL_MAP:
            key = TOP_LEVEL_MAP[fname]
            print(f"  📁  {fname}  →  [{key}]")
            items = drive_list(fid)

            # Separate direct images from sub-folders
            direct = [{"id": f["id"], "name": f["name"]} for f in items if is_image(f["name"])]
            sub_folders = [f for f in items if f.get("mimeType") == "application/vnd.google-apps.folder"]

            if sub_folders:
                # Store sub-folder structure — merge duplicates, strip spaces, skip empty
                manifest[key] = direct
                merged = {}  # name → combined photos list
                for sub in sorted(sub_folders, key=lambda x: x["name"].strip()):
                    sname = sub["name"].strip()
                    sub_photos = get_photos(sub["id"])
                    if sname in merged:
                        merged[sname].extend(sub_photos)  # merge duplicate folders
                    else:
                        merged[sname] = sub_photos

                manifest[key + "_subs"] = []
                kept = 0
                for sname, sub_photos in merged.items():
                    if not sub_photos:
                        continue  # skip empty folders
                    sub_key = f"{key}__{sname}"
                    manifest[sub_key] = sub_photos
                    manifest[key + "_subs"].append({"key": sub_key, "name": sname})
                    total_photos += len(sub_photos)
                    kept += 1
                    print(f"       📂  {sname}  →  [{sub_key}]  ({len(sub_photos)} photos)")
                print(f"       ✅  {kept} sub-folders with photos (skipped {len(sub_folders)-kept} empty/duplicate)\n")
            else:
                photos = direct if direct else get_photos(fid)
                manifest[key] = photos
                total_photos += len(photos)
                if photos:
                    print(f"       ✅  {len(photos)} photos\n")
                else:
                    print(f"       ⚠️  Empty (no images yet)\n")

        # ── Pre Utsav — scan its sub-folders ──────────────────────────────────
        elif fname == "Pre Utsav":
            print(f"  📂  Pre Utsav  (scanning sub-folders...)")
            sub_folders = drive_list(fid, mime_filter="application/vnd.google-apps.folder")

            if not sub_folders:
                print(f"       ⚠️  No sub-folders found inside Pre Utsav\n")
                continue

            for sub in sub_folders:
                sname = sub["name"].strip()   # strip accidental spaces
                sid   = sub["id"]
                if sname in PRE_UTSAV_MAP:
                    key = PRE_UTSAV_MAP[sname]
                    print(f"       📁  {sname}  →  [{key}]")
                    photos = get_photos(sid)
                    if photos:
                        manifest[key] = photos
                        total_photos += len(photos)
                        print(f"            ✅  {len(photos)} photos")
                    else:
                        manifest[key] = []
                        print(f"            ⚠️  Empty (no images yet)")
                else:
                    print(f"       ⚠️  Unknown sub-folder '{sname}' — skipped")
            print()

        else:
            print(f"  ⚠️   Unknown folder '{fname}' — skipped\n")

    # ── Write manifest ─────────────────────────────────────────────────────────
    if not manifest:
        print("⚠️   No photos found at all. Nothing written.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("─" * 50)
    print(f"✅  Done!  →  {OUTPUT_FILE}")
    print(f"   Albums written : {len(manifest)}")
    print(f"   Total photos   : {total_photos}")
    print()
    print("💡  Next steps:")
    print(f"   1. Place {OUTPUT_FILE} alongside index.html")
    print(f"   2. Run: vercel --prod  to push the update live")
    print(f"   3. Re-run this script whenever you add more photos to Drive")


if __name__ == "__main__":
    main()
