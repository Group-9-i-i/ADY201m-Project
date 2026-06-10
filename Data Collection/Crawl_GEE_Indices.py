import ee
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sys
import io
import requests
import os

CONFIG = {
    'YEAR': 2022,
    'PROJECT_ID': 'gen-lang-client-0272496285',
    'CLOUD_COVER_MAX': 90,
    'TIME_BUFFER_DAYS': 15,
    'SEASONAL_WINDOW_DAYS': 45,
    'SCALE': 500,
    'USE_LANDSAT': True,
    'USE_MODIS': True,
    'NUM_SPLIT_EC': 12
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DATA_FILE = os.path.join(SCRIPT_DIR, 'Bangladesh_main_data.csv')

OUTPUT_FILE_GEE = os.path.join(SCRIPT_DIR, 'Process_Bangladesh_GEE_Indices_Merge.csv')

DISTRICT_MAP = {
    'Barisal': 'Barishal', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
    "Cox's Bazar": 'CoxsBazar', 'Jessore': 'Jashore', 'Bogra': 'Bogura',
    'Jhalokati': 'Jhallokati', 'Brahamanbaria': 'Brahmanbaria',
    'Khagrachhari': 'Khagrachari', 'Maulvibazar': 'Moulvibazar',
    'Netrakona': 'Netrokona', 'Nawabganj': 'Chapai Nawabganj',
    'Panchagarh': 'Panchagar'
}

def init_gee():
    try:
        ee.Initialize(project=CONFIG['PROJECT_ID'])
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=CONFIG['PROJECT_ID'])

def mask_s2_clouds(image):
    # Lọc mây cho ảnh Sentinel-2 bằng dải QA60. Bit 10 là mây dày, Bit 11 là mây ti (cirrus).
    qa = image.select('QA60')
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(mask)

def calculate_ndvi_s2(image):
    # Tính NDVI cho Sentinel-2: (NIR - Red) / (NIR + Red) tương đương B8 và B4
    return image.addBands(image.normalizedDifference(['B8', 'B4']).rename('NDVI'))

def mask_l8_clouds(image):
    # Lọc mây cho Landsat 8/9 bằng QA_PIXEL. Bit 3 là mây, Bit 4 là bóng mây.
    qa = image.select('QA_PIXEL')
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return image.updateMask(mask)

