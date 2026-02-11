import pandas as pd
import ee
import geemap
import calendar
from datetime import datetime
import re

# ==========================================
# CẤU HÌNH
# ==========================================
PROJECT_ID = 'gen-lang-client-0272496285' 
INPUT_FILE = 'kk_with_full.csv'
OUTPUT_FILE = 'kk_with_full_ndvi_2022_smart_filtered_v2.csv'
YEAR = 2022

# Ngưỡng NDVI để coi là "đạt chuẩn"
NDVI_GOOD_THRESHOLD = 0.7 
# Tỷ lệ phần trăm các giai đoạn phải đạt chuẩn để KHÔNG cần quét lại
# Ví dụ: 0.7 nghĩa là 70% số giai đoạn phải có NDVI >= 0.7
PASS_RATE_THRESHOLD = 0.7

# ==========================================
# 1. KHỞI TẠO GEE
# ==========================================
def init_gee():
    print("[INIT] Đang khởi tạo Google Earth Engine...")
    try:
        ee.Initialize(project=PROJECT_ID)
    except:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)

# ==========================================
# 2. XỬ LÝ NGÀY THÁNG
# ==========================================
def parse_months(period_str):
    if not isinstance(period_str, str) or period_str.strip() == '' or 'No need' in period_str:
        return None, None
    period_str = period_str.lower().replace('.', '')
    months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'sept': 9 
    }
    found_months = []
    for m_name, m_num in months.items():
        if m_name in period_str:
            found_months.append((period_str.find(m_name), m_num))
    found_months.sort()
    if not found_months: return None, None
    return found_months[0][1], found_months[-1][1]

def get_date_range(start_m, end_m, year):
    if start_m is None: return None, None
    start_date = f"{year}-{start_m:02d}-01"
    end_year = year if end_m >= start_m else year + 1
    _, last_day = calendar.monthrange(end_year, end_m)
    end_date = f"{end_year}-{end_m:02d}-{last_day}"
    return start_date, end_date

# ==========================================
# 3. CÁC HÀM LẤY NDVI (MODIS & SENTINEL)
# ==========================================

# Tầng 1: MODIS (250m)
def get_ndvi_modis(feature_geom, start_date, end_date):
    try:
        dataset = ee.ImageCollection('MODIS/006/MOD13Q1') \
                  .filterDate(start_date, end_date) \
                  .select('NDVI')
        if dataset.size().getInfo() == 0: return None
        image = dataset.mean()
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=feature_geom,
            scale=250,
            maxPixels=1e9
        )
        val = stats.get('NDVI').getInfo()
        return val * 0.0001 if val is not None else None
    except:
        return None

# Tầng 2: Sentinel-2 (10m -> scale 30m)
def get_ndvi_sentinel_high_res(feature_geom, start_date, end_date):
    try:
        def maskS2clouds(image):
            qa = image.select('QA60')
            cloudBitMask = 1 << 10
            cirrusBitMask = 1 << 11
            mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
            return image.updateMask(mask).divide(10000)

        dataset = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                  .filterDate(start_date, end_date) \
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
                  .map(maskS2clouds)
        
        if dataset.size().getInfo() == 0: return None
        
        def addNDVI(image):
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return image.addBands(ndvi)
        
        image = dataset.map(addNDVI).select('NDVI').mean()
        
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=feature_geom,
            scale=30, # Tối ưu tốc độ nhưng vẫn chi tiết hơn MODIS nhiều
            maxPixels=1e9
        )
        val = stats.get('NDVI').getInfo()
        return val if val is not None else None
    except Exception as e:
        return None

