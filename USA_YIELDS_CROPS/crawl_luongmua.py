import requests
import pandas as pd
import time
import os

# ================= CẤU HÌNH =================
API_TOKEN = 'UfgTNtgxCaUKkKBKbyxkhLzVFerhklZd' 
BASE_URL = 'https://www.ncdc.noaa.gov/cdo-web/api/v2/data'

# Folder để lưu dữ liệu (Tạo folder riêng cho gọn)
OUTPUT_FOLDER = 'NOAA_Rainfall_Data'
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

US_STATES = {
    '01': 'Alabama', '02': 'Alaska', '04': 'Arizona', '05': 'Arkansas',
    '06': 'California', '08': 'Colorado', '09': 'Connecticut', '10': 'Delaware',
    '12': 'Florida', '13': 'Georgia', '15': 'Hawaii', '16': 'Idaho',
    '17': 'Illinois', '18': 'Indiana', '19': 'Iowa', '20': 'Kansas',
    '21': 'Kentucky', '22': 'Louisiana', '23': 'Maine', '24': 'Maryland',
    '25': 'Massachusetts', '26': 'Michigan', '27': 'Minnesota', '28': 'Mississippi',
    '29': 'Missouri', '30': 'Montana', '31': 'Nebraska', '32': 'Nevada',
    '33': 'New Hampshire', '34': 'New Jersey', '35': 'New Mexico', '36': 'New York',
    '37': 'North Carolina', '38': 'North Dakota', '39': 'Ohio', '40': 'Oklahoma',
    '41': 'Oregon', '42': 'Pennsylvania', '44': 'Rhode Island', '45': 'South Carolina',
    '46': 'South Dakota', '47': 'Tennessee', '48': 'Texas', '49': 'Utah',
    '50': 'Vermont', '51': 'Virginia', '53': 'Washington', '54': 'West Virginia',
    '55': 'Wisconsin', '56': 'Wyoming'
}

HEADERS = {'token': API_TOKEN}

def fetch_state_data_pagination(fips, state_name):
    """
    Lấy dữ liệu của TẤT CẢ các trạm trong bang bằng cách phân trang (Pagination).
    Mỗi lần lấy 1000 dòng cho đến khi hết.
    """
    print(f"\n--> BẮT ĐẦU: {state_name} (FIPS: {fips})")
    all_results = []
    offset = 1
    limit = 1000
    total_fetched = 0
    
    # Chia nhỏ theo năm để giảm tải cho server (API dễ timeout nếu query 10 năm 1 lúc cho toàn bang)
    # Chúng ta sẽ loop từng năm.
    for year in range(2015, 2026):
        print(f"   + Đang xử lý năm {year}...", end="")
        
        offset = 1 # Reset offset cho năm mới
        while True:
            params = {
                'datasetid': 'GSOM',        # Dữ liệu tháng
                'datatypeid': 'PRCP',       # Lượng mưa
                'locationid': f'FIPS:{fips}',
                'startdate': f'{year}-01-01',
                'enddate': f'{year}-12-31',
                'limit': limit,
                'offset': offset,           # <--- QUAN TRỌNG: Vị trí bắt đầu lấy dữ liệu
                'units': 'metric'
            }

            try:
                response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Nếu có kết quả
                    if 'results' in data and data['results']:
                        batch_size = len(data['results'])
                        all_results.extend(data['results'])
                        total_fetched += batch_size
                        
                        # Nếu lấy được ít hơn limit (ví dụ lấy được 500 dòng trong khi limit 1000)
                        # nghĩa là đã hết dữ liệu của năm đó.
                        if batch_size < limit:
                            print(f" [Xong năm {year}]")
                            break
                        
                        # Tăng offset để lấy trang tiếp theo
                        offset += batch_size
                        
                        # In dấu chấm để biết code đang chạy
                        print(".", end="", flush=True)
                        
                        # Nghỉ xíu để không spam server
                        time.sleep(0.2)
                    else:
                        # Không còn kết quả nào
                        print(f" [Xong năm {year}]")
                        break
                        
                elif response.status_code == 429:
                    print(f"\n      [!] Server báo quá tải. Nghỉ 5 giây...")
                    time.sleep(5)
                elif response.status_code == 503:
                    print(f"\n      [!] Lỗi Server NOAA. Thử lại sau 2s...")
                    time.sleep(2)
                else:
                    print(f"\n      [Lỗi] Mã {response.status_code}. Bỏ qua batch này.")
                    break
                    
            except Exception as e:
                print(f"\n      [Ngoại lệ] {e}. Thử lại...")
                time.sleep(2)
    
    return all_results

def main():
    print(f"--- TOOL TẢI DỮ LIỆU TOÀN BỘ TRẠM (ALL STATIONS) ---")
    print(f"Lưu ý: Quá trình này sẽ rất lâu vì dữ liệu khổng lồ.")
    
    for fips, name in US_STATES.items():
        # Gọi hàm lấy dữ liệu
        raw_data = fetch_state_data_pagination(fips, name)
        
        if raw_data:
            print(f"   => Tổng cộng: {len(raw_data)} bản ghi cho {name}.")
            
            # Xử lý dữ liệu ra dạng bảng
            processed_data = []
            for item in raw_data:
                processed_data.append({
                    'State': name,
                    'Station_ID': item.get('station', 'Unknown'), # ID Trạm
                    'Date': item.get('date', ''),
                    'Year': item.get('date', '')[:4],
                    'Month': item.get('date', '')[5:7],
                    'Precipitation_mm': item.get('value', 0),
                    'Attributes': item.get('attributes', '') # Cờ đánh dấu chất lượng dữ liệu
                })
            
            # Lưu ngay ra file CSV cho bang đó
            df = pd.DataFrame(processed_data)
            filename = f"{OUTPUT_FOLDER}/{name}_AllStations_2015_2025.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"   => Đã lưu file: {filename}")
        else:
            print(f"   => Không có dữ liệu nào cho {name}")
            
        print("-" * 50)

if __name__ == "__main__":
    main()