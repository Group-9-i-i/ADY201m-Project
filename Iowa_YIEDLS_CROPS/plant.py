import requests
import pandas as pd
import time
import os

# --- CẤU HÌNH ---
YOUR_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842"  # Key của bạn
START_YEAR = 2000
END_YEAR = 2025
STATE_NAME = "IOWA"

def get_iowa_yield_specific(api_key, start_year, end_year):
    """
    Hàm chuyên dụng để tải dữ liệu NĂNG SUẤT (YIELD) của tất cả cây trồng.
    Giữ lại toàn bộ các cột chi tiết từ USDA.
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    all_years_data = []

    print(f"--- BẮT ĐẦU TẢI DỮ LIỆU NĂNG SUẤT (YIELD) TẠI {STATE_NAME} ({start_year}-{end_year}) ---")

    for year in range(start_year, end_year + 1):
        # Cấu hình tham số để lọc riêng Năng suất
        params = {
            'key': api_key,
            'source_desc': 'SURVEY',      # Ưu tiên lấy số liệu Khảo sát hàng năm (liên tục nhất)
            'sector_desc': 'CROPS',       # Lĩnh vực Cây trồng
            'statisticcat_desc': 'YIELD', # CHỈ LẤY DỮ LIỆU NĂNG SUẤT
            'state_name': STATE_NAME,
            'year': str(year),
            'format': 'JSON'
        }

        try:
            print(f"-> Đang tải năm {year}...", end=" ")
            
            # Gửi yêu cầu
            response = requests.get(base_url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    # Chuyển đổi sang DataFrame (Tự động giữ tất cả các cột có trong DB)
                    df_year = pd.DataFrame(data['data'])
                    all_years_data.append(df_year)
                    print(f"Thành công! ({len(df_year)} dòng)")
                else:
                    print("Không có dữ liệu.")
            else:
                # Xử lý trường hợp năm đó chưa có dữ liệu (ví dụ 2025 chưa thu hoạch xong)
                print(f"Không tìm thấy hoặc lỗi server ({response.status_code})")

        except Exception as e:
            print(f"Lỗi kết nối: {e}")
        
        # Nghỉ 1 giây để tránh bị chặn
        time.sleep(1)

    # Gộp dữ liệu
    if all_years_data:
        print("\nĐang gộp tất cả các năm lại...")
        final_df = pd.concat(all_years_data, ignore_index=True)
        return final_df
    else:
        return None

# --- CHẠY CHƯƠNG TRÌNH ---
df_yield = get_iowa_yield_specific(YOUR_API_KEY, START_YEAR, END_YEAR)

if df_yield is not None:
    # 1. Hiển thị thông tin
    print(f"\n--- TỔNG KẾT ---")
    print(f"Tổng số dòng dữ liệu Yield: {df_yield.shape[0]}")
    print(f"Tổng số cột dữ liệu: {df_yield.shape[1]}")
    
    # 2. Lưu ra file CSV
    output_filename = f"iowa_crops_yield_only_{START_YEAR}_{END_YEAR}.csv"
    df_yield.to_csv(output_filename, index=False, encoding='utf-8')
    print(f"Đã lưu file thành công: {output_filename}")
    
    # 3. Hiển thị mẫu để kiểm tra
    print("\nVí dụ 5 dòng dữ liệu đầu tiên:")
    # Chọn vài cột quan trọng để hiển thị trên màn hình (trong file CSV vẫn đủ hết)
    cols_to_show = ['year', 'commodity_desc', 'short_desc', 'Value', 'unit_desc']
    print(df_yield[cols_to_show].head())
else:
    print("Không tải được dữ liệu nào.")