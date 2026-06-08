import ee
import time
import pandas as pd
import numpy as np
import os

PROJECT_ID = 'gen-lang-client-0272496285'
NUM_SPLIT = 12
YEAR = 2022
MAIN_DATA_FILE = 'Bangladesh_main_data.csv'
OUTPUT_FILE = 'Process_Bangladesh_Salinity_data.csv'

DISTRICT_MAP = {
    'Barisal': 'Barishal', 'Bogra': 'Bogura', 'Brahamanbaria': 'Brahmanbaria',
    'Chittagong': 'Chattogram', 'Comilla': 'Cumilla', "Cox's Bazar": 'CoxsBazar',
    'Jessore': 'Jashore', 'Jhalokati': 'Jhallokati', 'Khagrachhari': 'Khagrachari',
    'Maulvibazar': 'Moulvibazar', 'Nawabganj': 'Chapai Nawabganj',
    'Netrakona': 'Netrokona', 'Panchagarh': 'Panchagar'
}

def init_gee():
    try:
        ee.Initialize(project=PROJECT_ID)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)

def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def crawl_data():
    all_dataframes = []
    base_fc = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    district_names = base_fc.aggregate_array('ADM2_NAME').getInfo()
    district_chunks = list(split_list(district_names, NUM_SPLIT))

    def mask_s2_clouds(image):
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return image.updateMask(mask)

    def add_si(img):
        si = img.expression(
            'sqrt(b("B2") * b("B4"))',
            {'B2': img.select('B2'), 'B4': img.select('B4')}
        ).rename('Salinity_Index_Raw')
        return img.addBands(si)

    for month in range(1, 13):
        start_date = ee.Date.fromYMD(YEAR, month, 1)
        end_date = start_date.advance(1, 'month')

        s2_base = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) \
            .map(mask_s2_clouds) \
            .select(['B2', 'B4'])

        for chunk in district_chunks:
            try:
                subset_fc = base_fc.filter(ee.Filter.inList('ADM2_NAME', chunk)).map(lambda f: f.simplify(maxError=100))
                s2_subset = s2_base.filterBounds(subset_fc)
                monthly_mean = s2_subset.map(add_si).select('Salinity_Index_Raw').mean()
                
                stats = monthly_mean.reduceRegions(collection=subset_fc, reducer=ee.Reducer.mean(), scale=100, tileScale=16)
                
                stats_final = stats.map(lambda f: f.set({
                    'Month': month, 'Year': YEAR,
                    'Salinity_Index_Raw': ee.Algorithms.If(f.get('mean'), f.get('mean'), -9999)
                }))

                export_cols = ['ADM2_NAME', 'ADM1_NAME', 'Month', 'Year', 'Salinity_Index_Raw']
                data_json = stats_final.select(export_cols).getInfo()
                
                if data_json and 'features' in data_json and len(data_json['features']) > 0:
                    df_part = pd.DataFrame([f['properties'] for f in data_json['features']])[export_cols]
                    all_dataframes.append(df_part)
            except Exception:
                time.sleep(5)

    if all_dataframes:
        return pd.concat(all_dataframes, ignore_index=True)
    return None

def clean_data(df):
    df['Salinity_Index_Raw'] = df['Salinity_Index_Raw'].replace(-9999, np.nan)
    df = df.sort_values(by=['ADM2_NAME', 'Year', 'Month'])
    df['Salinity_Index_Raw'] = df.groupby('ADM2_NAME')['Salinity_Index_Raw'].transform(
        lambda g: g.interpolate(method='linear', limit_direction='both').bfill().ffill()
    )
    df['Salinity_Index_Raw'] = df['Salinity_Index_Raw'].fillna(0)
    df['District'] = df['ADM2_NAME'].replace(DISTRICT_MAP)
    df.drop(columns=['ADM2_NAME'], inplace=True, errors='ignore')
    return df

def get_season(month):
    if month in [11, 12, 1, 2, 3]: return 'Rabi'
    elif month in [4, 5, 6]: return 'Kharif 1'
    elif month in [7, 8, 9, 10]: return 'Kharif 2'
    return None

def feature_engineering(df):
    df['Season'] = df['Month'].apply(get_season)
    salinity_agg = df.groupby(['District', 'Season'])['Salinity_Index_Raw'].mean().reset_index()
    salinity_agg.rename(columns={'Salinity_Index_Raw': 'Avg_Salinity_Index'}, inplace=True)
    return salinity_agg

def merge_and_save(df_features):
    if not os.path.exists(MAIN_DATA_FILE):
        return
        
    df_main = pd.read_csv(MAIN_DATA_FILE)
    df_merged = pd.merge(df_main, df_features, on=['District', 'Season'], how='left')
    df_merged.to_csv(OUTPUT_FILE, index=False)

if __name__ == "__main__":
    print(f"Bắt đầu quy trình xử lý EC (Salinity)...")
    init_gee()
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")