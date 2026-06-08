import requests
import pandas as pd
from time import sleep
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import math
import numpy as np

# ===== CẤU HÌNH =====
SOIL_LAYERS = {
    "phh2o": "pH", "soc": "Organic_Carbon", "nitrogen": "Nitrogen",
    "clay": "Clay", "sand": "Sand", "silt": "Silt", "bdod": "Bulk_Density"
}

CONVERSION_FACTORS = {
    "phh2o": 10, "soc": 10, "nitrogen": 100, 
    "clay": 10, "sand": 10, "silt": 10, "bdod": 100
}

DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# ===== KẾT NỐI =====
def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

session = create_session()

# ===== HÀM CỐT LÕI (MICRO-LEVEL) =====
def fetch_exact_point(lat, lon):
    """Thử lấy dữ liệu tại đúng 1 tọa độ"""
    # 1. Ping nhanh lớp mặt 0-5cm để xem có đất không
    try:
        check_params = {"lat": lat, "lon": lon, "depth": "0-5cm", "property": ["phh2o"], "value": "mean"}
        r = session.get(BASE_URL, params=check_params, timeout=3)
        if r.status_code == 400: return None
        data = r.json()
        # Nếu giá trị pH là None -> Đây là nước hoặc bê tông
        if not data.get("properties", {}).get("layers", [])[0]["depths"][0]["values"]["mean"]:
            return None 
    except:
        return None

    # 2. Nếu có đất, lấy full dữ liệu 3 độ sâu
    point_record = {k: [] for k in SOIL_LAYERS}
    for depth in DEPTHS:
        params = {
            "lat": lat, "lon": lon, "depth": depth, 
            "property": list(SOIL_LAYERS.keys()), "value": "mean"
        }
        try:
            r = session.get(BASE_URL, params=params, timeout=3)
            layers = r.json()["properties"]["layers"]
            for layer in layers:
                name = layer["name"]
                val = layer["depths"][0]["values"]["mean"]
                if val is not None:
                    factor = CONVERSION_FACTORS.get(name, 1)
                    point_record[name].append(val / factor)
        except:
            continue
            
    # Tính trung bình 3 lớp đất
    final_values = {}
    if not point_record["phh2o"]: return None # Check lại lần cuối
    
    for k, v_list in point_record.items():
        final_values[k] = sum(v_list) / len(v_list) if v_list else None
        
    return final_values

def fetch_smart_point_with_rescue(target_lat, target_lon, point_name):
    """
    Thử điểm mục tiêu. Nếu thất bại, kích hoạt chế độ 'Cứu hộ' (Jitter)
    xung quanh 1-2km.
    """
    # 1. Thử điểm chính
    data = fetch_exact_point(target_lat, target_lon)
    if data:
        return data, False # False nghĩa là không cần cứu hộ

    # 2. Kích hoạt cứu hộ (Micro-Jitter)
    # Các độ lệch nhỏ: ~1km (0.01 độ) và ~2km (0.02 độ)
    jitter_offsets = [
        (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01), # Cách 1km 4 hướng
        (0.015, 0.015), (-0.015, -0.015),             # Cách 2km chéo
        (0.02, 0), (-0.02, 0)                         # Cách 2km ngang
    ]
    
    for d_lat, d_lon in jitter_offsets:
        rescue_lat = target_lat + d_lat
        rescue_lon = target_lon + d_lon
        data = fetch_exact_point(rescue_lat, rescue_lon)
        if data:
            return data, True # True nghĩa là đã được cứu hộ thành công
            
    return None, False # Thất bại hoàn toàn

# ===== HÀM TỔNG HỢP (MACRO-LEVEL) =====
def process_district(lat, lon, name):
    """
    Chiến thuật:
    1. Tạo 5 điểm lớn (Tâm, Bắc, Nam, Đông, Tây - cách 11km).
    2. Với mỗi điểm, nếu lỗi -> tự động tìm quanh đó 1-2km.
    """
    # Macro Grid: Các điểm vệ tinh cách tâm ~11km (0.1 độ)
    grid_points = [
        ("CENTER", 0, 0),
        ("NORTH ", 0.1, 0),
        ("SOUTH ", -0.1, 0),
        ("EAST  ", 0, 0.1),
        ("WEST  ", 0, -0.1)
    ]
    
    collected_samples = []
    log_str = ""
    
    for pt_name, d_lat, d_lon in grid_points:
        target_lat = lat + d_lat
        target_lon = lon + d_lon
        
        # Gọi hàm thông minh (có cứu hộ)
        data, rescued = fetch_smart_point_with_rescue(target_lat, target_lon, pt_name)
        
        if data:
            collected_samples.append(data)
            if rescued:
                log_str += "W" # Dấu này nghĩa là điểm gốc lỗi, nhưng đã tìm được điểm thay thế gần đó
            else:
                log_str += "OK" # Dấu này nghĩa là điểm gốc ngon lành
        else:
            log_str += "X" # Hết cứu

    # Tổng hợp dữ liệu
    if not collected_samples:
        print(f"   [{log_str}] -> Thất bại")
        return None

    final_soil = {}
    for k in SOIL_LAYERS:
        values = [s[k] for s in collected_samples if s.get(k) is not None]
        if values:
            final_soil[SOIL_LAYERS[k]] = round(sum(values) / len(values), 2)
        else:
            final_soil[SOIL_LAYERS[k]] = None
            
    final_soil["valid_points"] = len(collected_samples)
    final_soil["grid_log"] = log_str # Lưu lại log để bạn kiểm tra (VD: OK W OK X OK)
    
    print(f"   [{log_str}] ({len(collected_samples)}/5 điểm)", end=" ", flush=True)
    return final_soil

