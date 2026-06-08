import ee
import pandas as pd
from datetime import datetime, timedelta
import time
import sys

CONFIG = {
    'YEAR': 2022,
    'PROJECT_ID': 'gen-lang-client-0272496285',
    'CLOUD_COVER_MAX': 90,
    'TIME_BUFFER_DAYS': 15,
    'SEASONAL_WINDOW_DAYS': 45,
    'SCALE': 500,
    'USE_LANDSAT': True,
    'USE_MODIS': True
}

MAIN_DATA_FILE = 'Bangladesh_main_data.csv'
OUTPUT_FILE = 'Process_bangladesh_ndvi_data.csv'

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
    qa = image.select('QA60')
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return image.updateMask(mask)

def calculate_ndvi_s2(image):
    return image.addBands(image.normalizedDifference(['B8', 'B4']).rename('NDVI'))

def mask_l8_clouds(image):
    qa = image.select('QA_PIXEL')
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return image.updateMask(mask)

def calculate_ndvi_l8(image):
    return image.addBands(image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI'))

def calculate_ndvi_modis(image):
    return image.addBands(image.select('NDVI').multiply(0.0001).rename('NDVI'))

def get_ndvi_aggressive(district_geom, year, month):
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year + 1}-01-01" if month == 12 else f"{year}-{month + 1:02d}-01"
    
    start_exp = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
    end_exp = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=CONFIG['TIME_BUFFER_DAYS'])).strftime('%Y-%m-%d')
    
    def process_collection(col, count, method, source, dr):
        if count > 0:
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

def crawl_data():
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

def clean_data(df):
    df['District'] = df['District'].replace(DISTRICT_MAP)
    df = df.sort_values(['District', 'Month'])
    df['NDVI'] = df.groupby('District')['NDVI'].transform(lambda g: g.interpolate().bfill().ffill())
    df['Is_Real_Data'] = df['NDVI'].notna()
    return df

def feature_engineering(df):
    def get_season(m):
        if m in [12, 1, 2, 3]: return 'Rabi'
        if m in [4, 5, 6, 7]: return 'Kharif 1'
        if m in [8, 9, 10, 11]: return 'Kharif 2'
        return None
        
    df['Season'] = df['Month'].apply(get_season)
    stats = df.groupby(['District', 'Season'])['NDVI'].agg(['mean', 'max', 'min', 'std']).reset_index()
    stats.columns = ['District', 'Season', 'NDVI_Season_Mean', 'NDVI_Season_Max', 'NDVI_Season_Min', 'NDVI_Season_Std']
    stats['NDVI_Season_Range'] = stats['NDVI_Season_Max'] - stats['NDVI_Season_Min']
    stats['NDVI_Season_CV'] = stats.apply(lambda x: (x['NDVI_Season_Std'] / x['NDVI_Season_Mean']) if x['NDVI_Season_Mean'] > 0 else 0, axis=1)
    return stats

def merge_and_save(df_features):
    try:
        df_main = pd.read_csv(MAIN_DATA_FILE)
        df_main['Season_Clean'] = df_main['Season'].astype(str).str.strip()
        df_merged = pd.merge(df_main, df_features, left_on=['District', 'Season_Clean'], right_on=['District', 'Season'], how='left')
        if 'Season_Clean' in df_merged.columns:
            df_merged.drop(columns=['Season_Clean'], inplace=True)
        df_merged.to_csv(OUTPUT_FILE, index=False)
    except FileNotFoundError:
        pass

if __name__ == "__main__":
    print("Bắt đầu quy trình xử lý NDVI...")
    init_gee()
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")