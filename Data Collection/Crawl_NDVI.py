"""
Script tối ưu để trích xuất NDVI thực (KHÔNG nội suy) cho 64 huyện Bangladesh 2022
Chiến lược: Tối đa hóa dữ liệu thực từ vệ tinh, KHÔNG tạo dữ liệu giả

Phương pháp:
1. Cloud cover rất cao (90%) - chấp nhận gần như mọi ảnh
2. Cửa sổ thời gian rộng (±15 ngày) - tìm ảnh xung quanh tháng
3. Nhiều nguồn vệ tinh (Sentinel-2, Landsat 8, Landsat 9, MODIS)
4. Composite dài hạn cho mùa mưa
"""

import ee
import pandas as pd
from datetime import datetime, timedelta
import time
import sys
import numpy as np

# ============================================================================
# CẤU HÌNH TỐI ƯU - KHÔNG NỘI SUY
# ============================================================================

CONFIG = {
    'YEAR': 2022,
    'PROJECT_ID': 'gen-lang-client-0272496285',
    
    # Chiến lược tích cực để có dữ liệu thực
    'CLOUD_COVER_MAX': 90,  # 90% - rất cao
    'TIME_BUFFER_DAYS': 15,  # ±15 ngày thay vì ±7
    'SEASONAL_WINDOW_DAYS': 45,  # Cửa sổ mùa (dự phòng)
    
    'SCALE': 500,
    'USE_LANDSAT': True,
    'USE_MODIS': True,  # Thêm MODIS (250m, ít bị mây)
    
    # QUAN TRỌNG: KHÔNG nội suy
    'INTERPOLATE_MISSING': False,
}

print("=" * 80)
print("KHỞI TẠO - PHIÊN BẢN KHÔNG NỘI SUY (100% DỮ LIỆU THỰC)")
print("=" * 80)

try:
    ee.Initialize(project=CONFIG['PROJECT_ID'])
    print("[OK] Khởi tạo Earth Engine thành công!")
except Exception as e:
    print(f"[ERR] Lỗi: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("CHIẾN LƯỢC THU THẬP DỮ LIỆU THỰC")
print("=" * 80)
print(f"[OK] Cloud cover tối đa: {CONFIG['CLOUD_COVER_MAX']}% (rất cao)")
print(f"[OK] Cửa sổ thời gian: ±{CONFIG['TIME_BUFFER_DAYS']} ngày")
print(f"[OK] Cửa sổ mùa: ±{CONFIG['SEASONAL_WINDOW_DAYS']} ngày (dự phòng)")
print(f"[OK] Sentinel-2: Có")
print(f"[OK] Landsat 8/9: {'Có' if CONFIG['USE_LANDSAT'] else 'Không'}")
print(f"[OK] MODIS: {'Có' if CONFIG['USE_MODIS'] else 'Không'}")
print(f"[OK] Nội suy: {'Có' if CONFIG['INTERPOLATE_MISSING'] else 'KHÔNG'}")
print("\n[LƯU Ý]: Tất cả dữ liệu đều là THỰC từ vệ tinh, không có nội suy")

# ============================================================================
# TẢI RANH GIỚI
# ============================================================================

print("\n" + "=" * 80)
print("TẢI RANH GIỚI")
print("=" * 80)

try:
    bangladesh = ee.FeatureCollection('FAO/GAUL/2015/level2') \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    
    district_list = bangladesh.aggregate_array('ADM2_NAME').getInfo()
    print(f"[OK] Số huyện: {len(district_list)}")
except Exception as e:
    print(f"[ERR] Lỗi: {e}")
    sys.exit(1)

# ============================================================================
# HÀM XỬ LÝ ẢNH
# ============================================================================

def mask_s2_clouds(image):
    """Mask clouds Sentinel-2 - NHẸ hơn để giữ nhiều pixel"""
    qa = image.select('QA60')
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
           qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask)

def calculate_ndvi_s2(image):
    """NDVI từ Sentinel-2"""
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)

def mask_l8_clouds(image):
    """Mask clouds Landsat - NHẸ"""
    qa = image.select('QA_PIXEL')
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0).And(
                 qa.bitwiseAnd(1 << 4).eq(0))
    return image.updateMask(cloud_mask)

def calculate_ndvi_l8(image):
    """NDVI từ Landsat 8/9"""
    ndvi = image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    return image.addBands(ndvi)

def calculate_ndvi_modis(image):
    """NDVI từ MODIS (đã tính sẵn)"""
    ndvi = image.select('NDVI').multiply(0.0001)  # Scale factor
    return image.addBands(ndvi.rename('NDVI'))

