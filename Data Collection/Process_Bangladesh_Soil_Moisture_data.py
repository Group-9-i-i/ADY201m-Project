import pandas as pd
import numpy as np

def process_soil_moisture_data():
    print("1. Đang đọc dữ liệu Soil Moisture...")
    # Đọc file dữ liệu độ ẩm đất
    sm_df = pd.read_csv('Bangladesh_Soil_Moisture_data.csv')

    # -------------------------------------------------------------------
    # BƯỚC 1: CHUẨN HÓA TÊN DISTRICT (ĐỒNG BỘ VỚI MAIN DATA)
    # -------------------------------------------------------------------
    print("2. Đang chuẩn hóa tên Huyện (District)...")
    
    # Đổi tên cột ADM2_NAME thành District cho chuẩn hóa
    sm_df = sm_df.rename(columns={'ADM2_NAME': 'District'})
    
    # Từ điển chuẩn hóa 13 huyện bị lệch so với file Bangladesh_main_data.csv
    district_map = {
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
    
    # Làm sạch chuỗi (xóa khoảng trắng) và áp dụng thay thế
    sm_df['District'] = sm_df['District'].astype(str).str.strip()
    sm_df['District'] = sm_df['District'].replace(district_map)

    # Có thể xóa cột ADM1_NAME (Tên Vùng) vì nó dễ gây nhầm lẫn khi merge sau này
    if 'ADM1_NAME' in sm_df.columns:
        sm_df = sm_df.drop(columns=['ADM1_NAME'])

    # -------------------------------------------------------------------
    # BƯỚC 2: TÍNH TOÁN CÁC CHỈ SỐ MỚI (FEATURE ENGINEERING)
    # -------------------------------------------------------------------
    print("3. Tính toán các chỉ số nông nghiệp (Feature Engineering)...")
    
    # 2.1. Độ chênh lệch giữa vùng rễ và bề mặt
    sm_df['Rootzone_Surface_Diff'] = sm_df['sm_rootzone'] - sm_df['sm_surface']
    
    # 2.2. Tỷ lệ phân bổ nước (Cộng thêm 0.001 vào mẫu số để tránh lỗi chia cho 0)
    sm_df['Moisture_Ratio'] = sm_df['sm_rootzone'] / (sm_df['sm_surface'] + 0.001)
    
    # 2.3. Phân loại mức độ cấp nước ở vùng rễ (Stress Categorization)
    conditions = [
        (sm_df['sm_rootzone'] < 0.15),
        (sm_df['sm_rootzone'] >= 0.15) & (sm_df['sm_rootzone'] < 0.25),
        (sm_df['sm_rootzone'] >= 0.25)
    ]
    choices = ['High Stress', 'Moderate', 'Optimal']
    sm_df['Water_Availability_Cat'] = np.select(conditions, choices, default='Unknown')

    # Làm tròn các cột số thực mới tạo (4 chữ số thập phân để đảm bảo độ chính xác của viễn thám)
    sm_df['Rootzone_Surface_Diff'] = sm_df['Rootzone_Surface_Diff'].round(4)
    sm_df['Moisture_Ratio'] = sm_df['Moisture_Ratio'].round(4)

    # -------------------------------------------------------------------
    # BƯỚC 3: XUẤT FILE MỚI
    # -------------------------------------------------------------------
    output_filename = 'Bangladesh_Soil_Moisture_data_process.csv'
    
    # Sắp xếp lại thứ tự cột cho đẹp mắt (Đẩy District, Month, Year lên đầu)
    cols = ['District', 'month', 'year', 'sm_surface', 'sm_rootzone', 
            'Rootzone_Surface_Diff', 'Moisture_Ratio', 'Water_Availability_Cat']
    # Lọc những cột nào thực sự có trong DF
    final_cols = [c for c in cols if c in sm_df.columns] 
    
    sm_df = sm_df[final_cols]
    
    # Lưu file
    sm_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\n✅ HOÀN TẤT! File '{output_filename}' đã được tạo thành công.")
    print("Các tính năng mới đã thêm:")
    print(" - Rootzone_Surface_Diff")
    print(" - Moisture_Ratio")
    print(" - Water_Availability_Cat")

if __name__ == "__main__":
    process_soil_moisture_data()