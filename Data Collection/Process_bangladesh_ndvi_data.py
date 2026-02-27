import pandas as pd
import numpy as np

def process_ndvi_seasonal():
    print("1. Đang đọc dữ liệu...")
    try:
        # Sử dụng đúng tên file bạn đã upload
        df_main = pd.read_csv('Bangladesh_main_data.csv')
        df_ndvi = pd.read_csv('bangladesh_ndvi_data.csv')
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file input.")
        return

    # 2. Chuẩn hóa tên Quận trong file NDVI (quan trọng để khớp dữ liệu)
    district_corrections = {
        'Barisal': 'Barishal', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
        "Cox's Bazar": 'CoxsBazar', 'Jessore': 'Jashore', 'Bogra': 'Bogura',
        'Jhalokati': 'Jhallokati', 'Brahamanbaria': 'Brahmanbaria',
        'Khagrachhari': 'Khagrachari', 'Maulvibazar': 'Moulvibazar',
        'Netrakona': 'Netrokona', 'Nawabganj': 'Chapai Nawabganj',
        'Panchagarh': 'Panchagar'
    }
    df_ndvi['District'] = df_ndvi['District'].replace(district_corrections)

    # 3. Định nghĩa Mùa dựa trên Tháng
    # Quy ước phổ biến tại Bangladesh:
    # Rabi: 12, 1, 2, 3 (Đông/Xuân)
    # Kharif 1: 4, 5, 6, 7 (Hè/Thu - Pre-monsoon)
    # Kharif 2: 8, 9, 10, 11 (Thu/Đông - Monsoon/Post-monsoon)
    
    def get_season(month):
        if month in [12, 1, 2, 3]:
            return 'Rabi'
        elif month in [4, 5, 6, 7]:
            return 'Kharif 1'
        elif month in [8, 9, 10, 11]:
            return 'Kharif 2'
        return None

    # Tạo cột Season cho dữ liệu NDVI
    df_ndvi['Season'] = df_ndvi['Month'].apply(get_season)

    # 4. Tính toán các chỉ số thống kê (Aggregation) theo Quận và Mùa
    print("2. Đang tính toán các chỉ số NDVI theo mùa (Mean, Std, CV, Range)...")
    
    # Gom nhóm theo District và Season
    seasonal_stats = df_ndvi.groupby(['District', 'Season'])['NDVI'].agg(['mean', 'max', 'min', 'std']).reset_index()
    
    # Đổi tên cột cho rõ ràng
    seasonal_stats.columns = ['District', 'Season', 'NDVI_Season_Mean', 'NDVI_Season_Max', 'NDVI_Season_Min', 'NDVI_Season_Std']
    
    # Tính thêm các Feature nâng cao
    # Range: Biên độ biến động (Max - Min)
    seasonal_stats['NDVI_Season_Range'] = seasonal_stats['NDVI_Season_Max'] - seasonal_stats['NDVI_Season_Min']
    
    # CV: Hệ số biến thiên (Std / Mean) - Đo lường độ ổn định
    # Xử lý trường hợp chia cho 0 hoặc Mean quá nhỏ
    seasonal_stats['NDVI_Season_CV'] = seasonal_stats.apply(
        lambda x: (x['NDVI_Season_Std'] / x['NDVI_Season_Mean']) if x['NDVI_Season_Mean'] > 0 else 0, 
        axis=1
    )

    # 5. Gộp với file chính (Merge)
    print("3. Đang gộp dữ liệu...")
    
    # Chuẩn hóa cột Season trong file Main (đảm bảo viết hoa/thường giống nhau)
    # File Main có thể chứa NaN trong cột Season, ta cần xử lý
    df_main['Season_Clean'] = df_main['Season'].astype(str).str.strip()
    # Nếu file Main dùng 'Kharif-1' thay vì 'Kharif 1', cần chuẩn hóa. 
    # (Dựa trên check trước đó thì file Main dùng 'Kharif 1', 'Kharif 2', 'Rabi' nên OK)

    # Thực hiện Merge (Left Join để giữ lại toàn bộ dữ liệu file Main)
    df_merged = pd.merge(
        df_main,
        seasonal_stats,
        left_on=['District', 'Season'], # Cột ghép trong file Main
        right_on=['District', 'Season'], # Cột ghép trong file NDVI
        how='left'
    )
    
    # Xóa cột tạm nếu có
    if 'Season_Clean' in df_merged.columns:
        df_merged.drop(columns=['Season_Clean'], inplace=True)

    # 6. Lưu file
    output_filename = 'Process_bangladesh_ndvi_data.csv'
    df_merged.to_csv(output_filename, index=False)
    print(f"4. Hoàn tất! File đã được lưu tại: {output_filename}")
    
    # Kiểm tra kết quả
    print("\nXem trước dữ liệu sau khi gộp:")
    print(df_merged[['District', 'Season', 'Crop Name', 'NDVI_Season_Mean', 'NDVI_Season_Std']].head())
    
    # Kiểm tra xem có dòng nào không gộp được không (NaN ở cột mới)
    missing_ndvi = df_merged[df_merged['NDVI_Season_Mean'].isna()]
    if not missing_ndvi.empty:
        print(f"\nLưu ý: Có {len(missing_ndvi)} dòng không tìm thấy dữ liệu NDVI tương ứng (thường do thiếu Season hoặc District không khớp).")
        print(missing_ndvi[['District', 'Season']].drop_duplicates().head())

# Chạy chương trình
if __name__ == "__main__":
    process_ndvi_seasonal()