def calculate_ndvi_l8(image):
    # Tính NDVI cho Landsat 8/9: B5 (NIR) và B4 (Red)
    return image.addBands(image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI'))

def calculate_ndvi_modis(image):
    # Chuẩn hóa giá trị NDVI của MODIS bằng cách nhân với hệ số scale 0.0001
    return image.addBands(image.select('NDVI').multiply(0.0001).rename('NDVI'))

def get_ndvi_aggressive(district_geom, year, month):
    # Xác định khoảng thời gian của tháng hiện tại
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"
    
    # Mở rộng khoảng thời gian ra hai đầu (TIME_BUFFER_DAYS) để tăng khả năng lấy được ảnh không có mây
    start_exp = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
    end_exp = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
    
    def process_collection(col, count, method, source, dr):
        if count > 0:
            # Lấy trung vị (median) của tất cả các ảnh trong khoảng thời gian để loại bỏ nhiễu, sau đó tính trung bình (mean) theo không gian địa lý
            stats = col.select('NDVI').median().reduceRegion(
                reducer=ee.Reducer.mean(), geometry=district_geom, scale=CONFIG['SCALE'], maxPixels=1e9
            )
            val = stats.get('NDVI').getInfo()
            if val is not None:
                return {'ndvi': val, 'method': method, 'source': source, 'image_count': count, 'date_range': dr}
        return None

    try:
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(district_geom).filterDate(start_date, end_date).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])).map(mask_s2_clouds).map(calculate_ndvi_s2)
        res = process_collection(s2, s2.size().getInfo(), 'S2-Standard', 'Sentinel-2', f"{start_date} to {end_date}")
        if res: return res
    except Exception: pass

    try:
        s2_exp = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(district_geom).filterDate(start_exp, end_exp).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])).map(mask_s2_clouds).map(calculate_ndvi_s2)
        res = process_collection(s2_exp, s2_exp.size().getInfo(), f'S2-Extended±{CONFIG["TIME_BUFFER_DAYS"]}d', 'Sentinel-2', f"{start_exp} to {end_exp}")
        if res: return res
    except Exception: pass

    if CONFIG['USE_LANDSAT']:
        try:
            l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(district_geom).filterDate(start_date, end_date).filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])).map(mask_l8_clouds).map(calculate_ndvi_l8)
            l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterBounds(district_geom).filterDate(start_date, end_date).filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])).map(mask_l8_clouds).map(calculate_ndvi_l8)
            ls = l8.merge(l9)
            res = process_collection(ls, ls.size().getInfo(), 'Landsat-Standard', 'Landsat 8/9', f"{start_date} to {end_date}")
            if res: return res
        except Exception: pass

        try:
            l8_e = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(district_geom).filterDate(start_exp, end_exp).filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])).map(mask_l8_clouds).map(calculate_ndvi_l8)
            l9_e = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterBounds(district_geom).filterDate(start_exp, end_exp).filter(ee.Filter.lt('CLOUD_COVER', CONFIG['CLOUD_COVER_MAX'])).map(mask_l8_clouds).map(calculate_ndvi_l8)
            ls_e = l8_e.merge(l9_e)
            res = process_collection(ls_e, ls_e.size().getInfo(), f'Landsat-Extended±{CONFIG["TIME_BUFFER_DAYS"]}d', 'Landsat 8/9', f"{start_exp} to {end_exp}")
            if res: return res
        except Exception: pass

    if CONFIG['USE_MODIS']:
        try:
            mod = ee.ImageCollection('MODIS/061/MOD13Q1').filterBounds(district_geom).filterDate(start_date, end_date).map(calculate_ndvi_modis)
            res = process_collection(mod, mod.size().getInfo(), 'MODIS-16day', 'MODIS Terra', f"{start_date} to {end_date}")
            if res: return res
        except Exception: pass

    # Nếu tất cả các bộ vệ tinh trên đều thất bại, tiến hành gộp chung dữ liệu từ cả 3 hệ thống vệ tinh vào một Collection
    try:
        s2_a = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(district_geom).filterDate(start_exp, end_exp).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CONFIG['CLOUD_COVER_MAX'])).map(mask_s2_clouds).map(calculate_ndvi_s2).select('NDVI')
        comb = s2_a
        if CONFIG['USE_LANDSAT']:
            comb = comb.merge(l8_e.select('NDVI')).merge(l9_e.select('NDVI'))
        if CONFIG['USE_MODIS']:
            mod_e = ee.ImageCollection('MODIS/061/MOD13Q1').filterBounds(district_geom).filterDate(start_exp, end_exp).map(calculate_ndvi_modis).select('NDVI')
            comb = comb.merge(mod_e)
        res = process_collection(comb, comb.size().getInfo(), f'Combined-All±{CONFIG["TIME_BUFFER_DAYS"]}d', 'S2+L8/9+MODIS', f"{start_exp} to {end_exp}")
        if res: return res
    except Exception: pass

    try:
        start_sea = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=CONFIG['SEASONAL_WINDOW_DAYS'])).strftime('%Y-%m-%d')
        end_sea = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=CONFIG['SEASONAL_WINDOW_DAYS'])).strftime('%Y-%m-%d')
        mod_sea = ee.ImageCollection('MODIS/061/MOD13Q1').filterBounds(district_geom).filterDate(start_sea, end_sea).map(calculate_ndvi_modis)
        res = process_collection(mod_sea, mod_sea.size().getInfo(), f'Seasonal±{CONFIG["SEASONAL_WINDOW_DAYS"]}d', 'MODIS-Seasonal', f"{start_sea} to {end_sea}")
        if res: return res
    except Exception: pass

    return {'ndvi': None, 'method': 'NO-DATA', 'source': 'None', 'image_count': 0, 'date_range': ''}

def crawl_ndvi():
    try:
        bangladesh = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
        district_list = bangladesh.aggregate_array('ADM2_NAME').getInfo()
    except Exception:
        return None

    results = []
    for district_name in district_list:
        try:
            district_geom = bangladesh.filter(ee.Filter.eq('ADM2_NAME', district_name)).geometry()
            for month in range(1, 13):
                res = get_ndvi_aggressive(district_geom, CONFIG['YEAR'], month)
                results.append({
                    'District': district_name, 'Year': CONFIG['YEAR'], 'Month': month,
                    'NDVI': res['ndvi'], 'Method': res['method'], 'Source': res['source'],
                    'Image_Count': res['image_count'], 'Is_Real_Data': res['ndvi'] is not None
                })
        except Exception:
            for month in range(1, 13):
                results.append({
                    'District': district_name, 'Year': CONFIG['YEAR'], 'Month': month,
                    'NDVI': None, 'Method': 'ERROR', 'Source': 'Error', 'Image_Count': 0, 'Is_Real_Data': False
                })

    return pd.DataFrame(results)

