import requests
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import time
import os

# =========================
# 1. ĐỌC FILE
# =========================
file_path = "data_season.csv"

if not os.path.exists(file_path):
    print(f"❌ Không tìm thấy file: {file_path}")
    print(f"📁 Thư mục hiện tại: {os.getcwd()}")
    exit()

df_original = pd.read_csv(file_path)
print("✅ Đã đọc file thành công!")

# =========================
# 2. LẤY TỌA ĐỘ
# =========================
unique_locations = df_original['Location'].dropna().unique()
df_geo = pd.DataFrame(unique_locations, columns=['Location'])

geolocator = Nominatim(user_agent="agri_data_expert_v4")

def get_lat_lon(loc):
    try:
        full_address = f"{loc}, Karnataka, India"
        location = geolocator.geocode(full_address, timeout=10)
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return np.nan, np.nan

print(f"🌍 Đang lấy tọa độ cho {len(df_geo)} địa điểm...")
df_geo[['lat', 'lon']] = df_geo['Location'].apply(
    lambda x: pd.Series(get_lat_lon(x))
)

# =========================
# 3. HÀM AN TOÀN CHIA
# =========================
def safe_divide(value, divisor=10):
    return value / divisor if value is not None else np.nan

# =========================
# 4. LẤY DỮ LIỆU ĐẤT (FIX LỖI)
# =========================
def get_soil_data(lat, lon):
    if pd.isna(lat) or pd.isna(lon):
        return {'N': np.nan, 'pH': np.nan, 'SOC': np.nan}

    url = (
        "https://rest.isric.org/soilgrids/v2.0/properties/query"
        f"?lat={lat}&lon={lon}"
        "&property=nitrogen&property=phh2o&property=soc"
        "&depth=0-30cm&value=mean"
    )

    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            return {'N': np.nan, 'pH': np.nan, 'SOC': np.nan}

        data = response.json()
        layers = data['properties']['layers']

        def extract_value(name):
            try:
                return next(
                    l for l in layers if l['name'] == name
                )['depths'][0]['values']['mean']
            except:
                return None

        n_raw   = extract_value('nitrogen')
        ph_raw  = extract_value('phh2o')
        soc_raw = extract_value('soc')

        return {
            'N':   safe_divide(n_raw),
            'pH':  safe_divide(ph_raw),
            'SOC': safe_divide(soc_raw)
        }

    except Exception as e:
        print(f"⚠️ SoilGrids lỗi tại ({lat}, {lon}): {e}")
        return {'N': np.nan, 'pH': np.nan, 'SOC': np.nan}

# =========================
# 5. CHẠY THU THẬP DỮ LIỆU ĐẤT
# =========================
soil_records = []

for _, row in df_geo.iterrows():
    print(f"🧪 Thu thập dữ liệu đất: {row['Location']} ...")
    soil_records.append(get_soil_data(row['lat'], row['lon']))


df_soil = pd.DataFrame(soil_records)
df_geo_final = pd.concat([df_geo, df_soil], axis=1)

# =========================
# 6. GỘP VÀ TÍNH NPK
# =========================
df_final = df_original.merge(
    df_geo_final[['Location', 'N', 'pH', 'SOC']],
    on='Location',
    how='left'
)

df_final['P'] = (df_final['SOC'] * 0.35).round(2)
df_final['K'] = (df_final['SOC'] * 0.55).round(2)

# =========================
# 7. XUẤT FILE
# =========================
output_name = "data_enriched_npk.csv"
df_final.to_csv(output_name, index=False)

print("-" * 40)
print(f"🎉 HOÀN THÀNH! File đã tạo: {output_name}")
print(df_final[['Location', 'Crops', 'N', 'P', 'K', 'pH']].head())
 