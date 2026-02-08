import pandas as pd
import numpy as np

def merge_env_data():
    print("--- Đang đọc dữ liệu... ---")
    # 1. Đọc dữ liệu
    try:
        df_kk = pd.read_csv('kk_with_full.csv')
        df_env = pd.read_csv('Bangladesh_Env_Indicators_2022_Success.csv')
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file CSV. Hãy đảm bảo tên file đúng như yêu cầu.")
        return

    # 2. Chuẩn hóa tên Quận/Huyện trong file môi trường để khớp với file chính
    print("--- Đang chuẩn hóa tên Huyện... ---")
    district_mapping = {
        'Barisal': 'Barishal',
        'Bogra': 'Bogura',
        'Brahamanbaria': 'Brahmanbaria',
        'Chittagong': 'Chattogram',
        'Comilla': 'Cumilla',
        "Cox's Bazar": 'CoxsBazar',
        'Jessore': 'Jashore',
        'Jhalokati': 'Jhallokati',
        'Khagrachhari': 'Khagrachari',
        'Maulvibazar': 'Moulvibazar',
        'Nawabganj': 'Chapai Nawabganj',
        'Netrakona': 'Netrokona',
        'Panchagarh': 'Panchagar'
    }
    df_env['District'] = df_env['ADM2_NAME'].replace(district_mapping)

    # 3. Tạo bảng tra cứu nhanh (Lookup Dictionary)
    # Giúp code chạy nhanh hơn thay vì lọc dữ liệu cho từng dòng
    # Key = (Tên Huyện, Tháng) -> Value = {EVI, LAI, ...}
    env_lookup = df_env.groupby(['District', 'Month']).agg({
        'EVI': 'mean',
        'LAI': 'mean',
        'FPAR': 'mean',
        'LST_Kelvin': 'mean',
        'Soil_Moisture_mm': 'mean'
    }).to_dict('index')

    # 4. Hàm hỗ trợ xử lý thời gian
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    def get_month_num(month_str):
        if not isinstance(month_str, str): return None
        return month_map.get(month_str.strip().lower()[:3])

    def parse_growth_period(growth_str):
        """Chuyển đổi chuỗi như 'July to Oct' thành danh sách [7, 8, 9, 10]"""
        if not isinstance(growth_str, str) or 'no need' in growth_str.lower():
            return []
        
        parts = growth_str.lower().split(' to ')
        if len(parts) != 2:
            # Trường hợp chỉ có 1 tháng hoặc format lạ, thử lấy tháng đầu tiên
            m = get_month_num(growth_str)
            return [m] if m else []

        start, end = get_month_num(parts[0]), get_month_num(parts[1])
        if not start or not end: return []

        if start <= end:
            return list(range(start, end + 1))
        else:
            # Trường hợp qua năm mới (ví dụ Nov to Feb -> 11, 12, 1, 2)
            return list(range(start, 13)) + list(range(1, end + 1))

    # 5. Hàm tính toán chính (Chạy cho từng dòng của file KK)
    def calculate_row_metrics(row):
        district = row['District']
        
        # Lấy danh sách tháng sinh trưởng
        months = parse_growth_period(row['Growth'])
        
        # Nếu không có thông tin Growth, dùng tháng Transplant làm dự phòng
        if not months:
            t_month = get_month_num(row['Transplant'])
            months = [t_month] if t_month else []

        # List tạm để chứa giá trị
        evi_vals, lai_vals, fpar_vals, lst_vals, sm_vals = [], [], [], [], []

        for m in months:
            # Tra cứu dữ liệu từ file Env
            data = env_lookup.get((district, m))
            if data:
                # Chỉ lấy dữ liệu hợp lệ (loại bỏ -9999)
                if data['EVI'] > -1: evi_vals.append(data['EVI'])
                if data['LAI'] > -1: lai_vals.append(data['LAI'])
                if data['FPAR'] > -1: fpar_vals.append(data['FPAR'])
                if data['LST_Kelvin'] > 0: lst_vals.append(data['LST_Kelvin'])
                if data['Soil_Moisture_mm'] > -100: sm_vals.append(data['Soil_Moisture_mm'])

        # Hàm tính trung bình an toàn (tránh lỗi chia cho 0)
        def safe_avg(lst): return np.mean(lst) if lst else np.nan

        return pd.Series([
            safe_avg(evi_vals),
            safe_avg(lai_vals),
            safe_avg(fpar_vals),
            safe_avg(lst_vals),
            safe_avg(sm_vals)
        ])

    print("--- Đang tính toán và ghép dữ liệu (Sẽ mất khoảng 10-20 giây)... ---")
    
    # Tạo các cột mới
    new_cols = ['EVI_Season', 'LAI_Season', 'FPAR_Season', 'LST_Season', 'Soil_Moisture_Season']
    df_kk[new_cols] = df_kk.apply(calculate_row_metrics, axis=1)

    # 6. Lưu file
    output_file = 'kk_with_env_FINAL.csv'
    df_kk.to_csv(output_file, index=False)
    
    print("\n" + "="*50)
    print(f"XONG! Đã tạo file: {output_file}")
    print(f"Tổng số dòng: {len(df_kk)}")
    print("Dữ liệu môi trường đã được tính trung bình theo mùa vụ của từng loại cây.")
    print("="*50)

# Chạy hàm
if __name__ == "__main__":
    merge_env_data()