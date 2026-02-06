import requests
import pandas as pd
import time
import os

# --- CẤU HÌNH ---
START_YEAR = 2000
END_YEAR = 2024
# Đặt tên thư mục đơn giản, không dấu tiếng Việt
OUTPUT_DIR = "iowa_hourly_data_v2" 

# Tạo đường dẫn tuyệt đối để tránh lỗi
abs_output_dir = os.path.abspath(OUTPUT_DIR)
if not os.path.exists(abs_output_dir):
    try:
        os.makedirs(abs_output_dir)
        print(f"-> Đã tạo thư mục lưu trữ tại: {abs_output_dir}")
    except Exception as e:
        print(f"-> Lỗi không tạo được thư mục: {e}")
        # Nếu lỗi, dùng thư mục hiện tại
        abs_output_dir = os.getcwd()
        print(f"-> Sẽ lưu vào thư mục hiện tại: {abs_output_dir}")

# 5 Điểm đại diện Iowa
LOCATIONS = [
    {"name": "Center_Ames", "lat": 42.03, "lon": -93.62},
    {"name": "NorthWest",    "lat": 43.00, "lon": -95.50},
    {"name": "NorthEast",    "lat": 43.00, "lon": -91.50},
    {"name": "SouthWest",    "lat": 41.00, "lon": -95.50},
    {"name": "SouthEast",    "lat": 41.00, "lon": -91.50}
]

# Danh sách biến ĐỀ XUẤT
PROPOSED_VARIABLES = [
    # 1. NHIỆT ĐỘ & KHÔNG KHÍ
    "temperature_2m", "dew_point_2m", "skin_temperature", "surface_pressure",
    # 2. NƯỚC
    "precipitation", "rain", "snowfall", "et0_fao_evapotranspiration", "vapor_pressure_deficit",
    # 3. ĐỘ ẨM ĐẤT (4 Tầng)
    "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm", 
    "soil_moisture_28_to_100cm", "soil_moisture_100_to_255cm",
    # 4. NHIỆT ĐỘ ĐẤT (4 Tầng)
    "soil_temperature_0_to_7cm", "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm", "soil_temperature_100_to_255cm",
    # 5. BỨC XẠ
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    # 6. GIÓ
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"
]

def validate_variables():
    print("\n--- BƯỚC 1: KIỂM TRA TÍNH HỢP LỆ CỦA CÁC BIẾN ---")
    url = "https://archive-api.open-meteo.com/v1/archive"
    valid_vars = []
    
    test_params = {
        "latitude": 42.03, "longitude": -93.62,
        "start_date": "2023-01-01", "end_date": "2023-01-01",
        "hourly": [] 
    }

    for var in PROPOSED_VARIABLES:
        print(f"Checking '{var}'...", end=" ")
        test_params["hourly"] = [var]
        try:
            r = requests.get(url, params=test_params, timeout=10)
            if r.status_code == 200:
                print("OK")
                valid_vars.append(var)
            elif r.status_code == 429: # Lỗi quá tải
                print("FAIL (429) -> Đợi 5s...")
                time.sleep(5)
                # Thử lại
                r = requests.get(url, params=test_params, timeout=10)
                if r.status_code == 200:
                    print("OK (Retry)")
                    valid_vars.append(var)
                else:
                    print("FAIL -> Loại bỏ")
            else:
                print(f"FAIL ({r.status_code}) -> Loại bỏ")
        except:
            print("Lỗi kết nối -> Bỏ qua")
        time.sleep(0.5)
        
    print(f"\n=> Danh sách biến HỢP LỆ ({len(valid_vars)}/{len(PROPOSED_VARIABLES)})")
    return valid_vars

def download_data(valid_vars):
    if not valid_vars:
        print("Không có biến nào hợp lệ. Dừng chương trình.")
        return

    print(f"\n--- BƯỚC 2: BẮT ĐẦU TẢI DỮ LIỆU ({START_YEAR}-{END_YEAR}) ---")
    print(f"Lưu tại: {abs_output_dir}")
    
    url = "https://archive-api.open-meteo.com/v1/archive"

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n-> Đang xử lý năm {year}...", end=" ")
        year_data_list = []
        
        for loc in LOCATIONS:
            params = {
                "latitude": loc["lat"], "longitude": loc["lon"],
                "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
                "hourly": valid_vars,
                "timezone": "America/Chicago"
            }
            
            # --- CƠ CHẾ THỬ LẠI (RETRY) ---
            max_retries = 10
            success = False
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, timeout=120)
                    
                    if response.status_code == 200:
                        data = response.json()
                        df = pd.DataFrame(data['hourly'])
                        
                        # Thêm metadata
                        df['location'] = loc['name']
                        df['lat'] = loc['lat']
                        df['lon'] = loc['lon']
                        
                        # Sắp xếp cột
                        cols = ['time', 'location', 'lat', 'lon'] + [c for c in df.columns if c not in ['time', 'location', 'lat', 'lon']]
                        df = df[cols]
                        
                        year_data_list.append(df)
                        print(f"[OK:{loc['name']}]", end=" ")
                        success = True
                        
                        # Nghỉ 3 giây sau mỗi lần thành công để tránh bị chặn
                        time.sleep(3) 
                        break 

                    elif response.status_code == 429: # Bị chặn
                        wait_time = 30 * (attempt + 1)
                        print(f"\n   [!] Bị chặn (429). Chờ {wait_time}s...", end=" ")
                        time.sleep(wait_time)
                        continue # Thử lại
                    
                    else:
                        print(f"[Lỗi API {response.status_code}]", end=" ")
                        break

                except Exception as e:
                    print(f"[Lỗi mạng]", end=" ")
                    time.sleep(5)
            
        # --- LƯU FILE AN TOÀN ---
        if year_data_list:
            try:
                df_year = pd.concat(year_data_list, ignore_index=True)
                
                # Tạo đường dẫn file đầy đủ
                filename = f"iowa_hourly_{year}.csv"
                filepath = os.path.join(abs_output_dir, filename)
                
                # Ghi file
                df_year.to_csv(filepath, index=False)
                print(f" -> Đã lưu: {filepath}")
                
            except Exception as e:
                print(f"\n[!!! LỖI LƯU FILE !!!] : {e}")
                # Backup: Lưu ra file tên đơn giản ngay tại chỗ chạy code
                try:
                    backup_name = f"BACKUP_iowa_{year}.csv"
                    df_year.to_csv(backup_name, index=False)
                    print(f" -> Đã lưu bản BACKUP tại: {os.path.abspath(backup_name)}")
                except:
                    print(" -> Không thể lưu cả file backup.")
        else:
            print(" -> Không có dữ liệu để lưu.")

if __name__ == "__main__":
    clean_vars = validate_variables()
    if clean_vars:
        download_data(clean_vars)