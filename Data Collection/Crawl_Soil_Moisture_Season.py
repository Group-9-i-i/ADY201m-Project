import ee
import pandas as pd
import numpy as np
import time

PROJECT_ID = 'gen-lang-client-0272496285'
YEAR = 2022
COUNTRY = 'Bangladesh'
OUTPUT_FILE = 'Bangladesh_Soil_Moisture_data_process.csv'

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

def crawl_data():
    roi = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', COUNTRY))
    batches = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
    all_batches = []

    for batch in batches:
        batch_features = []
        for month in batch:
            start_date = ee.Date.fromYMD(YEAR, month, 1)
            end_date = start_date.advance(1, 'month')
            
            dataset = ee.ImageCollection("NASA/SMAP/SPL4SMGP/007").filterDate(start_date, end_date).select(['sm_surface', 'sm_rootzone'])
            img_mean = dataset.mean()
            stats = img_mean.reduceRegions(collection=roi, reducer=ee.Reducer.mean(), scale=11000, crs='EPSG:4326')
            fc_month = stats.map(lambda f: f.set({'month': month, 'year': YEAR})).select(
                ['ADM2_NAME', 'ADM1_NAME', 'sm_surface', 'sm_rootzone', 'month', 'year'], retainGeometry=False
            )
            
            data_local = fc_month.getInfo()
            if data_local and 'features' in data_local and len(data_local['features']) > 0:
                for feat in data_local['features']:
                    batch_features.append(feat['properties'])
        
        if batch_features:
            all_batches.append(pd.DataFrame(batch_features))
        time.sleep(3)

    if all_batches:
        return pd.concat(all_batches, ignore_index=True)
    return None

def clean_data(df):
    df = df.rename(columns={'ADM2_NAME': 'District'})
    df['District'] = df['District'].astype(str).str.strip().replace(DISTRICT_MAP)
    if 'ADM1_NAME' in df.columns:
        df = df.drop(columns=['ADM1_NAME'])
        
    df = df.sort_values(by=['District', 'year', 'month'])
    df['sm_rootzone'] = df.groupby('District')['sm_rootzone'].transform(lambda g: g.interpolate().bfill().ffill())
    df['sm_surface'] = df.groupby('District')['sm_surface'].transform(lambda g: g.interpolate().bfill().ffill())
    return df

def feature_engineering(df):
    df['Rootzone_Surface_Diff'] = (df['sm_rootzone'] - df['sm_surface']).round(4)
    df['Moisture_Ratio'] = (df['sm_rootzone'] / (df['sm_surface'] + 0.001)).round(4)
    
    conditions = [
        (df['sm_rootzone'] < 0.15),
        (df['sm_rootzone'] >= 0.15) & (df['sm_rootzone'] < 0.25),
        (df['sm_rootzone'] >= 0.25)
    ]
    choices = ['High Stress', 'Moderate', 'Optimal']
    df['Water_Availability_Cat'] = np.select(conditions, choices, default='Unknown')
    return df

def merge_and_save(df_features):
    cols = ['District', 'month', 'year', 'sm_surface', 'sm_rootzone', 'Rootzone_Surface_Diff', 'Moisture_Ratio', 'Water_Availability_Cat']
    final_cols = [c for c in cols if c in df_features.columns]
    df_features[final_cols].to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    print(f"Bắt đầu quy trình xử lý Soil Moisture...")
    init_gee()
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")