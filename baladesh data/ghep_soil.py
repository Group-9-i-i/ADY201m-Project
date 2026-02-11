import pandas as pd
import numpy as np

def update_soil_moisture_final():
    print("Đang tải dữ liệu...")
    # 1. Đọc 2 file
    main_df = pd.read_csv('ket_qua_ghep_final_full_pH_2022.csv')
    sm_df = pd.read_csv('Bangladesh_Soil_Moisture_2022_V2.csv')

    print(f"Số dòng thiếu Soil_Moisture_Season ban đầu: {main_df['Soil_Moisture_Season'].isnull().sum()}")

    # 2. Tạo từ điển ánh xạ tên Huyện (Mapping)
    # File SM dùng tên hơi khác file chính, cần map lại
    district_map = {
        'Barishal': 'Barisal',
        'Bogura': 'Bogra',
        'Brahmanbaria': 'Brahamanbaria', # Lưu ý chính tả
        'Chapai Nawabganj': 'Nawabganj',
        'Chattogram': 'Chittagong',
        'Cumilla': 'Comilla',
        'CoxsBazar': "Cox's Bazar",
        'Jashore': 'Jessore',
        'Khagrachari': 'Khagrachhari',
        'Moulvibazar': 'Maulvibazar',
        'Netrokona': 'Netrakona', # Map Main -> SM
        'Panchagar': 'Panchagarh'
    }
    
    # Tạo cột Lookup để tìm kiếm
    main_df['Lookup_District'] = main_df['District'].replace(district_map)

    # 3. Tạo từ điển tra cứu nhanh: (District, Month) -> Soil Moisture
    # Dùng chỉ số 'sm_rootzone' (độ ẩm vùng rễ) vì nó quan trọng nhất cho nông nghiệp
    sm_lookup = {}
    for _, row in sm_df.iterrows():
        sm_lookup[(row['ADM2_NAME'], row['month'])] = row['sm_rootzone']

    # 4. Hàm xử lý chuỗi tháng (Re-use từ các bước trước)
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

    # 5. Logic tính toán và điền khuyết
    def calculate_sm_for_row(row):
        # Lấy danh sách tháng của vụ mùa
        m_trans = parse_months(row['Transplant'])
        m_harv = parse_months(row['Harvest'])
        m_grow = parse_months(row['Growth']) # Có thể rỗng
        
        season_months = []
        
        # Logic ghép tháng: Nếu có Growth thì dùng luôn, nếu không thì tự suy luận khoảng giữa
        if m_trans and m_harv:
            if m_grow:
                season_months = list(set(m_trans + m_grow + m_harv))
            else:
                # Tự động điền khoảng trống (Gap Filling)
                last_trans = m_trans[-1] if (m_trans[-1] - m_trans[0] < 6) else m_trans[0]
                first_harv = m_harv[0]
                
                curr = last_trans
                inferred = [curr]
                while curr != first_harv:
                    curr += 1
                    if curr > 12: curr = 1
                    inferred.append(curr)
                # Cộng thêm tháng thu hoạch
                inferred.extend(m_harv)
                season_months = list(set(inferred))
        else:
            # Fallback
            season_months = list(set(m_trans + m_grow + m_harv))

        # Lấy giá trị Soil Moisture
        dist = row['Lookup_District']
        vals = [sm_lookup.get((dist, m)) for m in season_months if (dist, m) in sm_lookup]
        vals = [v for v in vals if v is not None]
        
        if vals:
            return np.mean(vals)
        return np.nan

    print("Đang tính toán và lấp đầy Soil Moisture...")
    
    # Tính toán cho toàn bộ dataframe
    calculated_sm = main_df.apply(calculate_sm_for_row, axis=1)
    
    # Cập nhật vào cột Soil_Moisture_Season
    # Ưu tiên lấy giá trị tính toán được để đảm bảo đồng bộ với dữ liệu 2022 mới nhất
    # Nếu tính ra NaN thì mới giữ lại giá trị cũ (nếu có)
    main_df['Soil_Moisture_Season'] = calculated_sm.fillna(main_df['Soil_Moisture_Season'])

    # Dọn dẹp
    main_df.drop(columns=['Lookup_District'], inplace=True)

    # Kiểm tra kết quả
    missing_final = main_df['Soil_Moisture_Season'].isnull().sum()
    print(f"Số dòng thiếu Soil_Moisture_Season sau khi xử lý: {missing_final}")
    
    # Lưu file
    output_file = 'ket_qua_ghep_final_full_SM_2022.csv'
    main_df.to_csv(output_file, index=False)
    print(f"Hoàn tất! File đã được lưu tại: {output_file}")

# Chạy hàm
update_soil_moisture_final()