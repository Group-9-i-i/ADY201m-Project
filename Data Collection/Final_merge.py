import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def merge_all_files():
    print("1. Đang đọc 3 file dữ liệu...")
    
    # Danh sách 3 file cần gộp
    f_names = [
        os.path.join(SCRIPT_DIR, 'Process_Bangladesh_GEE_Indices_Merge.csv'),
        os.path.join(SCRIPT_DIR, 'Process_Bangladesh_soil_data_Merge.csv'),
        os.path.join(SCRIPT_DIR, 'Process_Bangladesh_weather_data_Merge.csv')
    ]
    
    # Nạp toàn bộ dữ liệu vào list các DataFrames
    dfs = [pd.read_csv(f) for f in f_names]

    print("2. Chuẩn hóa lại cấu trúc các cột khóa...")
    # Chuẩn hóa để đảm bảo an toàn tuyệt đối khi ghép (tránh lỗi do thừa dấu cách)
    for df in dfs:
        if 'District' in df.columns:
            df['District'] = df['District'].astype(str).str.strip().str.title()
        if 'Season' in df.columns:
            df['Season'] = df['Season'].astype(str).str.strip().str.title()

    print("3. Bắt đầu quá trình ghép file (Merging)...")
    # Lấy file đầu tiên làm bảng gốc
    merged_df = dfs[0]

    # Duyệt qua 2 file còn lại để ghép dần vào bảng gốc
    for i in range(1, len(dfs)):
        current_df = dfs[i]
        
        # Tìm TẤT CẢ các cột chung giữa 2 bảng (tránh sinh ra các cột bị lặp _x, _y)
        # Bao gồm Area, AP Ratio, District, Season, Avg Temp...
        common_cols = list(set(merged_df.columns).intersection(set(current_df.columns)))
        
        # Thực hiện ghép (Merge)
        merged_df = pd.merge(merged_df, current_df, on=common_cols, how='outer')
        
        print(f" -> Đã ghép file thứ {i+1}. Số dòng hiện tại: {len(merged_df)} | Số cột: {len(merged_df.columns)}")

    # =====================================================================
    # BƯỚC 4: XUẤT FILE MỚI
    # =====================================================================
    # Lưu file ra thư mục chứa script
    output_filename = os.path.join(SCRIPT_DIR, 'Bangladesh_database_Final_Merged.csv')
    
    # (Tùy chọn) Có thể sắp xếp lại vị trí cột cho đẹp, đẩy 4 cột chính lên đầu
    cols = merged_df.columns.tolist()
    primary_keys = ['Area', 'AP Ratio', 'District', 'Season']
    # Loại bỏ primary keys khỏi vị trí hiện tại
    for key in primary_keys:
        if key in cols:
            cols.remove(key)
    # Gắn lại vào đầu danh sách
    final_cols = primary_keys + cols
    merged_df = merged_df[final_cols]

    # Lưu file
    merged_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\n✅ HOÀN TẤT! Đã tạo ra file tổng '{output_filename}'.")
    print(f"📊 Thống kê: File mới có chính xác {len(merged_df)} dòng và chứa đầy đủ {len(merged_df.columns)} cột.")

if __name__ == "__main__":
    merge_all_files()