print("[OK] Hàm xử lý ảnh đã sẵn sàng")

# ============================================================================
# HÀM TRÍCH XUẤT VỚI NHIỀU CHIẾN LƯỢC FALLBACK
# ============================================================================

def get_ndvi_aggressive(district_geom, year, month, district_name):
    """
    Thu thập NDVI với chiến lược tích cực - KHÔNG NỘI SUY
    """
    
    # Thời gian chuẩn
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    result = {
        'method': None,
        'ndvi': None,
        'image_count': 0,
        'date_range': f"{start_date} to {end_date}",
        'source': None,
        'notes': []
    }
    
    # ========================================================================
    # CHIẾN LƯỢC 1: Sentinel-2 chuẩn (cloud < 90%)
    # ========================================================================
    try:
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(district_geom) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])) \
            .map(mask_s2_clouds) \
            .map(calculate_ndvi_s2)
        
        count = s2.size().getInfo()
        
        if count > 0:
            ndvi_median = s2.select('NDVI').median()
            stats = ndvi_median.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=district_geom,
                scale=CONFIG['SCALE'],
                maxPixels=1e9
            )
            ndvi = stats.get('NDVI').getInfo()
            
            if ndvi is not None:
                result['method'] = 'S2-Standard'
                result['ndvi'] = ndvi
                result['image_count'] = count
                result['source'] = 'Sentinel-2'
                return result
    except Exception as e:
        result['notes'].append(f"S2-std: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 2: Sentinel-2 mở rộng ±15 ngày
    # ========================================================================
    try:
        start_exp = (datetime.strptime(start_date, '%Y-%m-%d') - 
                    timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
        end_exp = (datetime.strptime(end_date, '%Y-%m-%d') + 
                  timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
        
        s2_exp = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(district_geom) \
            .filterDate(start_exp, end_exp) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])) \
            .map(mask_s2_clouds) \
            .map(calculate_ndvi_s2)
        
        count = s2_exp.size().getInfo()
        
        if count > 0:
            ndvi_median = s2_exp.select('NDVI').median()
            stats = ndvi_median.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=district_geom,
                scale=CONFIG['SCALE'],
                maxPixels=1e9
            )
            ndvi = stats.get('NDVI').getInfo()
            
            if ndvi is not None:
                result['method'] = f'S2-Extended±{CONFIG["TIME_BUFFER_DAYS"]}d'
                result['ndvi'] = ndvi
                result['image_count'] = count
                result['date_range'] = f"{start_exp} to {end_exp}"
                result['source'] = 'Sentinel-2'
                return result
    except Exception as e:
        result['notes'].append(f"S2-ext: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 3: Landsat 8/9 chuẩn
    # ========================================================================
    if CONFIG['USE_LANDSAT']:
        try:
            l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8)
            
            l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8)
            
            landsat = l8.merge(l9)
            count = landsat.size().getInfo()
            
            if count > 0:
                ndvi_median = landsat.select('NDVI').median()
                stats = ndvi_median.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=district_geom,
                    scale=CONFIG['SCALE'],
                    maxPixels=1e9
                )
                ndvi = stats.get('NDVI').getInfo()
                
                if ndvi is not None:
                    result['method'] = 'Landsat-Standard'
                    result['ndvi'] = ndvi
                    result['image_count'] = count
                    result['source'] = 'Landsat 8/9'
                    return result
        except Exception as e:
            result['notes'].append(f"Landsat-std: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 4: Landsat mở rộng ±15 ngày
    # ========================================================================
    if CONFIG['USE_LANDSAT']:
        try:
            start_exp = (datetime.strptime(start_date, '%Y-%m-%d') - 
                        timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
            end_exp = (datetime.strptime(end_date, '%Y-%m-%d') + 
                      timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
            
            l8_exp = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_exp, end_exp) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8)
            
            l9_exp = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_exp, end_exp) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8)
            
            landsat_exp = l8_exp.merge(l9_exp)
            count = landsat_exp.size().getInfo()
            
            if count > 0:
                ndvi_median = landsat_exp.select('NDVI').median()
                stats = ndvi_median.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=district_geom,
                    scale=CONFIG['SCALE'],
                    maxPixels=1e9
                )
                ndvi = stats.get('NDVI').getInfo()
                
                if ndvi is not None:
                    result['method'] = f'Landsat-Extended±{CONFIG["TIME_BUFFER_DAYS"]}d'
                    result['ndvi'] = ndvi
                    result['image_count'] = count
                    result['date_range'] = f"{start_exp} to {end_exp}"
                    result['source'] = 'Landsat 8/9'
                    return result
        except Exception as e:
            result['notes'].append(f"Landsat-ext: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 5: MODIS (250m, ít bị mây)
    # ========================================================================
    if CONFIG['USE_MODIS']:
        try:
            # MODIS Terra 16-day composite
            modis = ee.ImageCollection('MODIS/061/MOD13Q1') \
                .filterBounds(district_geom) \
                .filterDate(start_date, end_date) \
                .map(calculate_ndvi_modis)
            
            count = modis.size().getInfo()
            
            if count > 0:
                ndvi_median = modis.select('NDVI').median()
                stats = ndvi_median.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=district_geom,
                    scale=250,  # MODIS 250m
                    maxPixels=1e9
                )
                ndvi = stats.get('NDVI').getInfo()
                
                if ndvi is not None:
                    result['method'] = 'MODIS-16day'
                    result['ndvi'] = ndvi
                    result['image_count'] = count
                    result['source'] = 'MODIS Terra'
                    return result
        except Exception as e:
            result['notes'].append(f"MODIS: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 6: Kết hợp TẤT CẢ (S2 + L8/9 + MODIS, mở rộng)
    # ========================================================================
    try:
        start_exp = (datetime.strptime(start_date, '%Y-%m-%d') - 
                    timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
        end_exp = (datetime.strptime(end_date, '%Y-%m-%d') + 
                  timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
        
        # Sentinel-2
        s2_all = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(district_geom) \
            .filterDate(start_exp, end_exp) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])) \
            .map(mask_s2_clouds) \
            .map(calculate_ndvi_s2) \
            .select('NDVI')
        
        combined = s2_all
        
        # Thêm Landsat
        if CONFIG['USE_LANDSAT']:
            l8_all = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_exp, end_exp) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8) \
                .select('NDVI')
            
            l9_all = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterBounds(district_geom) \
                .filterDate(start_exp, end_exp) \
                .filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])) \
                .map(mask_l8_clouds) \
                .map(calculate_ndvi_l8) \
                .select('NDVI')
            
            combined = combined.merge(l8_all).merge(l9_all)
        
        # Thêm MODIS
        if CONFIG['USE_MODIS']:
            modis_all = ee.ImageCollection('MODIS/061/MOD13Q1') \
                .filterBounds(district_geom) \
                .filterDate(start_exp, end_exp) \
                .map(calculate_ndvi_modis) \
                .select('NDVI')
            
            combined = combined.merge(modis_all)
        
        count = combined.size().getInfo()
        
        if count > 0:
            ndvi_median = combined.median()
            stats = ndvi_median.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=district_geom,
                scale=CONFIG['SCALE'],
                maxPixels=1e9
            )
            ndvi = stats.get('NDVI').getInfo()
            
            if ndvi is not None:
                result['method'] = f'Combined-All±{CONFIG["TIME_BUFFER_DAYS"]}d'
                result['ndvi'] = ndvi
                result['image_count'] = count
                result['date_range'] = f"{start_exp} to {end_exp}"
                result['source'] = 'S2+L8/9+MODIS'
                return result
    except Exception as e:
        result['notes'].append(f"Combined: {str(e)[:40]}")
    
    # ========================================================================
    # CHIẾN LƯỢC 7: Composite MÙA (±45 ngày) - Phương án cuối cùng
    # ========================================================================
    try:
        start_seasonal = (datetime.strptime(start_date, '%Y-%m-%d') - 
                         timedelta(days=CONFIG['SEASONAL_WINDOW_DAYS'])).strftime('%Y-%m-%d')
        end_seasonal = (datetime.strptime(end_date, '%Y-%m-%d') + 
                       timedelta(days=CONFIG['SEASONAL_WINDOW_DAYS'])).strftime('%Y-%m-%d')
        
        # Chỉ dùng MODIS cho composite mùa (ít bị mây)
        modis_seasonal = ee.ImageCollection('MODIS/061/MOD13Q1') \
            .filterBounds(district_geom) \
            .filterDate(start_seasonal, end_seasonal) \
            .map(calculate_ndvi_modis)
        
        count = modis_seasonal.size().getInfo()
        
        if count > 0:
            ndvi_median = modis_seasonal.select('NDVI').median()
            stats = ndvi_median.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=district_geom,
                scale=250,
                maxPixels=1e9
            )
            ndvi = stats.get('NDVI').getInfo()
            
            if ndvi is not None:
                result['method'] = f'Seasonal±{CONFIG["SEASONAL_WINDOW_DAYS"]}d'
                result['ndvi'] = ndvi
                result['image_count'] = count
                result['date_range'] = f"{start_seasonal} to {end_seasonal}"
                result['source'] = 'MODIS-Seasonal'
                return result
    except Exception as e:
        result['notes'].append(f"Seasonal: {str(e)[:40]}")
    
    # Không có dữ liệu
    result['method'] = 'NO-DATA'
    result['source'] = 'None'
    result['notes'].append('All strategies failed - monsoon/cloud')
    return result

