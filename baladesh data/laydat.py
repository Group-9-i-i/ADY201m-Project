import requests
import pandas as pd
from time import sleep
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import numpy as np

SOIL_LAYERS = {
    "phh2o": "pH",
    "soc": "Organic_Carbon",
    "nitrogen": "Nitrogen",
    "clay": "Clay",
    "sand": "Sand",
    "silt": "Silt",
    "bdod": "Bulk_Density"
}

# SoilGrids trả về số nguyên đã nhân lên (VD: pH 55 nghĩa là 5.5). 
# Cần chia lại để ra số thực tế.
CONVERSION_FACTORS = {
    "phh2o": 10,
    "soc": 10,
    "nitrogen": 100,
    "clay": 10,
    "sand": 10,
    "silt": 10,
    "bdod": 100
}

DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

def create_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1, # Giảm backoff để nhanh hơn chút
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

session = create_session()

def fetch_soilgrids_single_point(lat, lon, depth):
    """Hàm gọi API cho 1 điểm duy nhất"""
    params = {
        "lat": lat,
        "lon": lon,
        "depth": depth,
        "property": list(SOIL_LAYERS.keys()),
        "value": "mean"
    }
    
    try:
        r = session.get(BASE_URL, params=params, timeout=10)
        # Nếu gặp lỗi 400 (Bad Request) thường là do tọa độ ngoài vùng phủ
        if r.status_code == 400:
            return None
        r.raise_for_status()
        data = r.json()
        
        # Kiểm tra xem API có trả về layers không
        if "properties" not in data or "layers" not in data["properties"]:
            return None
            
        return data["properties"]["layers"]
    except Exception as e:
        # print(f"Error fetching {lat}, {lon}: {e}")
        return None

def parse_layers(layers):
    values = {}
    is_valid_data = False # Cờ kiểm tra xem có ít nhất 1 giá trị khác None không
    
    for layer in layers:
        name = layer["name"]
        try:
            val = layer["depths"][0]["values"]["mean"]
            if val is not None:
                # Áp dụng hệ số chuyển đổi ngay tại đây
                factor = CONVERSION_FACTORS.get(name, 1)
                values[name] = val / factor
                is_valid_data = True
            else:
                values[name] = None
        except Exception:
            values[name] = None
            
    return values, is_valid_data

def fetch_with_jitter(lat, lon, name):
    """
    Thử tọa độ gốc, nếu không có dữ liệu thì thử dịch chuyển xung quanh.
    Khoảng cách dịch chuyển ~0.01 độ (tương đương ~1.1km)
    """
    # Danh sách các độ lệch: (0,0) là gốc, sau đó là Đông, Tây, Nam, Bắc
    offsets = [
        (0, 0), 
        (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01),
        (0.015, 0.015), (-0.015, -0.015) # Thử xa hơn chút nếu cần
    ]
    
    for i, (d_lat, d_lon) in enumerate(offsets):
        test_lat = lat + d_lat
        test_lon = lon + d_lon
        
        # Dictionary chứa dữ liệu của 3 độ sâu cho điểm này
        point_data = {k: [] for k in SOIL_LAYERS}
        valid_depth_count = 0
        
        # Duyệt qua từng độ sâu
        for depth in DEPTHS:
            layers = fetch_soilgrids_single_point(test_lat, test_lon, depth)
            
            if layers:
                parsed_values, is_valid = parse_layers(layers)
                if is_valid:
                    for k, v in parsed_values.items():
                        if v is not None:
                            point_data[k].append(v)
                    valid_depth_count += 1
        
        # Nếu lấy được dữ liệu của đủ 3 độ sâu (hoặc ít nhất 1), coi như thành công
        if valid_depth_count > 0:
            if i > 0:
                print(f"   ⚠️ Đã tìm thấy dữ liệu thay thế tại offset {i} cho {name}")
            return point_data
            
    return None # Thất bại hoàn toàn sau khi thử hết các điểm

def collect_soil_data(district_csv):
    districts = pd.read_csv(district_csv)
    records = []
    
    total = len(districts)
    print(f"🚀 Bắt đầu thu thập dữ liệu cho {total} quận...")

    for idx, row in districts.iterrows():
        name = row["District"]
        lat = row["Latitude"]
        lon = row["Longitude"]

        print(f"[{idx+1}/{total}] 🌍 Đang xử lý: {name}...", end=" ", flush=True)
        
        # Dùng hàm fetch_with_jitter thay vì gọi trực tiếp
        depth_values = fetch_with_jitter(lat, lon, name)

        if depth_values is None:
            print(f"❌ THẤT BẠI (Vùng nước/Không dữ liệu)")
            continue

        # Tính trung bình các độ sâu
        soil = {"District": name, "Latitude": lat, "Longitude": lon}
        for k, values in depth_values.items():
            if values:
                soil[SOIL_LAYERS[k]] = round(sum(values) / len(values), 2)
            else:
                soil[SOIL_LAYERS[k]] = None
        
        records.append(soil)
        print("✅ OK")
        
        # Sleep nhẹ để tránh rate limit
        sleep(0.5)

    return pd.DataFrame(records)

# ===== MAIN =====
if __name__ == "__main__":
    # Đảm bảo tên file input đúng
    input_csv = "bangladesh_district_coords.csv" 
    
    try:
        df = collect_soil_data(input_csv)
        
        if not df.empty:
            output_file = "bangladesh_soil_features_final.csv"
            df.to_csv(output_file, index=False)
            print(f"\n🎉 Hoàn tất! Đã lấy được {len(df)}/{len(pd.read_csv(input_csv))} quận.")
            print(f"📁 Dữ liệu đã lưu vào: {output_file}")
        else:
            print("\n⚠️ Không lấy được dòng dữ liệu nào.")
            
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file {input_csv}. Hãy kiểm tra lại tên file.")