def clean_ndvi(df):
    df['District'] = df['District'].replace(DISTRICT_MAP)
    df = df.sort_values(['District', 'Month'])
    # Sử dụng backfill và forwardfill sau nội suy (interpolate) để xử lý các khoảng trống dữ liệu bị thiếu do mây
    df['NDVI'] = df.groupby('District')['NDVI'].transform(lambda g: g.interpolate().bfill().ffill())
    df['Is_Real_Data'] = df['NDVI'].notna()
    return df

def fe_ndvi(df):
    def get_season(m):
        if m in [12, 1, 2, 3]: return 'Rabi'
        if m in [4, 5, 6, 7]: return 'Kharif 1'
        if m in [8, 9, 10, 11]: return 'Kharif 2'
        return None
        
    df['Season'] = df['Month'].apply(get_season)
    stats = df.groupby(['District', 'Season'])['NDVI'].agg(['mean']).reset_index()
    stats.columns = ['District', 'Season', 'NDVI_Season_Mean']
    return stats



def crawl_multi_indices():
    bangladesh = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(['EVI'])
    col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H")
    col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(['LST_Day_1km'])
    col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(['ssm'])

    def process_month(month_offset):
        start_date = ee.Date(f"{CONFIG['YEAR']}-01-01").advance(month_offset, 'month')
        end_date = start_date.advance(1, 'month')

        def get_band(collection, band_name, scale, new_name, valid_max=None):
            # Lọc dữ liệu trong tháng và lấy giá trị trung bình pixel. Nếu ảnh trống, gán giá trị mặc định là -9999
            filtered = collection.select(band_name).filterDate(start_date, end_date)
            def compute():
                img = filtered.mean()
                if valid_max:
                    img = img.updateMask(img.lt(valid_max))
                return img.multiply(scale).rename(new_name)
            return ee.Image(ee.Algorithms.If(filtered.size().gt(0), compute(), ee.Image.constant(-9999).rename(new_name))).unmask(-9999)

        img_evi = get_band(col_evi, 'EVI', 0.0001, 'EVI')
        img_lai = get_band(col_lai_fpar, 'Lai_500m', 0.1, 'LAI')
        img_fpar = get_band(col_lai_fpar, 'Fpar_500m', 0.01, 'FPAR', valid_max=200)
        img_lst = get_band(col_lst, 'LST_Day_1km', 0.02, 'LST_Kelvin')
        img_sm = get_band(col_soil, 'ssm', 1.0, 'Soil_Moisture_mm')

        # Ghép tất cả các băng tần (bands) thành một image duy nhất để reduce hiệu quả hơn
        final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])
        reducer = ee.Reducer.mean().combine(reducer2=ee.Reducer.count(), sharedInputs=True)
        stats = final_image.reduceRegions(collection=bangladesh, reducer=reducer, scale=500)
        
        return stats.map(lambda f: f.set({'Month': start_date.get('month'), 'Year': start_date.get('year')}))

    # Tạo chuỗi từ 0 đến 11 tương ứng 12 tháng, dùng hàm map để xử lý đa luồng trên máy chủ GEE
    months = ee.List.sequence(0, 11)
    full_data = ee.FeatureCollection(months.map(process_month)).flatten()

    url = full_data.getDownloadURL(
        filetype='csv',
        selectors=['ADM2_NAME', 'Month', 'Year', 'EVI_mean', 'LAI_mean', 'FPAR_mean', 'LST_Kelvin_mean', 'Soil_Moisture_mm_mean']
    )
    
    response = requests.get(url)
    if response.status_code == 200:
        return pd.read_csv(io.StringIO(response.content.decode('utf-8')))
    return None

def clean_multi_indices(df):
    cols_to_fix = ['EVI_mean', 'LAI_mean', 'FPAR_mean', 'LST_Kelvin_mean', 'Soil_Moisture_mm_mean']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].replace(-9999, np.nan)
            
    df = df.sort_values(by=['ADM2_NAME', 'Year', 'Month'])

    def fill_missing(group):
        return group.interpolate(method='linear', limit_direction='both').bfill().ffill()

    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df.groupby('ADM2_NAME')[col].transform(fill_missing)
            df[col] = df[col].fillna(0)
    
    df['District'] = df['ADM2_NAME'].replace(DISTRICT_MAP)
    df.drop(columns=['ADM2_NAME'], inplace=True, errors='ignore')
    return df