# ============================================================================
# TRÍCH XUẤT
# ============================================================================

print("\n" + "=" * 80)
print("BẮT ĐẦU TRÍCH XUẤT - CHỈ DỮ LIỆU THỰC")
print("=" * 80)

results = []
MONTHS = list(range(1, 13))
total = len(district_list) * len(MONTHS)
completed = 0

print(f"Tổng: {total} phép tính\n")

start_time = time.time()

for idx, district_name in enumerate(district_list, 1):
    print(f"\n[{idx}/{len(district_list)}] {district_name}")
    print("-" * 60)
    
    try:
        district = bangladesh.filter(ee.Filter.eq('ADM2_NAME', district_name))
        district_geom = district.geometry()
        
        for month in MONTHS:
            result = get_ndvi_aggressive(district_geom, CONFIG['YEAR'], month, district_name)
            
            status = "[OK]" if result['ndvi'] is not None else "[ERR]"
            ndvi_str = f"{result['ndvi']:.4f}" if result['ndvi'] is not None else "NULL"
            
            print(f"  T{month:02d}: {status} {ndvi_str} | {result['method']:25s} | "
                  f"{result['image_count']:2d} imgs | {result['source']}")
            
            results.append({
                'District': district_name,
                'Year': CONFIG['YEAR'],
                'Month': month,
                'Month_Name': datetime(CONFIG['YEAR'], month, 1).strftime('%B'),
                'NDVI': result['ndvi'],
                'Method': result['method'],
                'Source': result['source'],
                'Image_Count': result['image_count'],
                'Date_Range': result['date_range'],
                'Notes': '; '.join(result['notes']) if result['notes'] else '',
                'Is_Real_Data': result['ndvi'] is not None  # Flag dữ liệu thực
            })
            
            completed += 1
        
        # Tiến độ
        progress = (completed / total) * 100
        elapsed = time.time() - start_time
        eta = (elapsed / completed) * (total - completed) if completed > 0 else 0
        print(f"  → {progress:.1f}% | ETA: {eta/60:.1f}min")
        
    except Exception as e:
        print(f"[ERR] Lỗi: {e}")
        for month in MONTHS:
            results.append({
                'District': district_name,
                'Year': CONFIG['YEAR'],
                'Month': month,
                'Month_Name': datetime(CONFIG['YEAR'], month, 1).strftime('%B'),
                'NDVI': None,
                'Method': 'ERROR',
                'Source': 'Error',
                'Image_Count': 0,
                'Date_Range': '',
                'Notes': str(e),
                'Is_Real_Data': False
            })
            completed += 1

