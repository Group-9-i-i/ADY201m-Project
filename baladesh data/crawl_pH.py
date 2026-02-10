import pandas as pd
import requests
import time
import sys

# ==========================================
# CẤU HÌNH
# ==========================================
INPUT_FILE = 'bangladesh_districts_coordinates.csv'
OUTPUT_FILE = 'bangladesh_soil_ph_2022_final.csv'

# ==========================================
# HÀM LẤY DỮ LIỆU THÔNG MINH (SPIRAL SEARCH)
# ==========================================
def get_soilgrids_ph_smart(lat, lon, district_name):
    """
    Tự động tìm kiếm xung quanh nếu điểm tâm rơi vào nước.
    Phạm vi tìm kiếm: Mở rộng dần từ 1km đến 10km.
    """
    
    # Danh sách độ lệch (Spiral Search Pattern)
    # 0.01 độ ~ 1.1km
    search_offsets = [
        (0, 0),             # 1. Tâm
        (0.01, 0),          # 2. Bắc 1km
        (-0.01, 0),         # 3. Nam 1km
        (0, 0.01),          # 4. Đông 1km
        (0, -0.01),         # 5. Tây 1km
        (0.02, 0.02),       # 6. Đông Bắc 2km
        (-0.02, -0.02),     # 7. Tây Nam 2km
        (0.03, 0),          # 8. Bắc 3km
        (0, 0.03),          # 9. Đông 3km
        (0.05, 0.05),       # 10. Xa hơn 5km (cho vùng cửa biển cực lớn)
        (-0.05, -0.05) 
    ]

    print(f"   > Đang quét {district_name}...", end="")
    
    for i, (dx, dy) in enumerate(search_offsets):
        try_lat = lat + dx
        try_lon = lon + dy
        
        try:
            # API SoilGrids
            url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={try_lon}&lat={try_lat}&property=phh2o&depth=0-5cm"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                layers = data.get('properties', {}).get('layers', [])
                
                if layers:
                    mean_val = layers[0]['depths'][0]['values']['mean']
                    
                    # Nếu tìm thấy giá trị (không phải None)
                    if mean_val is not None:
                        ph = mean_val / 10
                        if i == 0:
                            print(f" [OK] pH: {ph}")
                        else:
                            print(f" [OK - Tìm thấy cách tâm {i} bước] pH: {ph}")
                        return ph
        except:
            pass # Lỗi mạng thì thử điểm tiếp theo
            
    print(f" [CẢNH BÁO] Không tìm thấy đất sau {len(search_offsets)} lần thử.")
    return None

# ==========================================
# MAIN
# ==========================================
def main():
    print("--- BẮT ĐẦU QUÉT DỮ LIỆU ĐẤT BANGLADESH (NO GEE) ---")
    
    # 1. Đọc file
    try:
        df = pd.read_csv(INPUT_FILE)
        print(f"Đã tải {len(df)} huyện.")
    except FileNotFoundError:
        print(f"Lỗi: Không thấy file {INPUT_FILE}")
        return

    # 2. Quét dữ liệu
    results = []
    
    for index, row in df.iterrows():
        # Gọi hàm tìm kiếm thông minh
        ph = get_soilgrids_ph_smart(row['lat'], row['lon'], row['name'])
        results.append(ph)
        
    df['pH_Final_2022'] = results

    # 3. Điền giá trị trung bình cho các ô vẫn bị sót (Fallback cuối cùng)
    # Tính trung bình cả nước từ các ô đã tìm được
    national_mean = df['pH_Final_2022'].mean()
    if pd.isna(national_mean): national_mean = 6.0 # Giá trị mặc định nếu lỗi toàn bộ
    
    # Lấp đầy các ô trống còn lại bằng giá trị trung bình (để đảm bảo file không có ô trống)
    df['pH_Final_2022'] = df['pH_Final_2022'].fillna(round(national_mean, 2))
    
    # 4. Xuất file
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n--- HOÀN THÀNH 100% ---")
    print(f"File kết quả: {OUTPUT_FILE}")
    print(df[['name', 'pH_Final_2022']].head(10))

if __name__ == "__main__":
    main()