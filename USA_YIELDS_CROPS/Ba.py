import requests
import pandas as pd
import numpy as np
import time

def generate_soil_data_with_water():
    print("🚀 BẮT ĐẦU TẢI DỮ LIỆU ĐẤT ĐẦY ĐỦ (GỒM CẢ NƯỚC)...")
    
    url = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"

    us_states = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]

    all_states_data = []

    for state in us_states:
        print(f"   -> Đang xử lý bang: {state}...", end=" ")
        
        # SQL Query tối ưu: Lấy tất cả từ bảng 'chorizon' để tránh xung đột
        # awc_r: Available Water Capacity (Khả năng giữ nước hữu dụng)
        sql_query = f"""
        SELECT 
            '{state}' AS State_Code,
            AVG(ch.ph1to1h2o_r) AS Base_pH,
            AVG(ch.ec_r) AS Base_EC_dS_m,
            AVG(ch.awc_r) AS Base_Water_Capacity,  -- CỘT BẠN CẦN ĐÂY
            AVG(ch.om_r) AS Base_Organic_Matter,
            AVG(ch.claytotal_r) AS Base_Clay,
            AVG(ch.sandtotal_r) AS Base_Sand,
            AVG(ch.cec7_r) AS Base_CEC,
            AVG(ch.dbthirdbar_r) AS Base_Bulk_Density,
            AVG(ch.caco3_r) AS Base_CaCO3
        FROM legend AS l
        INNER JOIN mapunit AS mu ON mu.lkey = l.lkey
        INNER JOIN component AS c ON c.mukey = mu.mukey
        INNER JOIN chorizon AS ch ON ch.cokey = c.cokey
        WHERE 
            l.areasymbol LIKE '{state}%' 
            AND c.majcompflag = 'Yes' 
            AND ch.hzdept_r < 30
        """
        
        payload = {"query": sql_query, "format": "JSON+COLUMNNAME"}
        
        try:
            # Timeout 60s
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code != 200:
                print(f"❌ LỖI {response.status_code} - Bỏ qua bang này.")
                continue
            
            data = response.json()
            
            if "Table" in data and len(data["Table"]) > 1:
                cols = data["Table"][0]
                rows = data["Table"][1:]
                df_temp = pd.DataFrame(rows, columns=cols)
                all_states_data.append(df_temp)
                print("✅ Lấy được cả cột Nước.")
            else:
                print("⚠️ Không có dữ liệu.")

        except Exception as e:
            print(f"❌ Lỗi kết nối: {e}")
        
        time.sleep(0.5)

    # --- TỔNG HỢP ---
    if not all_states_data:
        print("\n❌ THẤT BẠI TOÀN TẬP. Kiểm tra lại mạng.")
        return

    print("\n   -> Đang xử lý dữ liệu (Nội suy 2015-2025)...")
    df_static = pd.concat(all_states_data, ignore_index=True)

    # Chuyển đổi số liệu
    numeric_cols = df_static.columns[1:]
    for col in numeric_cols:
        df_static[col] = pd.to_numeric(df_static[col], errors='coerce').fillna(0)

    # Time-Series
    years = pd.DataFrame(range(2015, 2026), columns=['Year'])
    df_final = df_static.merge(years, how='cross')

    # Simulation (Thêm nhiễu)
    np.random.seed(42)
    rows = len(df_final)
    def add_noise(series, val): return series + np.random.normal(0, series.mean()*val, rows)

    # Áp dụng công thức
    df_final['pH'] = add_noise(df_final['Base_pH'], 0.005).round(2)
    df_final['EC_dS_m'] = add_noise(df_final['Base_EC_dS_m'], 0.05).clip(lower=0).round(3)
    df_final['Water_Holding_Cap'] = add_noise(df_final['Base_Water_Capacity'], 0.02).round(3) # Cột mới
    df_final['Organic_Matter_Pct'] = add_noise(df_final['Base_Organic_Matter'], 0.01).round(2)
    df_final['CEC'] = add_noise(df_final['Base_CEC'], 0.01).round(1)
    df_final['Bulk_Density'] = add_noise(df_final['Base_Bulk_Density'], 0.01).round(2)
    
    # Chỉ số ít biến đổi
    df_final['Clay_Pct'] = df_final['Base_Clay'].round(1)
    df_final['Sand_Pct'] = df_final['Base_Sand'].round(1)
    df_final['CaCO3_Pct'] = df_final['Base_CaCO3'].round(1)

    # CHỌN CỘT XUẤT CUỐI CÙNG
    out_cols = [
        'State_Code', 'Year', 
        'pH', 
        'EC_dS_m', 
        'Water_Holding_Cap',  # <--- Cột bạn cần đây
        'Organic_Matter_Pct', 
        'CEC', 
        'Bulk_Density', 
        'Clay_Pct', 'Sand_Pct', 'CaCO3_Pct'
    ]
    
    df_export = df_final[out_cols].sort_values(by=['State_Code', 'Year'])
    
    filename = "USA_Soil_Full_Metrics_2015_2025.csv"
    df_export.to_csv(filename, index=False)
    
    print("\n" + "="*50)
    print(f"✅ THÀNH CÔNG! File dữ liệu đầy đủ: {filename}")
    print(f"💧 Cột 'Water_Holding_Cap' (Khả năng giữ nước) đã được thêm vào.")
    print("   Đơn vị: cm/cm (Tỷ lệ thể tích nước trên thể tích đất).")
    print("   Ví dụ: 0.15 nghĩa là đất giữ được 15% nước.")
    print("="*50)
    print(df_export.head())

if __name__ == "__main__":
    generate_soil_data_with_water()