import pandas as pd
import numpy as np

def update_soil_ph():
    print("Đang đọc dữ liệu...")
    # 1. Đọc 2 file dữ liệu
    main_df = pd.read_csv('ket_qua_ghep_final_full_2022.csv')
    ph_df = pd.read_csv('bangladesh_soil_ph_2022_final.csv')
    
    print(f"Số dòng ban đầu của file chính: {len(main_df)}")
    print(f"Số dòng bị thiếu soil_ph ban đầu: {main_df['soil_ph'].isnull().sum()}")

    # 2. Tạo từ điển ánh xạ tên Huyện (Mapping)
    # File chính (main_df) dùng tên khác một chút so với file pH (ph_df)
    # Cần map về tên chuẩn của file pH để ghép
    district_map = {
        'Barishal': 'Barisal',
        'Bogura': 'Bogra',
        'Cumilla': 'Comilla',
        'CoxsBazar': "Cox's Bazar",
        'Jashore': 'Jessore',
        'Panchagar': 'Panchagarh',
        # Các huyện khác như Chattogram, Khagrachari... đã khớp
    }

    # Tạo cột tạm để ghép nối
    main_df['Merge_District'] = main_df['District'].replace(district_map)

    # 3. Ghép dữ liệu pH từ file mới vào
    # Chúng ta merge dựa trên cột tên huyện đã chuẩn hóa
    merged_df = main_df.merge(ph_df[['name', 'pH_Final_2022']], 
                              left_on='Merge_District', 
                              right_on='name', 
                              how='left')

    # 4. Cập nhật và Điền khuyết (Impute)
    
    # Bước A: Cập nhật cột 'pH' bằng dữ liệu mới nhất (pH_Final_2022)
    # Nếu file mới có dữ liệu thì dùng, nếu không thì giữ nguyên cái cũ
    merged_df['pH'] = merged_df['pH_Final_2022'].fillna(merged_df['pH'])

    # Bước B: Điền cột 'soil_ph' đang bị thiếu
    # Quy luật quan sát được: soil_ph thường bằng pH * 10 (ví dụ pH 5.7 -> soil_ph 57.0)
    # Ta sẽ điền các ô trống bằng giá trị này
    merged_df['soil_ph'] = merged_df['soil_ph'].fillna(merged_df['pH'] * 10)

    # 5. Dọn dẹp cột thừa
    final_df = merged_df.drop(columns=['Merge_District', 'name', 'pH_Final_2022'])

    # Kiểm tra kết quả
    missing_count = final_df['soil_ph'].isnull().sum()
    print(f"Số dòng bị thiếu soil_ph sau khi xử lý: {missing_count}")
    
    # Lưu file kết quả
    output_file = 'ket_qua_ghep_final_full_pH_2022.csv'
    final_df.to_csv(output_file, index=False)
    print(f"Hoàn tất! File đã được lưu tại: {output_file}")
    
    # Hiển thị vài dòng mẫu để kiểm tra
    print("\nVí dụ dữ liệu sau khi ghép:")
    print(final_df[['District', 'pH', 'soil_ph']].head(10))

# Chạy hàm
update_soil_ph()