import requests
import pandas as pd
import os

# --- Settings ---
STATION = "05BH004"      # Bow River at Calgary
LAT = 51.05              # Calgary latitude
LON = -114.05            # Calgary longitude
OUTPUT_FILE = "data/bow_river_weather.csv"

# --- Step 1: Download river data ---
print("Getting river data...")
url = "https://api.weather.gc.ca/collections/hydrometric-realtime/items"
params = {"STATION_NUMBER": STATION, "f": "json", "limit": 2000, "sortby": "-DATETIME"}
response = requests.get(url, params=params)
data = response.json()

# Take the useful part of the data and put it in a table
rows = []
for item in data["features"]:
    rows.append(item["properties"])
river = pd.DataFrame(rows)

# Make a clean time column, rounded down to the hour
river["time"] = pd.to_datetime(river["DATETIME"], utc=True).dt.floor("h")

# Keep only the columns we need, one row per hour
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
response = requests.get(url, params=params)
weather = pd.DataFrame(response.json()["hourly"])
weather["time"] = pd.to_datetime(weather["time"], utc=True)

# --- Step 3: Combine river and weather by time ---
combined = river.merge(weather, on="time", how="left")

# --- Step 4: Add to old data if the file already exists ---
if os.path.exists(OUTPUT_FILE):
    old = pd.read_csv(OUTPUT_FILE)
    old["time"] = pd.to_datetime(old["time"], utc=True)
    combined = pd.concat([old, combined])

# Remove duplicate hours and sort by time
combined = combined.drop_duplicates(subset="time", keep="last")
combined = combined.sort_values("time")

# --- Step 5: Save ---
combined.to_csv(OUTPUT_FILE, index=False)
print("Done! Saved", len(combined), "rows to", OUTPUT_FILE)
