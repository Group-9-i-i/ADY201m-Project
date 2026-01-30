import requests
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import time
import os

# 1. Kiểm tra file và đọc dữ liệu
file_path = "data_season.csv"

if not os.path.exists(file_path):
    print(f"❌ Lỗi: Không tìm thấy file '{file_path}' tại thư mục hiện tại.")
    print(f"Thư mục hiện tại là: {os.getcwd()}")
    # Dừng chương trình hoặc cho phép nhập tên file khác
    exit()

df_original = pd.read_csv(file_path)
print("✅ Đã đọc file thành công!")

# 2. Lấy tọa độ cho các huyện (Chỉ lấy các huyện duy nhất để tiết kiệm thời gian)
unique_locations = df_original['Location'].unique()
df_geo = pd.DataFrame(unique_locations, columns=['Location'])

geolocator = Nominatim(user_agent="agri_data_expert_v3")

def get_lat_lon(loc):
    try:
        # Thêm bang Karnataka và India để định vị chính xác
        full_address = f"{loc}, Karnataka, India"
        location = geolocator.geocode(full_address, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def get_soil_data(lat, lon):
    if pd.isna(lat) or pd.isna(lon): return None
    
    # API SoilGrids lấy Nitrogen, pH và SOC (đại diện cho chất hữu cơ)
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=nitrogen&property=phh2o&property=soc&depth=0-5cm&value=mean"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            layers = data['properties']['layers']
            
            # Trích xuất giá trị từ JSON
            n_raw = next(l for l in layers if l['name'] == 'nitrogen')['depths'][0]['values']['mean']
            ph_raw = next(l for l in layers if l['name'] == 'phh2o')['depths'][0]['values']['mean']
            soc_raw = next(l for l in layers if l['name'] == 'soc')['depths'][0]['values']['mean']
            
            return {
                'N': n_raw / 10,       # Đơn vị g/kg
                'pH': ph_raw / 10,     # Thang đo 0-14
                'SOC': soc_raw / 10    # Organic Carbon
            }
    except Exception as e:
        print(f"Lỗi khi gọi SoilGrids tại ({lat}, {lon}): {e}")
    return None

# --- CHẠY TIẾN TRÌNH ---
print(f"Đang lấy tọa độ cho {len(unique_locations)} địa điểm...")
df_geo[['lat', 'lon']] = df_geo['Location'].apply(lambda x: pd.Series(get_lat_lon(x)))

soil_info = []
for idx, row in df_geo.iterrows():
    print(f"-> Thu thập dữ liệu đất tại: {row['Location']}...")
    res = get_soil_data(row['lat'], row['lon'])
    if res:
        soil_info.append(res)
    else:
        soil_info.append({'N': np.nan, 'pH': np.nan, 'SOC': np.nan})
    time.sleep(1.2) # Tránh bị chặn API

df_soil_data = pd.DataFrame(soil_info)
df_geo_final = pd.concat([df_geo, df_soil_data], axis=1)

# 3. Gộp lại vào bảng gốc và tính toán P, K dựa trên SOC (Chất hữu cơ)
df_final = df_original.merge(df_geo_final[['Location', 'N', 'pH', 'SOC']], on='Location', how='left')

# Công thức ước lượng P và K từ SOC (Hữu cơ càng cao thì P và K thường cao tương ứng)
df_final['P'] = (df_final['SOC'] * 0.35).round(2)
df_final['K'] = (df_final['SOC'] * 0.55).round(2)

# Xóa cột SOC trung gian nếu không cần thiết
# df_final = df_final.drop(columns=['SOC'])

# 4. Lưu ra file mới
output_name = 'data_enriched_npk.csv'
df_final.to_csv(output_name, index=False)
print("-" * 30)
print(f"🎉 HOÀN THÀNH! File mới đã được tạo: {output_name}")
print(df_final[['Location', 'Crops', 'N', 'P', 'K', 'pH']].head())