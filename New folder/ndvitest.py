import ee
import pandas as pd
import time
from geopy.geocoders import Nominatim

# =========================
# 1. Khởi tạo Earth Engine
# =========================
ee.Initialize(project='gen-lang-client-0272496285')
print("✅ Đã kết nối Google Earth Engine")

# =========================
# 2. Đọc CSV
# =========================
df = pd.read_csv("data_season.csv")
df.columns = df.columns.str.strip()

# =========================
# 3. Geocode Location → lat/lon
# =========================
geolocator = Nominatim(user_agent="ndvi_project")

location_cache = {}
lat_list = []
lon_list = []

unique_locations = df["Location"].dropna().unique()

print("🌍 Đang geocode Location...")

for loc in unique_locations:
    try:
        geo = geolocator.geocode(loc)
        if geo:
            location_cache[loc] = (geo.latitude, geo.longitude)
            print(f"✔ {loc} → ({geo.latitude}, {geo.longitude})")
        else:
            location_cache[loc] = (None, None)
            print(f"❌ Không tìm thấy tọa độ cho {loc}")
        time.sleep(1)  # tránh bị block
    except Exception as e:
        print(f"⚠️ Lỗi geocode {loc}: {e}")
        location_cache[loc] = (None, None)

df["lat"] = df["Location"].map(lambda x: location_cache[x][0])
df["lon"] = df["Location"].map(lambda x: location_cache[x][1])

# =========================
# 4. Map Season → date
# =========================
def season_to_dates(year, season):
    season = season.lower()
    if season == "kharif":
        return f"{year}-06-01", f"{year}-10-31"
    elif season == "rabi":
        return f"{year}-10-01", f"{year+1}-03-31"
    elif season == "zaid":
        return f"{year}-03-01", f"{year}-06-30"
    else:
        return None, None

# =========================
# 5. Hàm lấy NDVI
# =========================
def get_ndvi(lat, lon, start_date, end_date):
    try:
        if pd.isna(lat) or pd.isna(lon):
            return None

        point = ee.Geometry.Point([lon, lat])

        collection = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(point)
            .filterDate(start_date, end_date)
        )

        if collection.size().getInfo() == 0:
            return None

        ndvi_img = collection.select("NDVI").mean()

        value = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=250,
            maxPixels=1e9
        ).getInfo()

        return value["NDVI"] * 0.0001 if value and "NDVI" in value else None

    except Exception as e:
        print("⚠️ Lỗi NDVI:", e)
        return None

# =========================
# 6. Tính NDVI cho từng dòng
# =========================
ndvi_values = []

print("📡 Đang trích NDVI...")

for i, row in df.iterrows():
    start_date, end_date = season_to_dates(row["Year"], row["Season"])

    if start_date is None:
        ndvi_values.append(None)
        continue

    ndvi = get_ndvi(
        lat=row["lat"],
        lon=row["lon"],
        start_date=start_date,
        end_date=end_date
    )

    ndvi_values.append(ndvi)
    print(f"✔ {i+1}/{len(df)} NDVI = {ndvi}")

df["NDVI"] = ndvi_values

# =========================
# 7. Xuất CSV mới
# =========================
df.to_csv("data_season_with_ndvi.csv", index=False)
print("🎉 Đã tạo file data_season_with_ndvi.csv")