# ===== MAIN =====
def collect_soil_data(district_csv):
    districts = pd.read_csv(district_csv)
    records = []
    total = len(districts)
    
    print(f"Bắt đầu chế độ: Hybrid Search (Grid 11km + Jitter 1km)...")
    print(f"Chú thích: OK=Gốc OK, W=Đã cứu hộ (lệch 1km), X=Bó tay")

    for idx, row in districts.iterrows():
        name = row.get("District", row.get("district", "Unknown"))
        lat = row["lat"]
        lon = row["lon"]

        print(f"\n[{idx+1}/{total}] {name:<15}", end="", flush=True)
        
        soil_data = process_district(lat, lon, name)

        if soil_data:
            soil_data["District"] = name
            soil_data["Latitude"] = lat
            soil_data["Longitude"] = lon
            records.append(soil_data)
        else:
            # Vẫn tạo dòng trống
            empty = {k: None for k in SOIL_LAYERS.values()}
            empty["District"] = name
            empty["valid_points"] = 0
            empty["grid_log"] = "XXXXX"
            records.append(empty)

    return pd.DataFrame(records)

def process_soil_data(soil_df):
    print("1. Tính toán các chỉ số nông nghiệp từ dữ liệu đất...")
    
    print("3. Tính toán các chỉ số nông nghiệp từ dữ liệu đất...")
    soil_df['CN_Ratio'] = soil_df['Organic_Carbon'] / (soil_df['Nitrogen'] + 0.001)
    
    conditions_ph = [
        (soil_df['pH'] < 5.5),
        (soil_df['pH'] >= 5.5) & (soil_df['pH'] <= 7.0),
        (soil_df['pH'] > 7.0)
    ]
    choices_ph = ['Acidic (Chua)', 'Optimal (Tối ưu)', 'Alkaline (Kiềm)']
    soil_df['pH_Suitability'] = np.select(conditions_ph, choices_ph, default='Unknown')

    conditions_bd = [
        (soil_df['Bulk_Density'] < 1.4),
        (soil_df['Bulk_Density'] >= 1.4) & (soil_df['Bulk_Density'] <= 1.6),
        (soil_df['Bulk_Density'] > 1.6)
    ]
    choices_bd = ['Low', 'Moderate', 'High']
    soil_df['Compaction_Risk'] = np.select(conditions_bd, choices_bd, default='Unknown')

    def classify_texture(row):
        sand = row['Sand']
        clay = row['Clay']
        if pd.isna(sand) or pd.isna(clay):
            return 'Unknown'
        if sand >= 50:
            return 'Sandy (Cát)'
        elif clay >= 40:
            return 'Clayey (Sét)'
        else:
            return 'Loamy (Thịt/Phù sa)'

    soil_df['Dominant_Soil_Texture'] = soil_df.apply(classify_texture, axis=1)

    soil_df['CN_Ratio'] = soil_df['CN_Ratio'].round(2)

    output_filename = 'Bangladesh_soil_data_process.csv'
    
    cols = soil_df.columns.tolist()
    if 'District' in cols:
        cols.insert(0, cols.pop(cols.index('District')))
        soil_df = soil_df[cols]
    
    soil_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"\nHOÀN TẤT! File '{output_filename}' đã được tạo thành công.")

if __name__ == "__main__":
    df = collect_soil_data("bangladesh_districts_coords_data.csv")
    print("\nHoàn tất quá trình lấy dữ liệu!")
    
    # --- XỬ LÝ LỖI (DATA CLEANING) BÊN CRAWL ---
    print("Đang xử lý dữ liệu lỗi (bên crawl)...")
    df['District'] = df['District'].astype(str).str.strip().str.title()
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().sum() > 0:
            df[col] = df[col].fillna(df[col].median())
            
    process_soil_data(df)