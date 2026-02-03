import pandas as pd
import requests
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time

INPUT_FILE = "kk.csv"
OUTPUT_FILE = "kk_with_ph.csv"

SOIL_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# =========================
# Init geocoder
# =========================
geolocator = Nominatim(user_agent="bd_soil_ph_project")


# =========================
# Safe geocode function
# =========================
def get_latlon(district):
    try:
        loc = geolocator.geocode(f"{district}, Bangladesh")

        if loc is None:
            return None, None

        return float(loc.latitude), float(loc.longitude)

    except Exception as e:
        print("Geo error:", district, e)
        return None, None


# =========================
# SoilGrids pH function
# =========================
def get_soil_ph(lat, lon):

    params = {
        "lat": lat,
        "lon": lon,
        "property": "phh2o",
        "depth": "0-5cm"
    }

    try:
        r = requests.get(SOIL_URL, params=params, timeout=15)

        if r.status_code != 200:
            return None

        data = r.json()

        return data["properties"]["layers"][0]["depths"][0]["values"]["mean"]

    except Exception as e:
        print("Soil API error:", lat, lon, e)
        return None


# =========================
# Load dataset
# =========================
print("Loading data...")

df = pd.read_csv(INPUT_FILE)

# clean district column
df["District"] = df["District"].astype(str).str.strip()

districts = df["District"].unique()

print("Total districts:", len(districts))


# =========================
# Step 1 — Geocode
# =========================
coord_cache = {}

print("\nGeocoding districts...")

for d in tqdm(districts):

    lat, lon = get_latlon(d)

    if lat is None:
        print("Geo FAIL:", d)
        continue

    coord_cache[d] = (lat, lon)

    time.sleep(1.1)   # tránh rate limit


# =========================
# Step 2 — Soil pH query
# =========================
ph_cache = {}

print("\nFetching soil pH...")

for d, (lat, lon) in tqdm(coord_cache.items()):

    ph = get_soil_ph(lat, lon)
    ph_cache[d] = ph

    time.sleep(0.4)


# =========================
# Step 3 — Join back
# =========================

df["soil_ph"] = df["District"].map(ph_cache)

# =========================
# Save
# =========================

df.to_csv(OUTPUT_FILE, index=False)

print("\nDONE ✅")
print("Saved file:", OUTPUT_FILE)

# =========================
# Report missing
# =========================

missing = df[df["soil_ph"].isna()]["District"].unique()

if len(missing) > 0:
    print("\nDistrict missing soil_ph:")
    for m in missing:
        print("-", m)
else:
    print("\nAll districts mapped successfully")
