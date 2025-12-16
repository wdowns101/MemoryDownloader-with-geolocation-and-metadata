import json
import os
import urllib.request
import subprocess
from datetime import datetime, timedelta, date

JSON_FILE = "" #Filepath for your downloaded file 
OUTPUT_DIR = "" #Filepath for your desired location for the files

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


# ------------------ DST Rules ------------------

def nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def last_weekday(year, month, weekday):
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def us_dst(year):
    start = nth_weekday(year, 3, 6, 2)    # 2nd Sunday March
    end = nth_weekday(year, 11, 6, 1)     # 1st Sunday Nov
    return start, end


def eu_dst(year):
    start = last_weekday(year, 3, 6)      # Last Sunday March
    end = last_weekday(year, 10, 6)       # Last Sunday Oct
    return start, end


def au_dst(year):
    start = nth_weekday(year, 10, 6, 1)    # 1st Sunday Oct
    end = nth_weekday(year + 1, 4, 6, 1)   # 1st Sunday Apr
    return start, end


# ------------------ Time Conversion ------------------

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


# ------------------ Metadata ------------------

def apply_metadata(filepath, dt, lat=None, lon=None):
    is_video = filepath.lower().endswith(".mp4")

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
        iso = f"{lat:+.6f}{lon:+.6f}/"

        if is_video:
            # Write GPS to ALL atoms Photos.app may read
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
    media_type = item.get("Media Type", "").lower()
    ext = ".mp4" if media_type == "video" else ".jpg"
    filename = f"{i:05d}{ext}"

    if filename in existing_files:
        continue

    url = item.get("Media Download Url")
    if not url:
        continue

    lat, lon = parse_location(item.get("Location", ""))
    dt_utc = parse_datetime(item.get("Date"))

    dt_local = convert_utc_global(dt_utc, lat, lon)

    filepath = os.path.join(OUTPUT_DIR, filename)
    print(f"Downloading {filename}")

    urllib.request.urlretrieve(url, filepath)
    apply_metadata(filepath, dt_local, lat, lon)

print("All Snapchat memories downloaded with global local-time metadata ✅")