# ==========================================
# 4. LOGIC SÀNG LỌC THÔNG MINH (SMART FILTER V2)
# ==========================================
def smart_ndvi_extraction(row, geom, year):
    phases = ['Transplant', 'Growth', 'Harvest']
    # Lưu kết quả tạm thời: [(val, start_date, end_date), ...]
    temp_results = []
    
    # --- BƯỚC 1: QUÉT SƠ BỘ BẰNG MODIS (TẦNG 1) ---
    for phase in phases:
        s_m, e_m = parse_months(str(row[phase]))
        if s_m:
            s_d, e_d = get_date_range(s_m, e_m, year)
            val = get_ndvi_modis(geom, s_d, e_d)
            temp_results.append({'val': val, 'start': s_d, 'end': e_d, 'phase': phase})
        else:
            temp_results.append({'val': None, 'start': None, 'end': None, 'phase': phase})

    # --- BƯỚC 2: KIỂM TRA ĐIỀU KIỆN (PASS/FAIL) ---
    # Lấy danh sách các giá trị NDVI hợp lệ (không None)
    valid_vals = [item['val'] for item in temp_results if item['val'] is not None]
    total_valid_phases = len(valid_vals)
    
    # Đếm số giai đoạn có NDVI >= 0.7 (Good Quality)
    good_vals_count = sum(1 for v in valid_vals if v >= NDVI_GOOD_THRESHOLD)
    
    # Tính tỷ lệ đạt chuẩn
    pass_ratio = 0.0
    if total_valid_phases > 0:
        pass_ratio = good_vals_count / total_valid_phases
        
    is_high_quality = False
    # Điều kiện: Nếu tỷ lệ giai đoạn đạt chuẩn > 70% (ví dụ 3 giai đoạn thì cần ít nhất 2 cái tốt, hoặc 3/3)
    if pass_ratio >= PASS_RATE_THRESHOLD:
        is_high_quality = True
        
    final_ndvis = []
    
    if is_high_quality:
        # Giữ nguyên kết quả MODIS
        final_ndvis = [item['val'] for item in temp_results]
    else:
        # --- BƯỚC 3: QUÉT LẠI BẰNG SENTINEL-2 (TẦNG 2) ---
        # print(f"   [!] Huyện {row['District']} tỷ lệ đạt chuẩn thấp ({pass_ratio:.1%}). Chuyển sang Sentinel-2...")
        
        for item in temp_results:
            val_modis = item['val']
            s_d = item['start']
            e_d = item['end']
            
            if s_d is None:
                final_ndvis.append(None)
                continue
                
            # Logic tối ưu: Chỉ quét lại những giai đoạn bị thấp điểm (< 0.7) hoặc bị None
            # Nếu giai đoạn đó đã tốt rồi (>= 0.7) thì giữ nguyên để tiết kiệm thời gian
            if val_modis is not None and val_modis >= NDVI_GOOD_THRESHOLD:
                final_ndvis.append(val_modis)
            else:
                # Quét lại bằng Sentinel-2
                val_sentinel = get_ndvi_sentinel_high_res(geom, s_d, e_d)
                
                # Nếu Sentinel quét ra kết quả, lấy nó. Nếu không (do mây mù), đành dùng lại MODIS
                final_ndvis.append(val_sentinel if val_sentinel is not None else val_modis)

    return final_ndvis[0], final_ndvis[1], final_ndvis[2]

def get_std_dev_season(feature_geom, year):
    # Std Dev dùng MODIS để đảm bảo tính liên tục của chuỗi thời gian
    try:
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        dataset = ee.ImageCollection('MODIS/006/MOD13Q1').filterDate(start, end).select('NDVI')
        std_image = dataset.reduce(ee.Reducer.stdDev())
        stats = std_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=feature_geom, scale=250, maxPixels=1e9)
        val = stats.get('NDVI_stdDev').getInfo()
        return val * 0.0001 if val else None
    except: return None

# ==========================================
# 5. HÀM CHÍNH
# ==========================================
def main():
    init_gee()
    df = pd.read_csv(INPUT_FILE)
    
    print("Đang tải bản đồ hành chính...")
    bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    features = bangladesh_districts.getInfo()['features']
    
    district_geom_map = {}
    for ft in features:
        name = ft['properties']['ADM2_NAME'].lower().replace(' ', '')
        district_geom_map[name] = ee.Geometry(ft['geometry'])
        
    manual_mapping = {
        'bogra': 'bogura', 'barisal': 'barishal', 'comilla': 'cumilla',
        'jessore': 'jashore', "cox'sbazar": 'coxsbazar', 'panchagarh': 'panchagar',
        'brahmanbaria': 'brahamanbaria' 
    }

    print(f"Bắt đầu xử lý {len(df)} dòng...")
    print(f"Tiêu chí: > {PASS_RATE_THRESHOLD*100}% số giai đoạn có NDVI >= {NDVI_GOOD_THRESHOLD} thì giữ MODIS. Ngược lại dùng Sentinel.")

    ndvi_results = {'early': [], 'mid': [], 'late': [], 'std': []}
    
    for index, row in df.iterrows():
        dist_name = str(row['District']).lower().replace(' ', '')
        geom = district_geom_map.get(dist_name) or district_geom_map.get(manual_mapping.get(dist_name))
        
        if geom is None:
            # Fuzzy search
            for k, v in district_geom_map.items():
                if dist_name in k or k in dist_name:
                    geom = v; break
        
        if geom:
            e, m, l = smart_ndvi_extraction(row, geom, YEAR)
            std = get_std_dev_season(geom, YEAR)
            
            ndvi_results['early'].append(e)
            ndvi_results['mid'].append(m)
            ndvi_results['late'].append(l)
            ndvi_results['std'].append(std)
        else:
            print(f"⚠️ Không tìm thấy map: {row['District']}")
            for k in ndvi_results: ndvi_results[k].append(None)

        if index % 5 == 0:
            print(f"   > Đã xử lý {index}/{len(df)} dòng...", end='\r')

    df['NDVI_early'] = ndvi_results['early']
    df['NDVI_mid'] = ndvi_results['mid']
    df['NDVI_late'] = ndvi_results['late']
    df['NDVI_std'] = ndvi_results['std']
    
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ HOÀN THÀNH! File lưu tại: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()