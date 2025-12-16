import json
import os
import urllib.request
import subprocess
from datetime import datetime

JSON_FILE = "/Users/willdowns/Downloads/Miscelaneous/mydata~1765917007368/json/memories_history.json"
OUTPUT_DIR = "/Volumes/Photos-Videos/SnapchatT1"

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

media_items = data.get("Saved Media", [])
existing_files = set(os.listdir(OUTPUT_DIR))


def parse_datetime(date_str):
    # "2025-12-14 01:28:53 UTC"
    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S UTC")


def parse_location(location_str):
    # "Latitude, Longitude: 38.730972, -77.27732"
    try:
        coords = location_str.split(":")[1].strip()
        lat, lon = map(float, coords.split(","))
        if lat == 0.0 and lon == 0.0:
            return None, None
        return lat, lon
    except Exception:
        return None, None


def apply_metadata(filepath, dt, lat=None, lon=None):
    exif_cmd = [
        "exiftool",
        "-overwrite_original",
        f"-DateTimeOriginal={dt.strftime('%Y:%m:%d %H:%M:%S')}",
        f"-CreateDate={dt.strftime('%Y:%m:%d %H:%M:%S')}",
        f"-ModifyDate={dt.strftime('%Y:%m:%d %H:%M:%S')}",
    ]

    if lat is not None and lon is not None:
        exif_cmd.extend([
            f"-GPSLatitude={abs(lat)}",
            f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
            f"-GPSLongitude={abs(lon)}",
            f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
        ])

    exif_cmd.append(filepath)
    subprocess.run(exif_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Set filesystem timestamps (macOS)
    ts = dt.timestamp()
    os.utime(filepath, (ts, ts))


for i, item in enumerate(media_items, start=1):
    media_type = item.get("Media Type", "").lower()
    ext = ".mp4" if media_type == "video" else ".jpg"
    filename = f"{i:05d}{ext}"

    if filename in existing_files:
        continue

    url = item.get("Media Download Url")
    if not url:
        continue

    date_str = item.get("Date")
    location_str = item.get("Location", "")

    try:
        dt = parse_datetime(date_str)
    except Exception:
        print(f"⚠️ Invalid date for {filename}, skipping metadata")
        dt = None

    lat, lon = parse_location(location_str)

    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Downloading {filename} → Drive")

    try:
        urllib.request.urlretrieve(url, filepath)

        if dt:
            apply_metadata(filepath, dt, lat, lon)

    except Exception as e:
        print(f"❌ Failed: {e}")

print("All remaining Snapchat memories downloaded with metadata ✅")

