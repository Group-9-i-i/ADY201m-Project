import ee
import requests
import pandas as pd
import numpy as np
import io
import os

PROJECT_ID = 'gen-lang-client-0272496285'
YEAR = 2022
MAIN_DATA_FILE = 'Bangladesh_main_data.csv'
OUTPUT_FILE = 'Process_Bangladesh_EVI_LAI_FPAR_LST_data.csv'

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
        ee.Initialize(project=PROJECT_ID)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)

def crawl_data():
    bangladesh = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(['EVI'])
    col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H")
    col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(['LST_Day_1km'])
    col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(['ssm'])

    def process_month(month_offset):
        start_date = ee.Date(f'{YEAR}-01-01').advance(month_offset, 'month')
        end_date = start_date.advance(1, 'month')

        def get_band(collection, band_name, scale, new_name, valid_max=None):
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

        final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])
        reducer = ee.Reducer.mean().combine(reducer2=ee.Reducer.count(), sharedInputs=True)
        stats = final_image.reduceRegions(collection=bangladesh, reducer=reducer, scale=500)
        
        return stats.map(lambda f: f.set({'Month': start_date.get('month'), 'Year': start_date.get('year')}))

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

def clean_data(df):
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

def get_season(month):
    if month in [12, 1, 2, 3]: return 'Rabi'
    elif month in [4, 5, 6, 7]: return 'Kharif 1'
    elif month in [8, 9, 10, 11]: return 'Kharif 2'
    return 'Unknown'

def feature_engineering(df):
    df['Season'] = df['Month'].apply(get_season)
    features = ['EVI_mean', 'LAI_mean', 'FPAR_mean', 'LST_Kelvin_mean', 'Soil_Moisture_mm_mean']
    existing_features = [f for f in features if f in df.columns]
    
    seasonal_df = df.groupby(['District', 'Year', 'Season'])[existing_features].mean().reset_index()
    seasonal_df.rename(columns={
        'EVI_mean': 'EVI', 'LAI_mean': 'LAI', 'FPAR_mean': 'FPAR', 
        'LST_Kelvin_mean': 'LST_Kelvin', 'Soil_Moisture_mm_mean': 'Soil_Moisture_mm'
    }, inplace=True)
    
    return seasonal_df

def merge_and_save(df_features):
    if not os.path.exists(MAIN_DATA_FILE):
        return
        
    df_main = pd.read_csv(MAIN_DATA_FILE)
    df_main['Season'] = df_main['Season'].astype(str).str.strip().str.title()
    
    df_merged = pd.merge(df_main, df_features, on=['District', 'Season'], how='left')
    df_merged.to_csv(OUTPUT_FILE, index=False)

if __name__ == "__main__":
    print(f"Bắt đầu quy trình xử lý...")
    init_gee()
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")