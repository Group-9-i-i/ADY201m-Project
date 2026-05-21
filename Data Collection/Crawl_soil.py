import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

def request_json(params, timeout=3):
    """Goi API va tra ve JSON, neu loi thi tra ve None."""
    try:
        resp = session.get(BASE_URL, params=params, timeout=timeout)
        if resp.status_code == 400:
            return None
        return resp.json()
    except Exception:
        return None

def fetch_exact_point(lat, lon):
    """Thử lấy dữ liệu tại đúng 1 tọa độ"""
    # 1. Ping nhanh lớp mặt 0-5cm để xem có đất không
    check_params = {
        "lat": lat,
        "lon": lon,
        "depth": "0-5cm",
        "property": ["phh2o"],
        "value": "mean",
    }
    data = request_json(check_params)
    if not data:
        return None
    layers = data.get("properties", {}).get("layers", [])
    if not layers:
        return None
    depths = layers[0].get("depths", [])
    if not depths:
        return None
    ph_mean = depths[0].get("values", {}).get("mean")
    # Neu gia tri pH la None -> nuoc hoac be tong
    if ph_mean is None:
        return None

    # 2. Nếu có đất, lấy full dữ liệu 3 độ sâu
    point_record = {}
    for k in SOIL_LAYERS:
        point_record[k] = []
    for depth in DEPTHS:
        params = {
            "lat": lat, "lon": lon, "depth": depth, 
            "property": list(SOIL_LAYERS.keys()), "value": "mean"
        }
        data = request_json(params)
        if not data:
            continue
        layers = data.get("properties", {}).get("layers", [])
        for layer in layers:
            name = layer.get("name")
            depths = layer.get("depths", [])
            if not depths:
                continue
            val = depths[0].get("values", {}).get("mean")
            if val is not None:
                factor = CONVERSION_FACTORS.get(name, 1)
                point_record[name].append(val / factor)
            
    # Tính trung bình 3 lớp đất
    final_values = {}
    if not point_record["phh2o"]:
        return None # Check lai lan cuoi
    
    for k, v_list in point_record.items():
        if v_list:
            final_values[k] = sum(v_list) / len(v_list)
        else:
            final_values[k] = None
        
    return final_values

def fetch_smart_point_with_rescue(target_lat, target_lon):
    """
    Thử điểm mục tiêu. Nếu thất bại, kích hoạt chế độ 'Cứu hộ' (Jitter)
    xung quanh 1-2km.
    """
    # 1. Thử điểm chính
    data = fetch_exact_point(target_lat, target_lon)
    if data:
        return data, False # False nghĩa là không cần cứu hộ

    #nếu ko có data thì dịch chuyển 1 đoạn ngắn
    jitter_offsets = [
        (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01), 
        (0.015, 0.015), (-0.015, -0.015),             
        (0.02, 0), (-0.02, 0)                         
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
    
    for _, d_lat, d_lon in grid_points:
        target_lat = lat + d_lat
        target_lon = lon + d_lon
        
        # Gọi hàm thông minh (có cứu hộ)
        data, rescued = fetch_smart_point_with_rescue(target_lat, target_lon)
        
        if data:
            collected_samples.append(data)
            if rescued:
                log_str += "R" # R = Diem goc loi, da tim duoc diem thay the gan do
            else:
                log_str += "O" # O = Diem goc OK
        else:
            log_str += "X" # X = Het cuu

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
    final_soil["grid_log"] = log_str # Luu log de kiem tra (VD: OROXO)
    
    print(f"   [{log_str}] ({len(collected_samples)}/5 điểm)", end=" ", flush=True)
    return final_soil

# ===== MAIN =====
def collect_soil_data(district_csv):
    districts = pd.read_csv(district_csv)
    records = []
    total = len(districts)
    
    print("Bắt đầu chế độ: Hybrid Search (Grid 11km + Jitter 1km)...")
    print("Chú thích: O=Gốc OK, R=Đã cứu hộ (lệch 1km), X=Bó tay")

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
            empty = {}
            for k in SOIL_LAYERS.values():
                empty[k] = None
            empty["District"] = name
            empty["valid_points"] = 0
            empty["grid_log"] = "XXXXX"
            records.append(empty)

    return pd.DataFrame(records)

if __name__ == "__main__":
    df = collect_soil_data("bangladesh_districts_coords_data.csv")
    df.to_csv("Bangladesh_soil_data.csv", index=False)
    print("\nHoàn tất! File: Bangladesh_soil_data.csv")