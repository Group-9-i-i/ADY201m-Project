import requests
import pandas as pd
import time

def get_iowa_crops_by_year_range(api_key, start_year, end_year):
    """
    Hàm chạy vòng lặp tải dữ liệu từng năm để tránh lỗi 413 (Too Large).
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    all_years_data = [] # Danh sách chứa dữ liệu của từng năm

    print(f"--- Bắt đầu tải dữ liệu từ năm {start_year} đến {end_year} ---")

    for year in range(start_year, end_year + 1):
        params = {
            'key': api_key,
            'sector_desc': 'CROPS',
            'state_name': 'IOWA',
            'year': str(year),   # Lọc theo từng năm
            'format': 'JSON'
        }

        try:
            print(f"-> Đang tải năm {year}...", end=" ")
            response = requests.get(base_url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    df_year = pd.DataFrame(data['data'])
                    all_years_data.append(df_year)
                    print(f"Thành công! ({len(df_year)} dòng)")
                else:
                    print("Không có dữ liệu.")
            else:
                print(f"Lỗi HTTP: {response.status_code}")

        except Exception as e:
            print(f"Lỗi kết nối: {e}")
        
        # NGỦ 1 GIÂY để tránh bị server chặn do spam request (Rate Limiting)
        time.sleep(1)

    # Gộp tất cả dữ liệu lại
    if all_years_data:
        print("\nĐang gộp dữ liệu...")
        final_df = pd.concat(all_years_data, ignore_index=True)
        return final_df
    else:
        return None

# --- CẤU HÌNH ---
YOUR_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842"

# Bạn có thể chỉnh khoảng thời gian ở đây. 
# Ví dụ: lấy 24 năm gần nhất (2000 - 2024)
START_YEAR = 2000
END_YEAR = 2024

# --- CHẠY ---
df_full = get_iowa_crops_by_year_range(YOUR_API_KEY, START_YEAR, END_YEAR)

if df_full is not None:
    print(f"\n--- TỔNG KẾT ---")
    print(f"Tổng số dòng dữ liệu: {df_full.shape[0]}")
    
    output_file = "iowa_crops_2000_2024_full.csv"
    df_full.to_csv(output_file, index=False, encoding='utf-8')
    print(f"Đã lưu file thành công: {output_file}")
else:
    print("Không tải được dữ liệu nào.")