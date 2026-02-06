import requests
import pandas as pd
import os
import time

# --- CẤU HÌNH ---
YOUR_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842"
STATE = "IOWA"
OUTPUT_DIR = "iowa_features_data_fixed"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_nass_data_flexible(api_key, params, filename_desc):
    """
    Hàm tải dữ liệu linh hoạt, chấp nhận tải về trước rồi lọc sau để tránh lỗi 400.
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    params['key'] = api_key
    params['state_name'] = STATE
    params['format'] = 'JSON'
    
    print(f"--- Đang tải: {filename_desc} ---")
    
    try:
        response = requests.get(base_url, params=params, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                df = pd.DataFrame(data['data'])
                print(f"   -> Thành công! ({len(df)} dòng)")
                # Lưu file thô
                outfile = os.path.join(OUTPUT_DIR, f"iowa_{filename_desc}.csv")
                df.to_csv(outfile, index=False)
                return df
            else:
                print("   -> Không có dữ liệu.")
                return None
        else:
            print(f"   -> Lỗi API {response.status_code}: Kiểm tra lại tham số.")
            # In ra URL để debug nếu cần
            # print(response.url) 
            return None
    except Exception as e:
        print(f"   -> Lỗi kết nối: {e}")
        return None

def main_features_fixed():
    
    # 1. PHÂN BÓN (FERTILIZER) - CHIẾN THUẬT MỚI
    # Thay vì lọc kỹ Unit, ta tải toàn bộ dữ liệu Môi trường của Ngô
    print("\n[1] Đang xử lý dữ liệu PHÂN BÓN (Nitrogen, Potash, Phosphate)...")
    
    params_fert = {
        'sector_desc': 'ENVIRONMENTAL',
        'commodity_desc': 'CORN',
        'year__GE': '2000' # Lấy từ năm 2000
        # BỎ các tham số statisticcat_desc và unit_desc chi tiết để tránh lỗi 400
    }
    
    df_fert = get_nass_data_flexible(YOUR_API_KEY, params_fert, "corn_environmental_raw")
    
    if df_fert is not None:
        # Tự động lọc ra các file con quan trọng bằng Pandas
        print("   -> Đang tách dữ liệu phân bón chi tiết...")
        
        # a. Lượng bón (LB / ACRE / YEAR)
        # Tìm các dòng đơn vị có chứa "LB" và "ACRE" và "YEAR"
        mask_rate = df_fert['unit_desc'].str.contains('LB / ACRE / YEAR', na=False)
        df_rate = df_fert[mask_rate]
        df_rate.to_csv(os.path.join(OUTPUT_DIR, "iowa_fertilizer_rates_cleaned.csv"), index=False)
        print(f"      + Đã tạo file: iowa_fertilizer_rates_cleaned.csv ({len(df_rate)} dòng)")

        # b. Tỷ lệ diện tích bón (PCT OF AREA)
        mask_pct = df_fert['unit_desc'].str.contains('PCT', na=False)
        df_pct = df_fert[mask_pct]
        df_pct.to_csv(os.path.join(OUTPUT_DIR, "iowa_fertilizer_pct_area_cleaned.csv"), index=False)
        print(f"      + Đã tạo file: iowa_fertilizer_pct_area_cleaned.csv ({len(df_pct)} dòng)")


    # 2. LÀM ĐẤT (TILLAGE) - CHIẾN THUẬT MỚI
    # Thay vì tìm trong Economics (dễ nhầm), ta tìm theo từ khóa "TILLAGE" trong short_desc
    print("\n[2] Đang xử lý dữ liệu LÀM ĐẤT (Tillage)...")
    
    params_tillage = {
        'short_desc__LIKE': 'TILLAGE',  # Tìm mọi thứ có chữ TILLAGE
        'year__GE': '2000'
    }
    
    df_till = get_nass_data_flexible(YOUR_API_KEY, params_tillage, "tillage_raw")
    
    if df_till is not None:
        # Lọc lấy các dòng quan trọng về phương pháp làm đất
        # Thường là: NO-TILL, CONSERVATION TILLAGE, CONVENTIONAL
        print("   -> Đang lọc phương pháp làm đất...")
        mask_practices = df_till['short_desc'].str.contains('PRACTICE', na=False)
        df_till_clean = df_till[mask_practices]
        
        df_till_clean.to_csv(os.path.join(OUTPUT_DIR, "iowa_tillage_practices_cleaned.csv"), index=False)
        print(f"      + Đã tạo file: iowa_tillage_practices_cleaned.csv ({len(df_till_clean)} dòng)")

    print(f"\n--- HOÀN TẤT! Dữ liệu nằm trong thư mục '{OUTPUT_DIR}' ---")

if __name__ == "__main__":
    main_features_fixed()