def fe_multi_indices(df):
    def get_season(month):
        if month in [12, 1, 2, 3]: return 'Rabi'
        elif month in [4, 5, 6, 7]: return 'Kharif 1'
        elif month in [8, 9, 10, 11]: return 'Kharif 2'
        return 'Unknown'

    df['Season'] = df['Month'].apply(get_season)
    features = ['EVI_mean', 'LAI_mean', 'FPAR_mean', 'LST_Kelvin_mean', 'Soil_Moisture_mm_mean']
    existing_features = [f for f in features if f in df.columns]
    
    seasonal_df = df.groupby(['District', 'Year', 'Season'])[existing_features].mean().reset_index()
    seasonal_df.rename(columns={
        'EVI_mean': 'EVI', 'LAI_mean': 'LAI', 'FPAR_mean': 'FPAR', 
        'LST_Kelvin_mean': 'LST_Kelvin', 'Soil_Moisture_mm_mean': 'Soil_Moisture_mm'
    }, inplace=True)
    
    return seasonal_df



def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def mask_s2_clouds_ec(image):
    # Dải SCL phân loại mây của Sentinel-2. Loại bỏ các giá trị 3 (bóng mây), 8, 9, 10 (mây), 11 (tuyết)
    scl = image.select('SCL')
    mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return image.updateMask(mask)

def add_si(img):
    # Tính Salinity Index thông qua căn bậc 2 của tích dải B2 (Blue) và B4 (Red)
    si = img.expression(
        'sqrt(b("B2") * b("B4"))',
        {'B2': img.select('B2'), 'B4': img.select('B4')}
    ).rename('Salinity_Index_Raw')
    return img.addBands(si)

def crawl_ec():
    all_dataframes = []
    base_fc = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    district_names = base_fc.aggregate_array('ADM2_NAME').getInfo()
    
    # Chia danh sách District thành các chunk nhỏ nhằm tránh giới hạn Memory Limit Exceeded của GEE
    district_chunks = list(split_list(district_names, CONFIG['NUM_SPLIT_EC']))

    for month in range(1, 13):
        print(f"\n==============================================")
        print(f" 📅 ĐANG XỬ LÝ EC (Salinity) THÁNG {month}/{CONFIG['YEAR']}")
        print(f"==============================================")
        
        start_date = ee.Date.fromYMD(CONFIG['YEAR'], month, 1)
        end_date = start_date.advance(1, 'month')

        s2_base = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) \
            .map(mask_s2_clouds_ec) \
            .select(['B2', 'B4'])

        for i, chunk in enumerate(district_chunks):
            part_id = i + 1
            t_start = time.time()
            print(f"  ⏳ [Nhóm {part_id}/{CONFIG['NUM_SPLIT_EC']}] Đang gửi yêu cầu cho {len(chunk)} huyện... ", end="", flush=True)
            try:
                # simplify(maxError=100) làm mượt đường viền địa lý nhằm giảm độ phức tạp khi reduceRegions
                subset_fc = base_fc.filter(ee.Filter.inList('ADM2_NAME', chunk)).map(lambda f: f.simplify(maxError=100))
                s2_subset = s2_base.filterBounds(subset_fc)
                monthly_mean = s2_subset.map(add_si).select('Salinity_Index_Raw').mean()
                
                stats = monthly_mean.reduceRegions(collection=subset_fc, reducer=ee.Reducer.mean(), scale=100, tileScale=16)
                
                stats_final = stats.map(lambda f: f.set({
                    'Month': month, 'Year': CONFIG['YEAR'],
                    'Salinity_Index_Raw': ee.Algorithms.If(f.get('mean'), f.get('mean'), -9999)
                }))

                export_cols = ['ADM2_NAME', 'ADM1_NAME', 'Month', 'Year', 'Salinity_Index_Raw']
                data_json = stats_final.select(export_cols).getInfo()
                
                elapsed = time.time() - t_start
                if data_json and 'features' in data_json and len(data_json['features']) > 0:
                    df_part = pd.DataFrame([f['properties'] for f in data_json['features']])[export_cols]
                    all_dataframes.append(df_part)
                    print(f"✅ OK! (Mất {elapsed:.2f}s) - Lấy được {len(df_part)} dòng.")
                else:
                    print(f"⚠️ Rỗng (Mất {elapsed:.2f}s).")
            except Exception as e:
                print(f"\n❌ LỖI tại Nhóm {part_id}: {e}")
                print("   -> Đang nghỉ 5s rồi thử lại...")
                time.sleep(5)

    if all_dataframes:
        return pd.concat(all_dataframes, ignore_index=True)
    return None

