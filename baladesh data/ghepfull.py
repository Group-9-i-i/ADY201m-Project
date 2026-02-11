import pandas as pd
import numpy as np

def update_ndvi_for_ph_file():
    print("Đang khởi tạo và đọc dữ liệu...")
    
    # 1. Đọc dữ liệu
    ndvi_file = 'bangladesh_ndvi_2022_tier1_fast.csv'
    main_file = 'ket_qua_ghep_updated_pH.csv' # File gốc bạn muốn xử lý
    output_file = 'ket_qua_ghep_final_full_2022.csv'

    try:
        ndvi_raw_df = pd.read_csv(ndvi_file)
        main_df = pd.read_csv(main_file)
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file. Chi tiết: {e}")
        return

    print(f"Đã đọc file chính: {len(main_df)} dòng.")

    # 2. Chuẩn hóa tên Huyện (Mapping)
    district_map = {
        'Barishal': 'Barisal', 'Bogura': 'Bogra', 'Brahmanbaria': 'Brahamanbaria',
        'Chattogram': 'Chittagong', 'Cumilla': 'Comilla', 'CoxsBazar': "Cox's Bazar",
        'Jashore': 'Jessore', 'Khagrachari': 'Khagrachhari', 'Moulvibazar': 'Maulvibazar',
        'Chapai Nawabganj': 'Nawabganj', 'Netrokona': 'Netrakona', 'Panchagar': 'Panchagarh'
    }
    
    # Tạo cột lookup tạm
    main_df['Lookup_District'] = main_df['District'].map(lambda x: district_map.get(x, x))

    # 3. Tạo từ điển tra cứu nhanh: (District, Month) -> NDVI
    ndvi_lookup = {}
    for _, row in ndvi_raw_df.iterrows():
        ndvi_lookup[(row['District'], row['Month'])] = row['NDVI_Mean']

    # 4. Hàm xử lý chuỗi tháng
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

    # Helper tính trung bình
    def get_mean(dist, months):
        vals = [ndvi_lookup.get((dist, m)) for m in months if (dist, m) in ndvi_lookup]
        vals = [v for v in vals if v is not None]
        return np.mean(vals) if vals else np.nan

    # 5. Logic tính toán TỔNG HỢP (Tính mới + Điền khuyết)
    def calculate_row(row):
        dist = row['Lookup_District']
        
        # Parse các tháng từ chuỗi
        m_trans = parse_months(row['Transplant'])
        m_grow = parse_months(row['Growth']) # Sẽ rỗng nếu là "No need to do"
        m_harv = parse_months(row['Harvest'])

        # --- A. Tính NDVI Early, Late ---
        early = get_mean(dist, m_trans)
        late = get_mean(dist, m_harv)

        # --- B. Tính NDVI Prev Season ---
        prev = np.nan
        if m_trans:
            # Tháng trước tháng gieo trồng đầu tiên
            start_month = m_trans[0]
            p_month = start_month - 1 if start_month > 1 else 12
            prev = ndvi_lookup.get((dist, p_month), np.nan)

        # --- C. Tính NDVI Mid (Có xử lý điền khuyết) ---
        mid = np.nan
        m_mid_final = [] # Lưu lại tháng mid thực tế để tính std sau này

        if m_grow:
            # Trường hợp bình thường: Có tháng cụ thể
            mid = get_mean(dist, m_grow)
            m_mid_final = m_grow
        elif m_trans and m_harv:
            # Trường hợp "No need to do": Tự động suy luận tháng giữa (Gap Filling)
            last_trans = m_trans[-1] if (m_trans[-1] - m_trans[0] < 6) else m_trans[0]
            first_harv = m_harv[0]
            
            curr = last_trans + 1
            if curr > 12: curr = 1
            
            inferred = []
            while curr != first_harv:
                inferred.append(curr)
                curr += 1
                if curr > 12: curr = 1
                if len(inferred) > 11: break
            
            if inferred:
                mid = get_mean(dist, inferred)
                m_mid_final = inferred
            else:
                # Nếu không có khoảng giữa (liền kề), lấy trung bình Early và Late
                vals = [v for v in [early, late] if not np.isnan(v)]
                if vals: mid = np.mean(vals)

        # --- D. Tính NDVI Std (Độ lệch chuẩn toàn mùa) ---
        # Gộp tất cả các tháng tham gia vào mùa vụ
        all_months = list(set(m_trans + m_harv + m_mid_final))
        all_vals = [ndvi_lookup.get((dist, m)) for m in all_months if (dist, m) in ndvi_lookup]
        all_vals = [v for v in all_vals if v is not None]
        
        std = np.std(all_vals) if all_vals else np.nan

        return pd.Series([early, mid, late, std, prev])

    print("Đang xử lý tính toán và điền dữ liệu (có thể mất vài giây)...")
    
    # Áp dụng logic
    cols = ['NDVI_early', 'NDVI_mid', 'NDVI_late', 'NDVI_std', 'NDVI_prev_season']
    main_df[cols] = main_df.apply(calculate_row, axis=1)

    # Dọn dẹp
    main_df.drop(columns=['Lookup_District'], inplace=True)

    # Kiểm tra kết quả
    print("\nKiểm tra dữ liệu sau khi xử lý:")
    print(main_df[cols].isnull().sum())
    
    # Lưu file
    main_df.to_csv(output_file, index=False)
    print(f"\nHOÀN TẤT! File kết quả đã lưu tại: {output_file}")
    print("Bạn có thể dùng file này làm dữ liệu chuẩn.")

# Chạy chương trình
update_ndvi_for_ph_file()