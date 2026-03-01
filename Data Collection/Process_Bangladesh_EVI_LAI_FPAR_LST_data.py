import pandas as pd
import numpy as np  # <--- Thêm thư viện này để xử lý NaN

def process_and_merge_data():
    # --- 1. Đọc dữ liệu ---
    print("Đang đọc file...")
    try:
        # File vệ tinh (EVI, LAI...)
        df_evi = pd.read_csv('Bangladesh_EVI_LAI_FPAR_LST_data.csv')
        # File dữ liệu chính (Main data)
        df_main = pd.read_csv('Bangladesh_main_data.csv')
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file. {e}")
        return

    # ==============================================================================
    # --- BƯỚC MỚI THÊM VÀO: Xử lý giá trị lỗi (-9999) và Tự động điền dữ liệu ---
    # ==============================================================================
    print("Đang xử lý và tự động điền dữ liệu thiếu...")
    
    # Danh sách các cột cần làm sạch
    cols_to_fix = ['EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm']
    
    # 1. Thay thế -9999 thành NaN
    for col in cols_to_fix:
        if col in df_evi.columns:
            df_evi[col] = df_evi[col].replace(-9999, np.nan)
            
    # 2. Sắp xếp theo Quận -> Năm -> Tháng để nội suy theo thời gian chuẩn xác
    # Lưu ý: Lúc này tên cột vẫn là ADM2_NAME (chưa đổi tên)
    df_evi = df_evi.sort_values(by=['ADM2_NAME', 'Year', 'Month'])

    # 3. Hàm điền dữ liệu (Nội suy)
    def fill_missing_values(group):
        # Nội suy tuyến tính (Linear): Tự động tính giá trị giữa 2 điểm
        group = group.interpolate(method='linear', limit_direction='both')
        # Nếu đầu hoặc cuối chuỗi vẫn còn NaN, dùng giá trị gần nhất để điền (bfill/ffill)
        group = group.bfill().ffill()
        return group

    # 4. Áp dụng hàm điền dữ liệu cho từng Quận riêng biệt
    for col in cols_to_fix:
        if col in df_evi.columns:
            # transform giúp giữ nguyên số dòng của dataframe
            df_evi[col] = df_evi.groupby('ADM2_NAME')[col].transform(fill_missing_values)
            
            # Phòng trường hợp vẫn còn NaN (ví dụ cả quận không có dữ liệu nào), điền bằng 0 hoặc trung bình toàn cục
            if df_evi[col].isna().sum() > 0:
                 df_evi[col] = df_evi[col].fillna(0)
    
    print("-> Đã điền xong dữ liệu (Interpolation).")
    # ==============================================================================

    # --- 2. Chuẩn hóa tên quận trong file EVI để khớp với Main data ---
    # Danh sách sửa lỗi tên quận (mapping từ EVI -> Main)
    district_corrections = {
        'Barisal': 'Barishal',
        'Chittagong': 'Chattogram',
        'Comilla': 'Cumilla',
        "Cox's Bazar": 'CoxsBazar',
        'Jessore': 'Jashore',
        'Bogra': 'Bogura',
        'Jhalokati': 'Jhallokati',
        'Brahamanbaria': 'Brahmanbaria',
        'Khagrachhari': 'Khagrachari',
        'Maulvibazar': 'Moulvibazar',
        'Netrakona': 'Netrokona',
        'Nawabganj': 'Chapai Nawabganj',
        'Panchagarh': 'Panchagar'
    }
    
    # Sửa tên quận trong cột ADM2_NAME và đổi tên cột thành 'District'
    df_evi['ADM2_NAME'] = df_evi['ADM2_NAME'].replace(district_corrections)
    df_evi.rename(columns={'ADM2_NAME': 'District'}, inplace=True)

    # --- 3. Định nghĩa mùa dựa trên tháng ---
    # Quy ước:
    # - Rabi: Tháng 12, 1, 2, 3 (Mùa đông/xuân)
    # - Kharif 1: Tháng 4, 5, 6, 7 (Đầu mùa mưa)
    # - Kharif 2: Tháng 8, 9, 10, 11 (Cuối mùa mưa/thu)
    
    def get_season(month):
        if month in [12, 1, 2, 3]:
            return 'Rabi'
        elif month in [4, 5, 6, 7]:
            return 'Kharif 1'
        elif month in [8, 9, 10, 11]:
            return 'Kharif 2'
        return 'Unknown'

    df_evi['Season'] = df_evi['Month'].apply(get_season)

    # --- 4. Gom nhóm dữ liệu EVI theo Quận, Năm và Mùa ---
    # Tính trung bình các chỉ số EVI, LAI, FPAR, LST cho mỗi mùa
    evi_seasonal = df_evi.groupby(['District', 'Year', 'Season'])[[
        'EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm'
    ]].mean().reset_index()

    print(f"Đã xử lý xong dữ liệu vệ tinh. Số dòng sau khi gộp theo mùa: {len(evi_seasonal)}")

    # --- 5. Gộp với file Main ---
    # Lưu ý: File Main có thể không có cột Year. 
    # Nếu gộp, mỗi dòng trong Main sẽ được nhân bản cho từng năm có trong file EVI.
    
    # Kiểm tra xem tên mùa trong file Main viết hoa hay thường để khớp
    # (Ví dụ: Main dùng "Kharif 1" hay "Kharif 1")
    # Ta sẽ chuẩn hóa về dạng Title case cho chắc chắn
    df_main['Season'] = df_main['Season'].astype(str).str.strip().str.title() 
    # Sửa lại Kharif 1/2 cho đúng định dạng nếu cần (ví dụ Main ghi "Kharif 1", code tạo ra "Kharif 1")
    
    print("Đang gộp dữ liệu...")
    merged_df = pd.merge(
        df_main, 
        evi_seasonal, 
        on=['District', 'Season'], # Gộp theo Quận và Mùa
        how='left' # Giữ lại tất cả dữ liệu từ file Main
    )

    # --- 6. Lưu kết quả ---
    output_filename = 'Process_Bangladesh_EVI_LAI_FPAR_LST_data.csv'
    merged_df.to_csv(output_filename, index=False)
    print(f"Thành công! File đã gộp được lưu tại: {output_filename}")
    print(merged_df[['District', 'Season', 'Soil_Moisture_mm']].head()) # In thử cột Soil Moisture để kiểm tra

# Chạy hàm
process_and_merge_data()