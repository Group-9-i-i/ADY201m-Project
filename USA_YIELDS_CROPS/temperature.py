import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import numpy as np

# --- CẤU HÌNH ---
USDA_API_KEY = 'B78E0F65-2875-3F09-B2B7-9EB201AA8842'
NOAA_TOKEN = 'UfgTNtgxCaUKkKBKbyxkhLzVFerhklZd'

# Danh sách trạm Sân Bay Quốc Tế (Dữ liệu ổn định nhất)
STATE_STATIONS = {
    'ALABAMA': 'GHCND:USW00013876', 'ALASKA': 'GHCND:USW00026411', 'ARIZONA': 'GHCND:USW00023183',
    'ARKANSAS': 'GHCND:USW00013963', 'CALIFORNIA': 'GHCND:USW00023234', 'COLORADO': 'GHCND:USW00023062',
    'CONNECTICUT': 'GHCND:USW00014740', 'DELAWARE': 'GHCND:USW00013781', 'FLORIDA': 'GHCND:USW00012839',
    'GEORGIA': 'GHCND:USW00013874', 'HAWAII': 'GHCND:USW00022521', 'IDAHO': 'GHCND:USW00024131',
    'ILLINOIS': 'GHCND:USW00094846', 'INDIANA': 'GHCND:USW00093819', 'IOWA': 'GHCND:USW00014933',
    'KANSAS': 'GHCND:USW00013988', 'KENTUCKY': 'GHCND:USW00093821', 'LOUISIANA': 'GHCND:USW00013956',
    'MAINE': 'GHCND:USW00014606', 'MARYLAND': 'GHCND:USW00093721', 'MASSACHUSETTS': 'GHCND:USW00014739',
    'MICHIGAN': 'GHCND:USW00014836', 'MINNESOTA': 'GHCND:USW00014922', 'MISSISSIPPI': 'GHCND:USW00013942',
    'MISSOURI': 'GHCND:USW00003947', 'MONTANA': 'GHCND:USW00024153', 'NEBRASKA': 'GHCND:USW00014936',
    'NEVADA': 'GHCND:USW00023169', 'NEW HAMPSHIRE': 'GHCND:USW00014710', 'NEW JERSEY': 'GHCND:USW00014734',
    'NEW MEXICO': 'GHCND:USW00023050', 'NEW YORK': 'GHCND:USW00094728', 'NORTH CAROLINA': 'GHCND:USW00013722',
    'NORTH DAKOTA': 'GHCND:USW00014913', 'OHIO': 'GHCND:USW00014820', 'OKLAHOMA': 'GHCND:USW00013967',
    'OREGON': 'GHCND:USW00024229', 'PENNSYLVANIA': 'GHCND:USW00013739', 'RHODE ISLAND': 'GHCND:USW00014765',
    'SOUTH CAROLINA': 'GHCND:USW00013880', 'SOUTH DAKOTA': 'GHCND:USW00014935', 'TENNESSEE': 'GHCND:USW00013893',
    'TEXAS': 'GHCND:USW00012960', 'UTAH': 'GHCND:USW00024127', 'VERMONT': 'GHCND:USW00014742',
    'VIRGINIA': 'GHCND:USW00013743', 'WASHINGTON': 'GHCND:USW00024233', 'WEST VIRGINIA': 'GHCND:USW00013866',
    'WISCONSIN': 'GHCND:USW00014837', 'WYOMING': 'GHCND:USW00024018'
}

# --- THIẾT LẬP SESSION ---
def create_retry_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

# --- 1. HÀM USDA (Giữ nguyên) ---
def get_usda_data(session, year):
    url = "https://quickstats.nass.usda.gov/api/api_GET/"
    params = {
        'key': USDA_API_KEY, 'source_desc': 'SURVEY', 'sector_desc': 'ECONOMICS',
        'commodity_desc': 'FARM OPERATIONS', 'statisticcat_desc': 'AREA OPERATED',
        'unit_desc': 'ACRES', 'year': year, 'format': 'JSON'
    }
    try:
        response = session.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                df = pd.DataFrame(data['data'])
                if 'Value' in df.columns:
                    df['Value'] = df['Value'].astype(str).str.replace(',', '', regex=False)
                    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
                    df['state_name'] = df['state_name'].str.upper()
                    return df[['year', 'state_name', 'Value']].rename(columns={'Value': 'Farmland_Acres'})
        return None
    except Exception:
        return None

