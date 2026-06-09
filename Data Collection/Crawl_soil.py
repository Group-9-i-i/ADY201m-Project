import requests
import pandas as pd
import numpy as np
from time import sleep
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SOIL_LAYERS = {
    "phh2o": "pH", "soc": "Organic_Carbon", "nitrogen": "Nitrogen",
    "clay": "Clay", "sand": "Sand", "silt": "Silt"
}
CONVERSION_FACTORS = {
    "phh2o": 10, "soc": 10, "nitrogen": 100, 
    "clay": 10, "sand": 10, "silt": 10
}
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
COORDS_FILE = "bangladesh_districts_coords_data.csv"
OUTPUT_FILE = "Bangladesh_soil_data_process.csv"

def get_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

session = get_session()

def fetch_exact_point(lat, lon):
    try:
        check_params = {"lat": lat, "lon": lon, "depth": "0-5cm", "property": ["phh2o"], "value": "mean"}
        r = session.get(BASE_URL, params=check_params, timeout=3)
        if r.status_code == 400: return None
        data = r.json()
        if not data.get("properties", {}).get("layers", [])[0]["depths"][0]["values"]["mean"]:
            return None 
    except Exception:
        return None

    point_record = {k: [] for k in SOIL_LAYERS}
    for depth in DEPTHS:
        params = {"lat": lat, "lon": lon, "depth": depth, "property": list(SOIL_LAYERS.keys()), "value": "mean"}
        try:
            r = session.get(BASE_URL, params=params, timeout=3)
            layers = r.json()["properties"]["layers"]
            for layer in layers:
                name = layer["name"]
                val = layer["depths"][0]["values"]["mean"]
                if val is not None:
                    point_record[name].append(val / CONVERSION_FACTORS.get(name, 1))
        except Exception:
            continue
            
    if not point_record["phh2o"]: return None
    return {k: sum(v_list) / len(v_list) if v_list else None for k, v_list in point_record.items()}

def fetch_smart_point(target_lat, target_lon):
    data = fetch_exact_point(target_lat, target_lon)
    if data: return data, False

    jitter_offsets = [
        (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01),
        (0.015, 0.015), (-0.015, -0.015),
        (0.02, 0), (-0.02, 0)
    ]
    
    for d_lat, d_lon in jitter_offsets:
        data = fetch_exact_point(target_lat + d_lat, target_lon + d_lon)
        if data: return data, True
            
    return None, False

def process_district(lat, lon, name):
    grid_points = [
        ("CENTER", 0, 0), ("NORTH", 0.1, 0), ("SOUTH", -0.1, 0),
        ("EAST", 0, 0.1), ("WEST", 0, -0.1)
    ]
    
    collected_samples = []
    
    for _, d_lat, d_lon in grid_points:
        data, _ = fetch_smart_point(lat + d_lat, lon + d_lon)
        if data:
            collected_samples.append(data)

    if not collected_samples:
        return None

    final_soil = {}
    for k in SOIL_LAYERS:
        values = [s[k] for s in collected_samples if s.get(k) is not None]
        final_soil[SOIL_LAYERS[k]] = round(sum(values) / len(values), 2) if values else None
            
    return final_soil

def crawl_data():
    try:
        districts = pd.read_csv(COORDS_FILE)
    except FileNotFoundError:
        return None

    records = []
    for _, row in districts.iterrows():
        name = row.get("District", row.get("district", "Unknown"))
        soil_data = process_district(row["lat"], row["lon"], name)

        if soil_data:
            soil_data.update({"District": name})
            records.append(soil_data)
        else:
            empty = {k: None for k in SOIL_LAYERS.values()}
            empty.update({"District": name})
            records.append(empty)

    return pd.DataFrame(records)

def clean_data(df):
    df['District'] = df['District'].astype(str).str.strip().str.title()
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().sum() > 0:
            df[col] = df[col].fillna(df[col].median())
    return df

def feature_engineering(df):
    df['CN_Ratio'] = (df['Organic_Carbon'] / (df['Nitrogen'] + 0.001)).round(2)

    def classify_texture(row):
        sand, clay = row['Sand'], row['Clay']
        if pd.isna(sand) or pd.isna(clay): return 'Unknown'
        if sand >= 50: return 'Sandy (Cát)'
        if clay >= 40: return 'Clayey (Sét)'
        return 'Loamy (Thịt/Phù sa)'

    df['Dominant_Soil_Texture'] = df.apply(classify_texture, axis=1)
    return df

def merge_and_save(df):
    if 'Sand' in df.columns:
        df = df.drop(columns=['Sand'])
        
    cols = df.columns.tolist()
    if 'District' in cols:
        cols.insert(0, cols.pop(cols.index('District')))
        df = df[cols]
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    print(f"Bắt đầu quy trình xử lý Soil...")
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")