import requests
import pandas as pd
import os
import time
import io
from datetime import datetime

# --- CẤU HÌNH ---
START_YEAR = 2000
END_YEAR = 2024
OUTPUT_FOLDER = "iowa_climate_database_full" # Thư mục lưu dữ liệu

# Tạo thư mục nếu chưa có
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def get_station_list(network):
    """
    Lấy danh sách tất cả các trạm thuộc một mạng lưới (Network).
    """
    url = f"http://mesonet.agron.iastate.edu/geojson/network/{network}.geojson"
    try:
        response = requests.get(url)
        data = response.json()
        stations = []
        for feature in data['features']:
            props = feature['properties']
            stations.append({
                'id': props['sid'],
                'name': props['sname'],
                'lat': feature['geometry']['coordinates'][1],
                'lon': feature['geometry']['coordinates'][0]
            })
        return pd.DataFrame(stations)
    except Exception as e:
        print(f"Lỗi khi lấy danh sách trạm mạng {network}: {e}")
        return pd.DataFrame()

def download_station_data(network, station_id, start_year, end_year):
    """
    Tải dữ liệu hàng ngày cho 1 trạm cụ thể.
    """
    url = "http://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
    params = {
        'network': network,
        'stations': station_id,
        'year1': start_year, 'month1': 1, 'day1': 1,
        'year2': end_year, 'month2': 12, 'day2': 31,
        'format': 'csv',
        'na': 'blank'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            # Bỏ qua các dòng comment (#)
            content = response.content.decode('utf-8')
            # Kiểm tra xem có dữ liệu không
            if "station,day," not in content and "station,date," not in content:
                 return None
            
            df = pd.read_csv(io.StringIO(content), comment='#')
            return df
        else:
            return None
    except Exception as e:
        print(f"  -> Lỗi kết nối trạm {station_id}: {e}")
        return None

def main_downloader():
    # 1. TẢI MẠNG LƯỚI ĐẤT & NÔNG NGHIỆP (ISUSM) - QUAN TRỌNG NHẤT
    print("\n--- BƯỚC 1: TẢI DỮ LIỆU ĐẤT (ISUSM) ---")
    df_stations_soil = get_station_list("ISUSM")
    print(f"Tìm thấy {len(df_stations_soil)} trạm đo đất.")
    
    all_soil_data = []
    
    for index, row in df_stations_soil.iterrows():
        print(f"[{index+1}/{len(df_stations_soil)}] Đang tải trạm: {row['name']} ({row['id']})...", end=" ")
        
        df = download_station_data("ISUSM", row['id'], START_YEAR, END_YEAR)
        
        if df is not None and not df.empty:
            # Thêm thông tin toạ độ
            df['lat'] = row['lat']
            df['lon'] = row['lon']
            all_soil_data.append(df)
            print("OK!")
        else:
            print("Không có dữ liệu.")
        
        time.sleep(0.5) # Nghỉ nhẹ để không bị chặn IP

    if all_soil_data:
        final_soil = pd.concat(all_soil_data, ignore_index=True)
        filename = os.path.join(OUTPUT_FOLDER, "iowa_soil_isusm_full.csv")
        final_soil.to_csv(filename, index=False)
        print(f"-> Đã lưu dữ liệu đất đầy đủ: {filename} ({len(final_soil)} dòng)")

    # 2. TẢI MẠNG LƯỚI KHÍ TƯỢNG (IA_ASOS) - NHIỆT/MƯA/GIÓ
    print("\n--- BƯỚC 2: TẢI DỮ LIỆU KHÍ TƯỢNG (ASOS) ---")
    df_stations_weather = get_station_list("IA_ASOS")
    print(f"Tìm thấy {len(df_stations_weather)} trạm khí tượng sân bay.")
    
    all_weather_data = []
    
    for index, row in df_stations_weather.iterrows():
        print(f"[{index+1}/{len(df_stations_weather)}] Đang tải trạm: {row['name']} ({row['id']})...", end=" ")
        
        df = download_station_data("IA_ASOS", row['id'], START_YEAR, END_YEAR)
        
        if df is not None and not df.empty:
            df['lat'] = row['lat']
            df['lon'] = row['lon']
            all_weather_data.append(df)
            print("OK!")
        else:
            print("Không có dữ liệu.")
            
        time.sleep(0.5)

    if all_weather_data:
        final_weather = pd.concat(all_weather_data, ignore_index=True)
        filename = os.path.join(OUTPUT_FOLDER, "iowa_weather_asos_full.csv")
        final_weather.to_csv(filename, index=False)
        print(f"-> Đã lưu dữ liệu khí tượng đầy đủ: {filename} ({len(final_weather)} dòng)")

    print(f"\n--- HOÀN TẤT ---")
    print(f"Dữ liệu đã được lưu trong thư mục: {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main_downloader()