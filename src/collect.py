import requests
import pandas as pd
import os
import time

# --- Settings ---
STATION = "05BH004"      # Bow River at Calgary
LAT = 51.05
LON = -114.05
OUTPUT_FILE = "data/bow_river_weather.csv"

def get_with_retry(url, params, tries=3):
    """Try a web request up to 3 times, waiting 30 seconds each time."""
    for attempt in range(tries):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            print("Attempt", attempt + 1, "failed:", error)
            time.sleep(5)
    return None

# --- Step 1: Download river data ---
print("Getting river data...")
url = "https://api.weather.gc.ca/collections/hydrometric-realtime/items"
params = {"STATION_NUMBER": STATION, "f": "json", "limit": 2000, "sortby": "-DATETIME"}
response = get_with_retry(url, params)
if response is None:
    raise SystemExit("Could not get river data. Stopping.")

rows = []
for item in response.json()["features"]:
    rows.append(item["properties"])
river = pd.DataFrame(rows)
river["time"] = pd.to_datetime(river["DATETIME"], utc=True).dt.floor("h")
river = river[["time", "DISCHARGE", "LEVEL"]]
river = river.groupby("time").mean().reset_index()

# --- Step 2: Download weather data ---
print("Getting weather data...")
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT,
    "longitude": LON,
    "hourly": "temperature_2m,precipitation,snowfall,wind_speed_10m",
    "past_days": 7,
    "forecast_days": 1,
    "timezone": "UTC",
}
response = get_with_retry(url, params)
if response is None:
    print("Weather failed. Saving river data only this time.")
    weather = pd.DataFrame({
        "time": pd.to_datetime([], utc=True),
        "temperature_2m": [], "precipitation": [],
        "snowfall": [], "wind_speed_10m": [],
    })
else:
    weather = pd.DataFrame(response.json()["hourly"])
    weather["time"] = pd.to_datetime(weather["time"], utc=True)

# --- Step 3: Combine river and weather by time ---
combined = river.merge(weather, on="time", how="left")

# --- Step 4: Add to old data if the file already exists ---
if os.path.exists(OUTPUT_FILE):
    old = pd.read_csv(OUTPUT_FILE)
    old["time"] = pd.to_datetime(old["time"], utc=True)
    combined = pd.concat([old, combined])

# One row per hour; keep the newest value, but never replace a value with an empty one
combined = combined.groupby("time").last().reset_index()

# --- Step 5: Save ---
combined.to_csv(OUTPUT_FILE, index=False)
print("Done! Saved", len(combined), "rows to", OUTPUT_FILE)