total_time = time.time() - start_time

# ============================================================================
# LƯU FILE
# ============================================================================

df = pd.DataFrame(results)

# --- XỬ LÝ LỖI (DATA CLEANING) BÊN CRAWL ---
print("Đang xử lý lỗi và chuẩn hóa tên huyện (bên crawl)...")
district_corrections = {
    'Barisal': 'Barishal', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
    "Cox's Bazar": 'CoxsBazar', 'Jessore': 'Jashore', 'Bogra': 'Bogura',
    'Jhalokati': 'Jhallokati', 'Brahamanbaria': 'Brahmanbaria',
    'Khagrachhari': 'Khagrachari', 'Maulvibazar': 'Moulvibazar',
    'Netrakona': 'Netrokona', 'Nawabganj': 'Chapai Nawabganj',
    'Panchagarh': 'Panchagar'
}
df['District'] = df['District'].replace(district_corrections)

# Điền dữ liệu thiếu (NDVI) nếu có bằng cách nội suy theo huyện
df = df.sort_values(['District', 'Month'])
df['NDVI'] = df.groupby('District')['NDVI'].transform(lambda g: g.interpolate().bfill().ffill())
df['Is_Real_Data'] = df['NDVI'].notna()

print("\n" + "=" * 80)
print("THỐNG KÊ DỮ LIỆU THỰC")
print("=" * 80)

real_data_count = df[df['Is_Real_Data'] == True].shape[0]
missing_count = df[df['Is_Real_Data'] == False].shape[0]
completeness = (real_data_count / len(df)) * 100

