import pandas as pd
import numpy as np

def merge_dataframes():
    print("1. Đang đọc các file dữ liệu...")
    # Đọc file gốc (Main)
    main_df = pd.read_csv('Bangladesh_main_data.csv')
    
    # Đọc 3 file đã qua xử lý (Processed)
    weather_df = pd.read_csv('Process_Bangladesh_weather_data.csv')
    soil_df = pd.read_csv('Process_Bangladesh_soil_data.csv')
    sm_df = pd.read_csv('Process_Bangladesh_Soil_Moisture_data.csv')

    # Chuẩn hóa chung: Đảm bảo cột District khớp định dạng chữ hoa/thường, loại bỏ khoảng trắng
    main_df['District'] = main_df['District'].astype(str).str.strip().str.title()
    weather_df['District'] = weather_df['District'].astype(str).str.strip().str.title()
    soil_df['District'] = soil_df['District'].astype(str).str.strip().str.title()
    sm_df['District'] = sm_df['District'].astype(str).str.strip().str.title()
    
    # Chuẩn hóa cột Season
    if 'Season' in weather_df.columns:
        main_df['Season'] = main_df['Season'].astype(str).str.strip().str.title()
        weather_df['Season'] = weather_df['Season'].astype(str).str.strip().str.title()

    # =====================================================================
    # FILE 1: GHÉP DỮ LIỆU THỜI TIẾT (WEATHER)
    # =====================================================================
    print("2. Đang ghép file Thời tiết (Weather)...")
    weather_merged = pd.merge(main_df, weather_df, on=['District', 'Season'], how='left')
    weather_merged.to_csv('Process_Bangladesh_weather_data_Merge.csv', index=False, encoding='utf-8-sig')
    print(" -> Đã tạo Process_Bangladesh_weather_data_Merge.csv")

    # =====================================================================
    # FILE 2: GHÉP DỮ LIỆU ĐẤT (SOIL)
    # =====================================================================
    print("3. Đang ghép file Đất (Soil)...")
    
    # ---- SỬA LỖI THIẾU TỌA ĐỘ CHO JHALLOKATI ----
    # Tìm dòng của Jhallokati và điền tọa độ nếu nó đang bị NaN
    mask_jhallokati = soil_df['District'] == 'Jhallokati'
    soil_df.loc[mask_jhallokati, 'Latitude'] = soil_df.loc[mask_jhallokati, 'Latitude'].fillna(22.6406)
    soil_df.loc[mask_jhallokati, 'Longitude'] = soil_df.loc[mask_jhallokati, 'Longitude'].fillna(90.1987)
    # ---------------------------------------------

    soil_merged = pd.merge(main_df, soil_df, on='District', how='left')
    soil_merged.to_csv('Process_Bangladesh_soil_data_Merge.csv', index=False, encoding='utf-8-sig')
    print(" -> Đã tạo Process_Bangladesh_soil_data_Merge.csv")

    # =====================================================================
    # FILE 3: GHÉP DỮ LIỆU ĐỘ ẨM (SOIL MOISTURE)
    # =====================================================================
    print("4. Đang ghép file Độ ẩm đất (Soil Moisture)...")
    
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    def parse_months(date_str):
        if not isinstance(date_str, str): return []
        s = date_str.lower().strip()
        if 'no need' in s: return []
        if 'throughout' in s or 'year' in s: return list(range(1, 13))
        
        s = s.replace(',', ' ').replace('-', ' to ').replace('mid', '').replace('end', '')
        parts = s.split()
        found_months = []
        for p in parts:
            for k, v in month_map.items():
                if p == k or (len(p) >= 3 and p.startswith(k[:3])):
                    found_months.append(v)
                    break
        
        if 'to' in parts and len(found_months) >= 2:
            start, end = found_months[0], found_months[-1]
            if start <= end: return list(range(start, end + 1))
            else: return list(range(start, 13)) + list(range(1, end + 1))
            
        return sorted(list(set(found_months)))

    sm_numeric_cols = ['sm_surface', 'sm_rootzone', 'Rootzone_Surface_Diff', 'Moisture_Ratio']
    sm_lookup = {}
    for _, row in sm_df.iterrows():
        sm_lookup[(row['District'], row['month'])] = row[sm_numeric_cols].to_dict()

    def calculate_sm_for_main(row):
        m_trans = parse_months(row['Transplant'])
        m_grow = parse_months(row['Growth'])
        m_harv = parse_months(row['Harvest'])
        
        season_months = list(set(m_trans + m_grow + m_harv))
        dist = row['District']
        
        if not season_months:
            return pd.Series([np.nan] * len(sm_numeric_cols) + ['Unknown'])
            
        collected_data = {col: [] for col in sm_numeric_cols}
        for m in season_months:
            if (dist, m) in sm_lookup:
                for col in sm_numeric_cols:
                    collected_data[col].append(sm_lookup[(dist, m)][col])
        
        avg_results = []
        for col in sm_numeric_cols:
            if collected_data[col]:
                avg_results.append(np.mean(collected_data[col]))
            else:
                avg_results.append(np.nan)
                
        avg_rootzone = avg_results[1]
        if pd.isna(avg_rootzone):
            cat = 'Unknown'
        elif avg_rootzone < 0.15:
            cat = 'High Stress'
        elif avg_rootzone < 0.25:
            cat = 'Moderate'
        else:
            cat = 'Optimal'
            
        return pd.Series(avg_results + [cat])

    sm_result_cols = sm_numeric_cols + ['Water_Availability_Cat']
    sm_calculated_df = main_df.apply(calculate_sm_for_main, axis=1)
    sm_calculated_df.columns = sm_result_cols
    
    sm_merged = pd.concat([main_df, sm_calculated_df], axis=1)
    
    for col in sm_numeric_cols:
        sm_merged[col] = sm_merged[col].round(4)
        
    sm_merged.to_csv('Process_Bangladesh_Soil_Moisture_data_Merge.csv', index=False, encoding='utf-8-sig')
    print(" -> Đã tạo Process_Bangladesh_Soil_Moisture_data_Merge.csv")

    print("\n✅ HOÀN TẤT! Jhallokati đã được điền đủ tọa độ. 3 file đã được lưu thành công.")

if __name__ == "__main__":
    merge_dataframes()