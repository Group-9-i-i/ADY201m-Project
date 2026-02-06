import requests
import pandas as pd
import time
import os

# --- CẤU HÌNH ---
YOUR_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842"
MISSING_YEARS = [2007, 2017, 2022] # Các năm bị lỗi 413
EXISTING_FILE = "iowa_crops_2000_2024_full.csv" # File bạn đã tải được phần lớn

def get_data_by_group_split(api_key, year):
    """
    Hàm tải dữ liệu cho các năm 'nặng' bằng cách chia nhỏ theo từng nhóm cây trồng (Group).
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    
    # Danh sách các nhóm cây trồng chính để chia nhỏ gói tin
    # Thay vì tải 1 cục, ta tải 4 cục nhỏ
    groups = ['FIELD CROPS', 'VEGETABLES', 'FRUIT & TREE NUTS', 'HORTICULTURE', 'CROP TOTALS']
    
    year_data = []
    print(f"--- Đang xử lý năm {year} (Chia nhỏ để tránh lỗi 413) ---")

    for group in groups:
        params = {
            'key': api_key,
            'sector_desc': 'CROPS',
            'group_desc': group,   # LỌC THEO NHÓM ĐỂ GIẢM DUNG LƯỢNG
            'state_name': 'IOWA',
            'year': str(year),
            'format': 'JSON'
        }

        try:
            print(f"   + Đang tải nhóm '{group}'...", end=" ")
            response = requests.get(base_url, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    df_part = pd.DataFrame(data['data'])
                    year_data.append(df_part)
                    print(f"OK! ({len(df_part)} dòng)")
                else:
                    print("Không có số liệu.")
            elif response.status_code == 413:
                print("VẪN BỊ LỖI 413 (Quá lớn). Cần chia nhỏ hơn nữa.")
                # Ở đây có thể viết thêm logic chia nhỏ commodity nếu cần thiết
                # Nhưng thường chia theo Group là đủ.
            else:
                print(f"Lỗi {response.status_code}")

        except Exception as e:
            print(f"Lỗi kết nối: {e}")
        
        time.sleep(1) # Nghỉ 1 chút

    if year_data:
        return pd.concat(year_data, ignore_index=True)
    else:
        return None

# --- BẮT ĐẦU QUY TRÌNH VÁ LỖI ---

# 1. Đọc file dữ liệu cũ (đã tải được các năm thường)
if os.path.exists(EXISTING_FILE):
    print(f"Đang đọc file hiện tại: {EXISTING_FILE}")
    df_main = pd.read_csv(EXISTING_FILE)
    print(f"-> Số dòng hiện có: {len(df_main)}")
else:
    print("Không tìm thấy file CSV cũ. Đang tạo mới dataframe rỗng.")
    df_main = pd.DataFrame()

# 2. Tải bù các năm thiếu
missing_data_list = []

for year in MISSING_YEARS:
    # Kiểm tra xem năm này đã có trong file cũ chưa (tránh trùng lặp)
    if not df_main.empty and year in df_main['year'].values:
        # Đếm số dòng của năm đó, nếu quá ít (ví dụ < 1000) thì coi như thiếu và tải lại
        count = len(df_main[df_main['year'] == year])
        if count > 1000:
            print(f"Năm {year} đã có dữ liệu ({count} dòng). Bỏ qua.")
            continue
    
    # Gọi hàm tải chia nhỏ
    df_missing = get_data_by_group_split(YOUR_API_KEY, year)
    
    if df_missing is not None:
        missing_data_list.append(df_missing)

# 3. Ghép nối và Lưu file
if missing_data_list:
    print("\nĐang ghép dữ liệu mới vào dữ liệu cũ...")
    df_missing_total = pd.concat(missing_data_list, ignore_index=True)
    
    # Nối vào bảng chính
    df_final = pd.concat([df_main, df_missing_total], ignore_index=True)
    
    # Sắp xếp lại theo Năm cho đẹp
    if 'year' in df_final.columns:
        df_final = df_final.sort_values(by=['year', 'commodity_desc'])

    # Lưu đè lên file cũ (hoặc file mới)
    output_file = "iowa_crops_2000_2024_fixed.csv"
    df_final.to_csv(output_file, index=False, encoding='utf-8')
    
    print(f"\n--- THÀNH CÔNG ---")
    print(f"Tổng số dòng sau khi sửa: {len(df_final)}")
    print(f"File đã được lưu tại: {output_file}")
    
    # Kiểm tra nhanh số lượng dòng của các năm vừa sửa
    print("\nKiểm tra lại số dòng của các năm từng bị lỗi:")
    for year in MISSING_YEARS:
        count = len(df_final[df_final['year'] == year])
        print(f"- Năm {year}: {count} dòng")

else:
    print("\nKhông tải thêm được dữ liệu nào hoặc các năm đã đầy đủ.")