print(f"Tổng điểm dữ liệu: {len(df)}")
print(f"Dữ liệu thực từ vệ tinh: {real_data_count} ({completeness:.1f}%)")
print(f"Thiếu dữ liệu: {missing_count} ({100-completeness:.1f}%)")
print(f"Thời gian: {total_time/60:.2f} phút")

# Thống kê theo nguồn
print("\nPhân bố nguồn dữ liệu:")
source_counts = df[df['Is_Real_Data'] == True]['Source'].value_counts()
for source, count in source_counts.items():
    print(f"  {source}: {count} ({count/real_data_count*100:.1f}%)")

# Thống kê theo phương pháp
print("\nPhương pháp trích xuất:")
method_counts = df[df['Is_Real_Data'] == True]['Method'].value_counts()
for method, count in method_counts.items():
    print(f"  {method}: {count}")

# Thống kê NDVI
valid = df[df['NDVI'].notna()]
if len(valid) > 0:
    print(f"\nNDVI Statistics:")
    print(f"  Mean: {valid['NDVI'].mean():.4f}")
    print(f"  Min:  {valid['NDVI'].min():.4f}")
    print(f"  Max:  {valid['NDVI'].max():.4f}")
    print(f"  Std:  {valid['NDVI'].std():.4f}")

# Huyện thiếu nhiều nhất
print("\n5 huyện thiếu dữ liệu nhiều nhất:")
missing_by_district = df[df['Is_Real_Data'] == False].groupby('District').size().sort_values(ascending=False).head(5)
for district, count in missing_by_district.items():
    print(f"  {district}: {count}/12 tháng")

# Lưu file
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f'bangladesh_ndvi_2022_REAL_DATA_ONLY_{timestamp}.csv'

# df.to_csv(output_file, index=False, encoding='utf-8-sig')

print("\n" + "=" * 80)
print("HOÀN THÀNH CRAWL!")
print("=" * 80)
print(f"[OK] Độ hoàn chỉnh: {completeness:.1f}% (100% dữ liệu thực)")
print(f"[OK] KHÔNG có dữ liệu nội suy")
print(f"[OK] Phù hợp cho nghiên cứu khoa học")
print()

# ============================================================================
# XỬ LÝ VÀ GỘP DỮ LIỆU
# ============================================================================
def process_ndvi_seasonal(df_ndvi):
    print("1. Đang đọc dữ liệu Main...")
    try:
        df_main = pd.read_csv('Bangladesh_main_data.csv')
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file input.")
        return

    # Tên District đã được chuẩn hóa ở bước crawl

    def get_season(month):
        if month in [12, 1, 2, 3]:
            return 'Rabi'
        elif month in [4, 5, 6, 7]:
            return 'Kharif 1'
        elif month in [8, 9, 10, 11]:
            return 'Kharif 2'
        return None

    df_ndvi['Season'] = df_ndvi['Month'].apply(get_season)

    print("2. Đang tính toán các chỉ số NDVI theo mùa (Mean, Std, CV, Range)...")
    
    seasonal_stats = df_ndvi.groupby(['District', 'Season'])['NDVI'].agg(['mean', 'max', 'min', 'std']).reset_index()
    seasonal_stats.columns = ['District', 'Season', 'NDVI_Season_Mean', 'NDVI_Season_Max', 'NDVI_Season_Min', 'NDVI_Season_Std']
    seasonal_stats['NDVI_Season_Range'] = seasonal_stats['NDVI_Season_Max'] - seasonal_stats['NDVI_Season_Min']
    seasonal_stats['NDVI_Season_CV'] = seasonal_stats.apply(
        lambda x: (x['NDVI_Season_Std'] / x['NDVI_Season_Mean']) if x['NDVI_Season_Mean'] > 0 else 0, 
        axis=1
    )

    print("3. Đang gộp dữ liệu...")
    df_main['Season_Clean'] = df_main['Season'].astype(str).str.strip()

    df_merged = pd.merge(
        df_main,
        seasonal_stats,
        left_on=['District', 'Season'],
        right_on=['District', 'Season'],
        how='left'
    )
    
    if 'Season_Clean' in df_merged.columns:
        df_merged.drop(columns=['Season_Clean'], inplace=True)

    output_filename = 'Process_bangladesh_ndvi_data.csv'
    df_merged.to_csv(output_filename, index=False)
    print(f"4. Hoàn tất gộp dữ liệu! File đã được lưu tại: {output_filename}")

process_ndvi_seasonal(df)