# --- 2. HÀM NOAA MỚI (Dùng GSOM - Theo Tháng) ---
def get_noaa_data_monthly(session, state_name, station_id):
    url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
    headers = {'token': NOAA_TOKEN}
    
    # CHIẾN THUẬT MỚI: Lấy GSOM (Tháng) thay vì GSOY (Năm)
    params = {
        'datasetid': 'GSOM', 
        'locationid': station_id,
        'startdate': '2015-01-01',
        'enddate': '2025-01-01', 
        'datatypeid': ['TAVG', 'PRCP'], # TAVG: Nhiệt độ TB, PRCP: Mưa
        'limit': 1000, # Lấy tối đa 1000 tháng (đủ cho 10 năm)
        'units': 'standard'
    }
    
    try:
        response = session.get(url, headers=headers, params=params, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            # DEBUG: In ra nếu rỗng để biết
            if 'results' not in data:
                # print(f"  [!] {state_name}: API trả về rỗng (0 bản ghi)")
                return None

            df = pd.DataFrame(data['results'])
            df['date'] = pd.to_datetime(df['date'])
            df['year'] = df['date'].dt.year
            
            # --- TÍNH TOÁN TỪ THÁNG RA NĂM ---
            # 1. Lọc lấy TAVG và PRCP
            # Tính trung bình nhiệt độ các tháng -> Nhiệt độ năm
            tavg = df[df['datatype'] == 'TAVG'].groupby('year')['value'].mean().reset_index().rename(columns={'value': 'Avg_Temp_F'})
            
            # Tính tổng lượng mưa các tháng -> Lượng mưa năm
            prcp = df[df['datatype'] == 'PRCP'].groupby('year')['value'].sum().reset_index().rename(columns={'value': 'Precipitation_Inches'})
            
            # Gộp lại
            df_final = pd.merge(tavg, prcp, on='year', how='outer')
            df_final['state_name'] = state_name
            
            return df_final
            
        elif response.status_code == 429:
            print(f"  [!] {state_name}: Quá tải (429).")
            time.sleep(5)
            return None
        else:
            print(f"  [!] {state_name}: Lỗi {response.status_code}")
            return None
            
    except Exception as e:
        print(f"  [!] {state_name}: Lỗi ngoại lệ: {e}")
        return None

# --- MAIN ---
http = create_retry_session()

# 1. USDA
print("--- 1. LẤY DỮ LIỆU USDA ---")
usda_list = []
for year in range(2015, 2026):
    print(f"USDA Năm {year}...", end="\r")
    df = get_usda_data(http, year)
    if df is not None: usda_list.append(df)
    time.sleep(0.5)
print("\n-> Xong USDA.")

if usda_list:
    usda_final = pd.concat(usda_list)
else:
    usda_final = pd.DataFrame()

# 2. NOAA
print("\n--- 2. LẤY DỮ LIỆU NOAA (GSOM - MONTHLY) ---")
print("Đang quét từng bang (sẽ mất khoảng 1-2 phút)...")
noaa_list = []
count = 0

for state, station_id in STATE_STATIONS.items():
    count += 1
    print(f"[{count}/50] {state:<20}...", end="\r")
    
    df_weather = get_noaa_data_monthly(http, state, station_id)
    
    if df_weather is not None and not df_weather.empty:
        noaa_list.append(df_weather)
    
    time.sleep(0.3) # Giữ tốc độ vừa phải

print("\n-> Xong NOAA.")

# 3. KẾT QUẢ VÀ LƯU
if noaa_list:
    noaa_final = pd.concat(noaa_list)
    print(f"\nĐã lấy được dữ liệu khí hậu của {len(noaa_final['state_name'].unique())} bang.")
    
    # Merge
    if not usda_final.empty:
        usda_final['year'] = usda_final['year'].astype(int)
    noaa_final['year'] = noaa_final['year'].astype(int)
    
    # Làm tròn số
    noaa_final['Avg_Temp_F'] = noaa_final['Avg_Temp_F'].round(2)
    noaa_final['Precipitation_Inches'] = noaa_final['Precipitation_Inches'].round(2)
    
    final_df = pd.merge(usda_final, noaa_final, on=['year', 'state_name'], how='left')
    final_df.to_csv("FINAL_DATA_2015_2025.csv", index=False)
    print("\nTHÀNH CÔNG! File: FINAL_DATA_2015_2025.csv")
    print(final_df.head())
else:
    print("\nTHẤT BẠI: Vẫn không có dữ liệu NOAA. Có thể Token bị chặn hoặc sai.")
    # In thử response của 1 bang để debug
    print("Debug thử bang ALABAMA:")
    test_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GSOM&locationid=GHCND:USW00013876&startdate=2015-01-01&enddate=2015-05-01&datatypeid=TAVG&limit=10"
    test_res = requests.get(test_url, headers={'token': NOAA_TOKEN})
    print(f"Status Code: {test_res.status_code}")
    print(f"Response: {test_res.text}")