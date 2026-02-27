import pandas as pd
import numpy as np

def process_soil_data():
    print("1. Đang đọc dữ liệu Đất (Soil)...")
    soil_df = pd.read_csv('Bangladesh_soil_data.csv')

    # -------------------------------------------------------------------
    # BƯỚC 1: CHUẨN HÓA TÊN DISTRICT
    # -------------------------------------------------------------------
    print("2. Đang dọn dẹp và chuẩn hóa tên Huyện (District)...")
    # Đảm bảo cột District là kiểu chuỗi, xóa khoảng trắng ở 2 đầu và viết hoa chữ cái đầu
    soil_df['District'] = soil_df['District'].astype(str).str.strip().str.title()
    
    # -------------------------------------------------------------------
    # BƯỚC 2: TÍNH TOÁN CÁC CHỈ SỐ MỚI (FEATURE ENGINEERING)
    # -------------------------------------------------------------------
    print("3. Tính toán các chỉ số nông nghiệp từ dữ liệu đất...")

    # 2.1. Tỷ lệ C/N (Carbon to Nitrogen Ratio)
    # Cộng một số rất nhỏ (0.001) vào Nitrogen để tránh lỗi chia cho 0 nếu có dữ liệu khuyết
    soil_df['CN_Ratio'] = soil_df['Organic_Carbon'] / (soil_df['Nitrogen'] + 0.001)
    
    # 2.2. Đánh giá mức độ phù hợp của pH (pH Suitability)
    conditions_ph = [
        (soil_df['pH'] < 5.5),
        (soil_df['pH'] >= 5.5) & (soil_df['pH'] <= 7.0),
        (soil_df['pH'] > 7.0)
    ]
    choices_ph = ['Acidic (Chua)', 'Optimal (Tối ưu)', 'Alkaline (Kiềm)']
    soil_df['pH_Suitability'] = np.select(conditions_ph, choices_ph, default='Unknown')

    # 2.3. Đánh giá rủi ro nén dẽ của đất (Compaction Risk) qua Bulk Density
    conditions_bd = [
        (soil_df['Bulk_Density'] < 1.4),
        (soil_df['Bulk_Density'] >= 1.4) & (soil_df['Bulk_Density'] <= 1.6),
        (soil_df['Bulk_Density'] > 1.6)
    ]
    choices_bd = ['Low', 'Moderate', 'High']
    soil_df['Compaction_Risk'] = np.select(conditions_bd, choices_bd, default='Unknown')

    # 2.4. Phân loại cấu trúc đất (Đất Cát, Đất Sét, Đất Thịt...)
    def classify_texture(row):
        sand = row['Sand']
        clay = row['Clay']
        if pd.isna(sand) or pd.isna(clay):
            return 'Unknown'
        if sand >= 50:
            return 'Sandy (Cát)'
        elif clay >= 40:
            return 'Clayey (Sét)'
        else:
            return 'Loamy (Thịt/Phù sa)'

    soil_df['Dominant_Soil_Texture'] = soil_df.apply(classify_texture, axis=1)

    # Làm tròn các cột số vừa tạo
    soil_df['CN_Ratio'] = soil_df['CN_Ratio'].round(2)

    # -------------------------------------------------------------------
    # BƯỚC 3: XUẤT FILE MỚI
    # -------------------------------------------------------------------
    output_filename = 'Bangladesh_soil_data_process.csv'
    
    # Đẩy cột District lên đầu cho dễ nhìn
    cols = soil_df.columns.tolist()
    cols.insert(0, cols.pop(cols.index('District')))
    soil_df = soil_df[cols]
    
    soil_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\n✅ HOÀN TẤT! File '{output_filename}' đã được tạo thành công.")
    print("Các biến mới được tạo bao gồm:")
    print(" - CN_Ratio")
    print(" - pH_Suitability")
    print(" - Compaction_Risk")
    print(" - Dominant_Soil_Texture")

if __name__ == "__main__":
    process_soil_data()