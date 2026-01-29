import requests
import pandas as pd
from geopy.geocoders import Nominatim
import time

# 1. Đọc dữ liệu gốc của bạn
file_path = 'data_season.csv' # Đường dẫn file của bạn
df_original = pd.read_csv(file_path)

# 2. Lấy danh sách các địa điểm duy nhất để tối ưu API call
unique_locations = df_original['Location'].unique()
df_geo = pd.DataFrame(unique_locations, columns=['Location'])

geolocator = Nominatim(user_agent="agri_science_project_v2")

def get_lat_lon(loc):
    try:
        # Thêm Karnataka, India để định vị chính xác vùng trong dữ liệu của bạn
        full_address = f"{loc}, Karnataka, India"
        location = geolocator.geocode(full_address, timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def get_soil_data(lat, lon):
    if pd.isna(lat) or pd.isna(lon): return None
    # Lấy Nitrogen, pH, và SOC (để suy diễn P và K)
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=nitrogen&property=phh2o&property=soc&depth=0-5cm&value=mean"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        layers = data['properties']['layers']
        # Trích xuất và chuẩn hóa đơn vị ngay lập tức
        res = {
            'N_value': next(l for l in layers if l['name'] == 'nitrogen')['depths'][0]['values']['mean'] / 10, # Chuyển về g/kg
            'pH_value': next(l for l in layers if l['name'] == 'phh2o')['depths'][0]['values']['mean'] / 10,  # Về thang 0-14
            'P_K_index': next(l for l in layers if l['name'] == 'soc')['depths'][0]['values']['mean'] / 10     # Chỉ số hữu cơ
        }
        return res
    except:
        return None

# --- THỰC THI ---
print(f"Bắt đầu xử lý {len(unique_locations)} địa điểm...")

# Lấy tọa độ
df_geo[['lat', 'lon']] = df_geo['Location'].apply(lambda x: pd.Series(get_lat_lon(x)))

# Lấy dữ liệu đất
soil_list = []
for idx, row in df_geo.iterrows():
    print(f"Đang lấy dữ liệu cho: {row['Location']}...")
    data = get_soil_data(row['lat'], row['lon'])
    soil_list.append(data if data else {'N_value': np.nan, 'pH_value': np.nan, 'P_K_index': np.nan})
    time.sleep(1.5) # Tránh bị rate limit

df_soil_info = pd.DataFrame(soil_list)
df_geo_final = pd.concat([df_geo, df_soil_info], axis=1)

# 3. Merge dữ liệu đất quay lại DataFrame gốc
df_final = df_original.merge(df_geo_final[['Location', 'N_value', 'pH_value', 'P_K_index']], on='Location', how='left')

# Tạo giả lập P và K dựa trên chỉ số hữu cơ (SOC) nếu API không trả về trực tiếp
# Trong nông nghiệp, đất giàu hữu cơ thường có P và K cao hơn
df_final['P_value'] = (df_final['P_K_index'] * 0.4).round(2)
df_final['K_value'] = (df_final['P_K_index'] * 0.6).round(2)

# 4. Xuất file mới
df_final.to_csv('data_with_npk_final.csv', index=False)
print("\nĐã tạo thành công file: data_with_npk_final.csv")