import pandas as pd
import os

def merge_ph_data():
    # --- CẤU HÌNH TÊN FILE ---
    # Đảm bảo các file này nằm cùng thư mục với file code python
    file_nguon_ph = 'bangladesh_soil_ph_2022_final.csv'  # File chứa pH mới
    file_can_ghep = 'ket_qua_ghep.csv'                  # File cần thay thế cột pH
    file_ket_qua = 'ket_qua_ghep_updated_pH.csv'        # Tên file xuất ra

    # Kiểm tra file tồn tại
    if not os.path.exists(file_nguon_ph) or not os.path.exists(file_can_ghep):
        print("LỖI: Không tìm thấy file đầu vào. Hãy kiểm tra lại tên file hoặc đường dẫn.")
        return

    print("Đang đọc dữ liệu...")
    # 1. Đọc dữ liệu
    df_new = pd.read_csv(file_nguon_ph)
    df_old = pd.read_csv(file_can_ghep)

    print(f" - File nguồn pH: {len(df_new)} dòng")
    print(f" - File cần ghép: {len(df_old)} dòng")

    # 2. Chuẩn hóa tên huyện (Mapping)
    # Đây là danh sách các huyện có tên viết khác nhau giữa 2 file
    name_mapping = {
        'Bogra': 'Bogura',
        'Barisal': 'Barishal',
        'Comilla': 'Cumilla',
        'Jessore': 'Jashore',
        "Cox's Bazar": 'CoxsBazar',
        'Panchagarh': 'Panchagar'
    }

    # Tạo cột tên chuẩn trong file nguồn
    df_new['District_Mapped'] = df_new['name'].replace(name_mapping)

    # 3. Tạo từ điển tra cứu (Lookup Dictionary)
    # Dạng: {'Bagerhat': 5.8, 'Bogura': 6.1, ...}
    ph_lookup = dict(zip(df_new['District_Mapped'], df_new['pH_Final_2022']))

    # 4. Thực hiện thay thế (Update)
    print("Đang cập nhật cột pH...")
    
    # Lưu lại giá trị cũ để so sánh (tùy chọn)
    df_old['pH_Old_Backup'] = df_old['pH']
    
    # Map giá trị mới vào cột pH dựa trên tên huyện (District)
    # map() sẽ trả về NaN nếu không tìm thấy tên huyện, nên ta dùng fillna để giữ lại giá trị cũ nếu cần (hoặc để kiểm tra lỗi)
    df_old['pH'] = df_old['District'].map(ph_lookup)

    # 5. Kiểm tra lỗi (Quan trọng)
    missing_data = df_old[df_old['pH'].isna()]
    if not missing_data.empty:
        print(f"CẢNH BÁO: Có {len(missing_data)} dòng không tìm thấy pH mới (bị Null).")
        print("Các huyện bị thiếu:", missing_data['District'].unique())
        # Nếu muốn giữ lại giá trị cũ cho những dòng bị thiếu:
        # df_old['pH'] = df_old['pH'].fillna(df_old['pH_Old_Backup'])
    else:
        print("THÀNH CÔNG: 100% các dòng đã được cập nhật pH mới.")

    # Xóa cột backup không cần thiết
    if 'pH_Old_Backup' in df_old.columns:
        del df_old['pH_Old_Backup']

    # 6. Lưu file kết quả
    df_old.to_csv(file_ket_qua, index=False)
    print(f"\nĐã lưu file kết quả tại: {file_ket_qua}")
    
    # Hiển thị 5 dòng đầu để kiểm tra
    print("\n5 dòng đầu tiên của file mới:")
    print(df_old[['District', 'pH']].head())

if __name__ == "__main__":
    merge_ph_data()