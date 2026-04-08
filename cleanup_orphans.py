"""
One-time script to remove orphan files from data/uploads/ (files that have
no entry in file_metadata.json). Run this to free space immediately without
starting the full server.

  python cleanup_orphans.py

Orphans happen when the server crashes after saving a file but before
updating metadata, or if metadata was cleared/corrupted.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "config.json") as f:
    config = json.load(f)
UPLOAD_FOLDER = BASE_DIR / config["storage"]["upload_folder"]
METADATA_PATH = BASE_DIR / config["storage"]["metadata_file"]

def main():
    if not UPLOAD_FOLDER.exists():
        print("Upload folder does not exist. Nothing to clean.")
        return
    metadata = {}
    if METADATA_PATH.exists():
        with open(METADATA_PATH) as f:
            metadata = json.load(f)
    valid_names = {info["stored_name"] for info in metadata.values()}
    removed = 0
    freed = 0
    for f in list(UPLOAD_FOLDER.iterdir()):
        if f.is_file() and f.name not in valid_names:
            size = f.stat().st_size
            try:
                f.unlink()
                removed += 1
                freed += size
                print(f"Removed orphan: {f.name} ({size / (1024**3):.2f} GB)")
            except OSError as e:
                print(f"Failed to remove {f.name}: {e}")
    if removed:
        print(f"\nDone. Removed {removed} file(s), freed {freed / (1024**3):.2f} GB.")
    else:
        print("No orphan files found.")

if __name__ == "__main__":
    main()
