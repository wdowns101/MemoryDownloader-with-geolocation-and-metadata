import json
import os
import urllib.request
import subprocess
from datetime import datetime, timedelta, date

JSON_FILE = "" Path to the Snapchat JSON file you downloaded
OUTPUT_DIR = "" Where you want your videos/images to be saved

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

media_items = data.get("Saved Media", [])
existing_files = set(os.listdir(OUTPUT_DIR))


# ------------------ Parsing ------------------

def parse_datetime(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S UTC")


def parse_location(location_str):
    try:
        coords = location_str.split(":")[1].strip()
        lat, lon = map(float, coords.split(","))
        if lat == 0.0 and lon == 0.0:
            return None, None
        return lat, lon
    except Exception:
        return None, None


# ------------------ DST + Time ------------------

def nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def us_dst(year):
    return nth_weekday(year, 3, 6, 2), nth_weekday(year, 11, 6, 1)


def eu_dst(year):
    return last_weekday(year, 3, 6), last_weekday(year, 10, 6)


def au_dst(year):
    return nth_weekday(year, 10, 6, 1), nth_weekday(year + 1, 4, 6, 1)


def longitude_offset(lon):
    return int(round(lon / 15))


def is_dst(dt, lon):
    y = dt.year
    d = dt.date()

    if -170 <= lon <= -50:
        start, end = us_dst(y)
        return start <= d < end

    if -25 <= lon <= 45:
        start, end = eu_dst(y)
        return start <= d < end

    if 110 <= lon <= 180:
        start, end = au_dst(y)
        return d >= start or d < end

    return False


def convert_utc_global(dt_utc, lat, lon):
    if lon is None:
        return dt_utc

    offset = longitude_offset(lon)
    dt_local = dt_utc + timedelta(hours=offset)

    if is_dst(dt_local, lon):
        dt_local += timedelta(hours=1)

    return dt_local


# ------------------ File Handling ------------------

FILETYPE_EXT_MAP = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "heic": ".heic",
    "png": ".png",
    "webp": ".webp",
    "mp4": ".mp4",
    "mov": ".mov"
}


def detect_file_type(filepath):
    try:
        return subprocess.check_output(
            ["exiftool", "-FileType", "-s3", filepath],
            stderr=subprocess.DEVNULL
        ).decode().strip().lower()
    except Exception:
        return None


def repair_mp4(filepath):
    fixed = filepath.replace(".mp4", "_fixed.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-err_detect", "ignore_err",
            "-i", filepath,
            "-c", "copy",
            "-movflags", "+faststart",
            fixed
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    os.replace(fixed, filepath)


# ------------------ Metadata ------------------

def apply_metadata(filepath, dt, lat=None, lon=None):
    is_video = filepath.lower().endswith(".mp4")
    iso = f"{lat:+.6f}{lon:+.6f}/" if lat is not None else None

    cmd = [
        "exiftool",
        "-overwrite_original",
        "-api", "QuickTimeUTC",
        f"-CreateDate={dt.strftime('%Y:%m:%d %H:%M:%S')}",
        f"-ModifyDate={dt.strftime('%Y:%m:%d %H:%M:%S')}",
    ]

    if not is_video:
        cmd.append(f"-DateTimeOriginal={dt.strftime('%Y:%m:%d %H:%M:%S')}")

    if lat is not None and lon is not None:
        if is_video:
            cmd.extend([
                f"-QuickTime:LocationISO6709={iso}",
                f"-Keys:LocationISO6709={iso}",
                f"-Keys:GPSCoordinates={lat},{lon}",
            ])
        else:
            cmd.extend([
                f"-GPSLatitude={abs(lat)}",
                f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
                f"-GPSLongitude={abs(lon)}",
                f"-GPSLongitudeRef={'E' if lon >= 0 else 'W'}",
            ])

    cmd.append(filepath)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ts = dt.timestamp()
    os.utime(filepath, (ts, ts))


# ------------------ Main Loop ------------------

for i, item in enumerate(media_items, start=1):
    base_name = f"{i:05d}"
    temp_path = os.path.join(OUTPUT_DIR, base_name)

    url = item.get("Media Download Url")
    if not url:
        continue

    lat, lon = parse_location(item.get("Location", ""))
    dt_utc = parse_datetime(item.get("Date"))
    dt_local = convert_utc_global(dt_utc, lat, lon)

    print(f"Downloading {base_name}")
    urllib.request.urlretrieve(url, temp_path)

    filetype = detect_file_type(temp_path)
    ext = FILETYPE_EXT_MAP.get(filetype, ".bin")
    final_path = temp_path + ext
    os.rename(temp_path, final_path)

    if final_path.endswith(".mp4"):
        repair_mp4(final_path)

    apply_metadata(final_path, dt_local, lat, lon)

print("✅ All Snapchat memories downloaded, repaired, and fully tagged")
