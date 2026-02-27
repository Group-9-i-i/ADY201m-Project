import pandas as pd
import os

def merge_datasets():
    # Tên các file đầu vào và đầu ra
    # Hãy đảm bảo các file này nằm cùng thư mục với script này
    salinity_path = 'Bangladesh_Salinity_data.csv'
    main_data_path = 'Bangladesh_main_data.csv'
    output_path = 'Process_Bangladesh_Salinity_data.csv'

    # Kiểm tra xem file có tồn tại không
    if not os.path.exists(salinity_path) or not os.path.exists(main_data_path):
        print(f"Lỗi: Không tìm thấy file dữ liệu.")
        print(f"Vui lòng đảm bảo '{salinity_path}' và '{main_data_path}' nằm cùng thư mục với file code này.")
        return

    # 1. Đọc dữ liệu
    print("Đang đọc dữ liệu...")
    try:
        df_salinity = pd.read_csv(salinity_path)
        df_main = pd.read_csv(main_data_path)
    except Exception as e:
        print(f"Lỗi khi đọc file CSV: {e}")
        return

    # 2. Chuẩn hóa tên Quận/Huyện (District Mapping)
    # Ánh xạ tên từ file Salinity sang tên chuẩn trong file Main
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

    print("Đang chuẩn hóa tên địa danh...")
    # Tạo cột District mới trong file Salinity đã được chuẩn hóa tên
    df_salinity['District'] = df_salinity['ADM2_NAME'].replace(district_map)

    # 3. Tạo cột Season cho dữ liệu độ mặn
    # Quy tắc mùa vụ:
    # Rabi: Tháng 11, 12, 1, 2, 3
    # Kharif 1: Tháng 4, 5, 6
    # Kharif 2: Tháng 7, 8, 9, 10
    def get_season(month):
        if month in [11, 12, 1, 2, 3]:
            return 'Rabi'
        elif month in [4, 5, 6]:
            return 'Kharif 1'
        elif month in [7, 8, 9, 10]:
            return 'Kharif 2'
        return None

    print("Đang phân loại mùa vụ...")
    df_salinity['Season'] = df_salinity['Month'].apply(get_season)

    # 4. Tổng hợp dữ liệu độ mặn
    # Tính trung bình độ mặn theo từng Quận và Mùa vụ để có thể ghép 1-1 với file chính
    print("Đang tính toán độ mặn trung bình theo mùa...")
    salinity_agg = df_salinity.groupby(['District', 'Season'])['Salinity_Index_Raw'].mean().reset_index()
    salinity_agg.rename(columns={'Salinity_Index_Raw': 'Avg_Salinity_Index'}, inplace=True)

    # 5. Ghép dữ liệu (Merge)
    # Sử dụng Left Join để giữ lại toàn bộ dữ liệu nông nghiệp chính và thêm cột độ mặn tương ứng
    print("Đang ghép dữ liệu...")
    merged_df = pd.merge(df_main, salinity_agg, on=['District', 'Season'], how='left')

    # 6. Lưu kết quả
    print(f"Đang lưu kết quả vào file '{output_path}'...")
    merged_df.to_csv(output_path, index=False)
    
    print("Hoàn tất!")
    print(f"Dữ liệu đã gộp: {merged_df.shape[0]} dòng, {merged_df.shape[1]} cột.")
    print("-" * 30)
    print("5 dòng đầu tiên của dữ liệu mới:")
    print(merged_df[['District', 'Season', 'Crop Name', 'Avg_Salinity_Index']].head())

if __name__ == "__main__":
    merge_datasets()