import requests
import pandas as pd
import time
import os
from tqdm import tqdm # Thư viện thanh tiến độ

# --- CẤU HÌNH ---
MY_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842"
FILENAME = "usa_crops_state_level_2015_2025.csv"
YEARS = range(2015, 2026) # 2015 -> 2025

# Danh sách 50 bang + DC để duyệt qua (Tránh gọi 'US' tổng quát sẽ bị lỗi limit)
US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

def fetch_state_data(api_key, year, state_alpha):
    """
    Lấy dữ liệu crops của 1 Bang trong 1 Năm
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    params = {
        'key': api_key,
        'source_desc': 'SURVEY',
        'sector_desc': 'CROPS',
        'year': str(year),
        'agg_level_desc': 'STATE',  # Lấy chi tiết cấp Bang
        'state_alpha': state_alpha, # Chỉ định mã bang cụ thể (VD: 'CA')
        'format': 'JSON'
    }
    
    try:
        # Timeout 30s là đủ cho request nhỏ cấp bang
        response = requests.get(base_url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                return pd.DataFrame(data['data'])
    except Exception:
        pass # Nếu lỗi thì bỏ qua bang đó, chạy tiếp
    
    return None

# --- CHẠY CHƯƠNG TRÌNH ---

# Xóa file cũ nếu tồn tại để viết mới từ đầu (tránh bị trùng lặp khi chạy lại)
if os.path.exists(FILENAME):
    os.remove(FILENAME)
    print(f"Đã xóa file cũ {FILENAME} để tạo mới.")

print(f"Bắt đầu tải dữ liệu chi tiết từng Bang (2015-2025)...")
print(f"Tổng số lượt request dự kiến: {len(YEARS) * len(US_STATES)}")

# Khởi tạo thanh tiến độ tổng
total_iterations = len(YEARS) * len(US_STATES)
pbar = tqdm(total=total_iterations, desc="Tiến độ", unit="request")

# Biến đếm để xử lý header CSV
is_first_write = True

for year in YEARS:
    for state in US_STATES:
        # Cập nhật mô tả thanh tiến độ
        pbar.set_description(f"Đang tải: {year} - {state}")
        
        df = fetch_state_data(MY_API_KEY, year, state)
        
        if df is not None and not df.empty:
            # Sắp xếp sơ bộ
            if 'commodity_desc' in df.columns:
                df = df.sort_values(by='commodity_desc')
            
            # LƯU NGAY LẬP TỨC (Append mode 'a')
            # Nếu là lần đầu tiên thì ghi cả header, các lần sau không ghi header
            df.to_csv(FILENAME, mode='a', index=False, header=is_first_write)
            is_first_write = False
            
        # Cập nhật thanh tiến độ
        pbar.update(1)
        
        # Nghỉ cực ngắn để không spam server quá nhanh nhưng vẫn nhanh hơn trước
        time.sleep(0.5)

pbar.close()
print("\n" + "="*50)
print(f"HOÀN TẤT! Dữ liệu đã được lưu vào: {FILENAME}")
print("Gợi ý: File này rất lớn, bạn nên dùng Pandas để mở thay vì Excel.")