def clean_ec(df):
    df['Salinity_Index_Raw'] = df['Salinity_Index_Raw'].replace(-9999, np.nan)
    df = df.sort_values(by=['ADM2_NAME', 'Year', 'Month'])
    df['Salinity_Index_Raw'] = df.groupby('ADM2_NAME')['Salinity_Index_Raw'].transform(
        lambda g: g.interpolate(method='linear', limit_direction='both').bfill().ffill()
    )
    df['Salinity_Index_Raw'] = df['Salinity_Index_Raw'].fillna(0)
    df['District'] = df['ADM2_NAME'].replace(DISTRICT_MAP)
    df.drop(columns=['ADM2_NAME'], inplace=True, errors='ignore')
    return df

def fe_ec(df):
    def get_season(month):
        if month in [11, 12, 1, 2, 3]: return 'Rabi'
        elif month in [4, 5, 6]: return 'Kharif 1'
        elif month in [7, 8, 9, 10]: return 'Kharif 2'
        return None

    df['Season'] = df['Month'].apply(get_season)
    salinity_agg = df.groupby(['District', 'Season'])['Salinity_Index_Raw'].mean().reset_index()
    salinity_agg.rename(columns={'Salinity_Index_Raw': 'Avg_Salinity_Index'}, inplace=True)
    return salinity_agg

def save_all_gee(df_ndvi, df_multi, df_ec):
    if not os.path.exists(MAIN_DATA_FILE):
        print(f"❌ LỖI: Không tìm thấy file gốc {MAIN_DATA_FILE}. Hủy bỏ quá trình lưu!")
        return
        
    df_main = pd.read_csv(MAIN_DATA_FILE)
    df_main['Season'] = df_main['Season'].astype(str).str.strip().str.title()
    
    if df_ndvi is not None:
        df_ndvi['Season'] = df_ndvi['Season'].astype(str).str.strip().str.title()
        df_main = pd.merge(df_main, df_ndvi, on=['District', 'Season'], how='left')
        
    if df_multi is not None:
        df_multi['Season'] = df_multi['Season'].astype(str).str.strip().str.title()
        df_main = pd.merge(df_main, df_multi, on=['District', 'Season'], how='left')
        
    if df_ec is not None:
        df_ec['Season'] = df_ec['Season'].astype(str).str.strip().str.title()
        df_main = pd.merge(df_main, df_ec, on=['District', 'Season'], how='left')
        
    df_main.to_csv(OUTPUT_FILE_GEE, index=False)

if __name__ == "__main__":
    print("Bat dau quy trinh thu thap du lieu Google Earth Engine tong hop...")
    init_gee()
    
    print("\n[1/3] Bat dau quy trinh xu ly NDVI...")
    df_raw_ndvi = crawl_ndvi()
    df_final_ndvi = None
    if df_raw_ndvi is not None and not df_raw_ndvi.empty:
        df_clean_ndvi = clean_ndvi(df_raw_ndvi)
        df_final_ndvi = fe_ndvi(df_clean_ndvi)
        print("Hoan tat NDVI.")
    else:
        print("Khong co du lieu NDVI.")

    print("\n[2/3] Bat dau quy trinh xu ly Multi-Indices (EVI/LAI/FPAR/LST)...")
    df_raw_multi = crawl_multi_indices()
    df_final_multi = None
    if df_raw_multi is not None and not df_raw_multi.empty:
        df_clean_multi = clean_multi_indices(df_raw_multi)
        df_final_multi = fe_multi_indices(df_clean_multi)
        print("Hoan tat Multi-Indices.")
    else:
        print("Khong co du lieu Multi-Indices.")

    print("\n[3/3] Bat dau quy trinh xu ly Salinity (EC)...")
    df_raw_ec = crawl_ec()
    df_final_ec = None
    if df_raw_ec is not None and not df_raw_ec.empty:
        df_clean_ec = clean_ec(df_raw_ec)
        df_final_ec = fe_ec(df_clean_ec)
        print("Hoan tat Salinity.")
    else:
        print("Khong co du lieu Salinity.")
        
    print("\nTien hanh gop tat ca va luu file...")
    save_all_gee(df_final_ndvi, df_final_multi, df_final_ec)
    print(f"Da luu ket qua tong hop tai {OUTPUT_FILE_GEE}")
        
    print("\nHOAN TAT QUA TRINH THU THAP TU GEE!")
