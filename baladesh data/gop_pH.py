import pandas as pd
import numpy as np
import calendar

# 1. Đọc dữ liệu
kk_df = pd.read_csv('kk_with_ph.csv')
ndvi_df = pd.read_csv('bangladesh_ndvi_2022_REAL_DATA_ONLY_20260207_234758.csv')

# 2. XỬ LÝ DỮ LIỆU NDVI (Sửa tên NDVI để khớp với KK)
# Chuyển tên quận trong NDVI về chữ thường để dễ xử lý map
ndvi_df['District_Lower'] = ndvi_df['District'].str.lower().str.strip()

# Pivot table: Index là tên quận (chữ thường), Cột là Tháng
ndvi_pivot = ndvi_df.pivot_table(index='District_Lower', columns='Month', values='NDVI', aggfunc='mean')

# TỪ ĐIỂN ÁNH XẠ: Key = Tên trong NDVI (viết thường) -> Value = Tên trong KK_WITH_PH
# Mục đích: Đổi tên index của bảng NDVI thành tên chuẩn của KK
ndvi_to_kk_map = {
    'barisal': 'Barishal',
    'chittagong': 'Chattogram',
    'comilla': 'Cumilla',
    'jessore': 'Jashore',
    'bogra': 'Bogura',
    'brahamanbaria': 'Brahmanbaria', # Sửa lỗi chính tả trong file NDVI
    'nawabganj': 'Chapai Nawabganj',
    "cox's bazar": 'CoxsBazar',      # File KK viết liền
    'jhalokati': 'Jhallokati',       # File KK có 2 chữ 'l'
    'khagrachhari': 'Khagrachari',   # File KK ít hơn 1 chữ 'h'
    'maulvibazar': 'Moulvibazar',
    'netrakona': 'Netrokona',
    'panchagarh': 'Panchagar'        # File KK không có 'h' cuối
}

# Đổi tên index của ndvi_pivot
new_index = []
for name in ndvi_pivot.index:
    # Nếu tên có trong map thì đổi sang tên KK, nếu không thì viết hoa chữ cái đầu (Title case) để khớp
    if name in ndvi_to_kk_map:
        new_index.append(ndvi_to_kk_map[name])
    else:
        new_index.append(name.title()) # ví dụ: dhaka -> Dhaka

ndvi_pivot.index = new_index

# 3. HÀM XỬ LÝ THỜI GIAN (Giữ nguyên như trước)
month_map = {m.lower(): i for i, m in enumerate(calendar.month_name) if i > 0}
month_map.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if i > 0})
month_map['sept'] = 9

def parse_month_range(text):
    if pd.isna(text) or not isinstance(text, str): return []
    text = text.lower().strip()
    if 'throuout' in text or 'year' in text: return list(range(1, 13))
    if 'no need' in text: return []
    
    if ' to ' in text: parts = text.split(' to ')
    elif '-' in text: parts = text.split('-')
    else: return [month_map.get(text)] if month_map.get(text) else []
    
    start, end = month_map.get(parts[0].strip()), month_map.get(parts[1].strip())
    if not start or not end: return []
    
    if start <= end: return list(range(start, end + 1))
    else: return list(range(start, 13)) + list(range(1, end + 1))

# 4. TÍNH TOÁN VÀ BỔ SUNG CỘT
def calculate_ndvi_metrics(row):
    # Lấy tên quận trực tiếp từ file KK (không cần map nữa vì NDVI đã đổi theo KK rồi)
    district = row['District'] 
    
    # Kiểm tra xem quận này có trong bảng NDVI (đã đổi tên) chưa
    if district not in ndvi_pivot.index:
        # Fallback: Thử tìm dạng chữ thường hoặc in hoa nếu chưa khớp chính xác
        # Nhưng với bước map ở trên thì tỷ lệ khớp đã rất cao.
        return pd.Series([None] * 5)
    
    ndvi_vals = ndvi_pivot.loc[district]
    
    months_early = parse_month_range(row['Transplant'])
    months_mid = parse_month_range(row['Growth'])
    months_late = parse_month_range(row['Harvest'])
    
    def get_mean(months):
        valid_m = [m for m in months if m in ndvi_vals.index]
        return ndvi_vals[valid_m].mean() if valid_m else None

    val_early = get_mean(months_early)
    val_mid = get_mean(months_mid)
    val_late = get_mean(months_late)
    
    # Std
    all_months = set(months_early + months_mid + months_late)
    valid_all = [m for m in all_months if m in ndvi_vals.index]
    val_std = ndvi_vals[valid_all].std() if valid_all else None
    
    # Prev Season
    start_month = months_early[0] if months_early else (months_mid[0] if months_mid else None)
    if start_month:
        prev_m = start_month - 1 if start_month > 1 else 12
        val_prev = ndvi_vals[prev_m] if prev_m in ndvi_vals.index else None
    else:
        val_prev = None
        
    return pd.Series([val_early, val_mid, val_late, val_std, val_prev])

# Áp dụng
cols = ['NDVI_early', 'NDVI_mid', 'NDVI_late', 'NDVI_std', 'NDVI_prev_season']
kk_df[cols] = kk_df.apply(calculate_ndvi_metrics, axis=1)

# Lưu file (Tên quận được giữ nguyên gốc)
kk_df.to_csv('kk_with_ph_ndvi_sync_kk_names.csv', index=False)
print("Hoàn tất! File mới vẫn giữ nguyên tên quận gốc của bạn.")
print(kk_df[['District', 'Season', 'NDVI_mid']].head())