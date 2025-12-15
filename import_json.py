import json
import os
import urllib.request

JSON_FILE = "" # Path to the Snapchat JSON file you downloaded
OUTPUT_DIR = "" # Where you want your videos to be saved

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

media_items = data.get("Saved Media", [])

existing_files = set(os.listdir(OUTPUT_DIR))

for i, item in enumerate(media_items, start=1):
    media_type = item.get("Media Type", "").lower()
    ext = ".mp4" if media_type == "video" else ".jpg"
    filename = f"{i:05d}{ext}"

    if filename in existing_files:
        continue

    url = item.get("Media Download Url")
    if not url:
        continue

    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Downloading {filename} → GiraDrive")

    try:
        urllib.request.urlretrieve(url, filepath)
    except Exception as e:
        print(f"❌ Failed: {e}")

print("All remaining Snapchat memories downloaded ✅")
