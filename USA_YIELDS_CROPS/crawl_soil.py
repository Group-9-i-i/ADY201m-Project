import pandas as pd
import requests
import zipfile
import io
import os
from datetime import datetime

# Cấu hình
START_YEAR = 2015
OUTPUT_FOLDER = "US_Soil_Data_Processed"
# URL file dữ liệu gốc của USGS (Chứa toàn bộ dữ liệu đất từng đo được ở Mỹ)
SOURCE_URL = "https://mrdata.usgs.gov/ngdb/soil/ngdbsoil-csv.zip"

def download_and_extract():
    print(f"1. Đang tải dữ liệu gốc từ USGS ({SOURCE_URL})...")
    print("   (File này khoảng 30MB nén, vui lòng đợi...)")
    
    try:
        response = requests.get(SOURCE_URL)
        response.raise_for_status()
        
        print("2. Đang giải nén dữ liệu...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Tìm file .csv trong file zip
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                raise Exception("Không tìm thấy file CSV trong file nén.")
            
            target_file = csv_files[0]
            print(f"   -> Đã tìm thấy file: {target_file}")
            
            # Đọc file CSV vào Pandas (Low_memory=False để tránh cảnh báo)
            print("3. Đang đọc dữ liệu vào bộ nhớ (có thể mất 1-2 phút)...")
            df = pd.read_csv(z.open(target_file), encoding='latin1', low_memory=False)
            return df
            
    except Exception as e:
        print(f"Lỗi nghiêm trọng khi tải: {e}")
        return None

def process_data(df):
    if df is None: return

    # Tạo thư mục lưu kết quả
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        
    print(f"4. Bắt đầu xử lý {len(df)} dòng dữ liệu...")

    # Chuẩn hóa tên cột về chữ thường
    df.columns = [c.lower() for c in df.columns]

    # Xử lý cột thời gian
    # Các tên cột ngày tháng thường gặp trong dữ liệu USGS
    date_cols = ['date_collected', 'col_date', 'date']
    target_date_col = None
    
    for col in date_cols:
        if col in df.columns:
            target_date_col = col
            break
    
    if target_date_col:
        print(f"   -> Sử dụng cột thời gian: {target_date_col}")
        # Chuyển đổi sang datetime, lỗi thì biến thành NaT
        df[target_date_col] = pd.to_datetime(df[target_date_col], errors='coerce')
        
        # Thêm cột Year cho dễ lọc
        df['year_extracted'] = df[target_date_col].dt.year
    else:
        print("   -> CẢNH BÁO: Không tìm thấy cột ngày tháng. Sẽ xuất toàn bộ dữ liệu.")

    # Lấy danh sách tất cả các bang có trong dữ liệu
    if 'state' not in df.columns:
        print("Lỗi: Không tìm thấy cột 'state' để phân loại.")
        return

    states = df['state'].dropna().unique()
    print(f"   -> Tìm thấy dữ liệu của {len(states)} bang/khu vực.")

    # Vòng lặp tách file theo từng bang
    count_saved = 0
    for state in states:
        # Lọc dữ liệu bang hiện tại
        state_df = df[df['state'] == state].copy()
        
        # Lọc theo năm (Nếu tìm thấy cột ngày tháng)
        if target_date_col:
            # Lọc: Lấy dữ liệu từ năm 2015 trở về sau
            # HOẶC lấy dữ liệu không có ngày tháng (để tránh mất mẫu quan trọng bị thiếu ngày)
            recent_data = state_df[
                (state_df['year_extracted'] >= START_YEAR) | 
                (state_df['year_extracted'].isna()) 
            ]
        else:
            recent_data = state_df

        # Nếu có dữ liệu thì lưu file
        if not recent_data.empty:
            # Làm sạch tên file
            safe_state_name = str(state).replace(" ", "_")
            file_name = f"{OUTPUT_FOLDER}/Soil_Data_{safe_state_name}.csv"
            
            # Lưu CSV
            recent_data.to_csv(file_name, index=False)
            print(f"   [OK] Đã lưu {safe_state_name}: {len(recent_data)} dòng (Có chứa Cu, Mg, As...)")
            count_saved += 1
        
    print(f"\n--- HOÀN TẤT ---")
    print(f"Đã lưu dữ liệu của {count_saved} bang vào thư mục '{OUTPUT_FOLDER}'")
    print(f"Lưu ý: Nếu số lượng dòng ít, đó là do thực tế không có mẫu đo mới trong giai đoạn {START_YEAR}-2025.")

if __name__ == "__main__":
    # Bước 1 & 2 & 3: Tải và đọc
    full_dataframe = download_and_extract()
    
    # Bước 4: Xử lý và tách file
    process_data(full_dataframe)