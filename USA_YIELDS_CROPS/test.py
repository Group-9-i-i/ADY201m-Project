import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_natural_data(input_file, output_file):
    print(f"--> Đang đọc file gốc: {input_file}...")
    try:
        df = pd.read_csv(input_file)
        
        # Xác định cột số liệu
        metadata_cols = ['Year', 'State', 'ActivityStartDate', 'Month', 'OrganizationIdentifier']
        value_cols = [c for c in df.columns if c not in metadata_cols]
        
        print(f"--> Các chỉ số cần xử lý: {value_cols}")
        
        # Tạo mốc thời gian 2024-2025
        future_dates = []
        curr = datetime(2024, 1, 15)
        end = datetime(2025, 12, 15)
        while curr <= end:
            future_dates.append(curr)
            curr += timedelta(days=30)
            
        new_rows = []
        states = df['State'].unique()
        
        for state in states:
            state_df = df[df['State'] == state]
            
            # Tính toán xác suất xuất hiện dữ liệu của bang này
            # (Ví dụ: Bang này có hay đo đạc không? Hay lười đo?)
            total_history_rows = len(state_df)
            
            for date_val in future_dates:
                row = {
                    'Year': date_val.year,
                    'State': state,
                    'ActivityStartDate': date_val.strftime('%Y-%m-%d')
                }
                
                for col in value_cols:
                    # Lấy dữ liệu lịch sử
                    valid_series = pd.to_numeric(state_df[col], errors='coerce').dropna()
                    
                    # --- LOGIC QUYẾT ĐỊNH MỚI ---
                    
                    # 1. Nếu lịch sử hoàn toàn trống -> Tương lai cũng để trống
                    if valid_series.empty:
                        row[col] = np.nan
                    else:
                        # 2. Nếu có lịch sử -> Tính toán tham số
                        mu = valid_series.mean()
                        sigma = valid_series.std()
                        
                        # Xử lý trường hợp chỉ có 1 mẫu
                        if np.isnan(sigma): sigma = mu * 0.1
                        if sigma == 0: sigma = 0.001
                        
                        # 3. TẠO SỰ TỰ NHIÊN (Rất quan trọng)
                        # Tính tỷ lệ có dữ liệu trong quá khứ (Data Availability Rate)
                        # Nếu quá khứ cột này bị thủng 30%, thì tương lai cũng nên thủng ~30%
                        availability_rate = len(valid_series) / total_history_rows if total_history_rows > 0 else 0
                        
                        # Tung xúc xắc: Có điền dữ liệu vào tháng này không?
                        if random.random() <= availability_rate:
                            # Sinh dữ liệu chuẩn Gaussian
                            val = np.random.normal(mu, sigma)
                            
                            # Ràng buộc giá trị
                            val = max(0.001, val)
                            if val > mu + 3*sigma: val = mu + 3*sigma
                            
                            row[col] = round(val, 4)
                        else:
                            # Giả lập việc tháng này không đi đo
                            row[col] = np.nan

                new_rows.append(row)
                
        # Gộp và Lưu
        if new_rows:
            df_new = pd.DataFrame(new_rows)
            df_final = pd.concat([df, df_new], ignore_index=True)
            
            df_final['ActivityStartDate'] = pd.to_datetime(df_final['ActivityStartDate'])
            df_final = df_final.sort_values(by=['State', 'ActivityStartDate'])
            
            df_final.to_csv(output_file, index=False)
            print(f"\n[THÀNH CÔNG] File kết quả: {output_file}")
            print("Dữ liệu 2024-2025 đã được sinh ra với các khoảng trống tự nhiên (NaN).")
        else:
            print("[Lỗi] Không sinh được dữ liệu.")

    except Exception as e:
        print(f"[LỖI] {e}")

# --- CHẠY CODE ---
input_filename = "US_AllStates_FullData_20260206.csv"
output_filename = "US_Natural_Pattern_2015_2025.csv"

generate_natural_data(input_filename, output_filename)