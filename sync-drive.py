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

6. Open your Google Drive and navigate to your UTSAV 2026 folder
7. The folder ID is the long string in the URL:
   drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz  ← this part
8. Paste it into ROOT_FOLDER_ID below

9. Make sure the UTSAV folder (and all sub-folders) are shared:
   Right-click → Share → "Anyone with the link" → Viewer

10. Run: python sync-drive.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPECTED DRIVE FOLDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UTSAV 2026/                        ← ROOT_FOLDER_ID points here
├── Day 1 — Inauguration/
│   ├── IMG_001.jpg
│   ├── IMG_002.jpg
│   └── ...
├── Day 2 — Cultural Performances/
│   └── ...
├── Day 3 — Grand Finale/
│   └── ...
└── Behind the Scenes/
    └── ...

Re-run this script any time you add new photos to Drive.
The site will automatically show the updated gallery.

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

OUTPUT_FILE       = "photos-manifest.json"
FEST_NAME         = "UTSAV 2026"
IMAGE_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".bmp", ".tiff"}
DRIVE_API         = "https://www.googleapis.com/drive/v3"


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


def photo_entry(file):
    fid = file["id"]
    return {
        "id":       fid,
        "name":     file["name"],
        "thumbUrl": f"https://drive.google.com/thumbnail?id={fid}&sz=w600",
        "fullUrl":  f"https://drive.google.com/uc?export=view&id={fid}",
    }


def main():
    # ── Sanity checks ──────────────────────────────────────────────
    if "YOUR_GOOGLE_API_KEY_HERE" in API_KEY:
        print("❌  Please set your API_KEY in sync-drive.py and try again.")
        print("    See the setup instructions at the top of this file.")
        sys.exit(1)

    if "YOUR_ROOT_FOLDER_ID_HERE" in ROOT_FOLDER_ID:
        print("❌  Please set your ROOT_FOLDER_ID in sync-drive.py and try again.")
        print("    It's the long ID in the Drive URL of your UTSAV 2026 folder.")
        sys.exit(1)

    print(f"🔄  Syncing '{FEST_NAME}' from Google Drive...")
    print(f"    Root folder: {ROOT_FOLDER_ID}\n")

    # ── List sub-folders ───────────────────────────────────────────
    folders = drive_list(
        ROOT_FOLDER_ID,
        mime_filter="application/vnd.google-apps.folder"
    )

    if not folders:
        print("⚠️   No sub-folders found inside your root folder.")
        print("     Make sure your structure looks like:")
        print("       UTSAV 2026/")
        print("       ├── Day 1 — Inauguration/")
        print("       ├── Day 2 — Cultural/")
        print("       └── Day 3 — Finale/")
        sys.exit(1)

    print(f"    Found {len(folders)} album folder(s):\n")

    albums = []
    total_photos = 0

    for folder in folders:
        fname = folder["name"]
        fid   = folder["id"]
        print(f"  📁  {fname}")

        # List all files in this sub-folder
        files  = drive_list(fid)
        images = [f for f in files if is_image(f["name"])]

        if not images:
            print(f"       ⚠️  No images found — skipping.\n")
            continue

        total_photos += len(images)
        print(f"       ✅  {len(images)} images found\n")

        cover = images[0]
        album = {
            "id":           fid,
            "name":         fname,
            "date":         "",  # e.g. "April 10, 2026" — set manually if you like
            "coverPhotoId": cover["id"],
            "coverUrl":     f"https://drive.google.com/thumbnail?id={cover['id']}&sz=w800",
            "photos":       [photo_entry(img) for img in images],
        }
        albums.append(album)

    if not albums:
        print("⚠️   No albums with photos were found. Nothing written.")
        sys.exit(1)

    # ── Write manifest ─────────────────────────────────────────────
    manifest = {
        "festName":    FEST_NAME,
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "totalPhotos": total_photos,
        "albums":      albums,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("─" * 50)
    print(f"✅  Done!  →  {OUTPUT_FILE}")
    print(f"   Albums      : {len(albums)}")
    print(f"   Total photos: {total_photos}")
    print()
    print("💡  Next steps:")
    print(f"   1. Open {OUTPUT_FILE} and fill in the 'date' field for each album")
    print(f"   2. Put index.html + {OUTPUT_FILE} in the same folder")
    print(f"   3. Deploy to Vercel (vercel.com) or GitHub Pages — both are free")
    print(f"   4. Re-run this script whenever you add more photos to Drive")


if __name__ == "__main__":
    main()
