import requests
import pandas as pd
import json
import time
import urllib.parse

# --- CẤU HÌNH NGƯỜI DÙNG (QUAN TRỌNG) ---

# 1. LINK WMS GỐC (Copy nguyên văn từ tab Network của bạn)
# Link này chứa Token (jW8X...), nó sẽ hết hạn sau 30 phút nên cần copy mới.
RAW_WMS_URL = "https://soilhealth.dac.gov.in/jW8X3zM5Y7pQvLr4K2Tn6HqPbD0tZmN9R6JfO1wCiG8xV5eTk2CdMoF9YsQr0Z7LmN1YxU4pTb2K5LvHqX7F3aCmGzR4Pw0D8UtYnJ9oZ2SvNlQ7Tz1PjR5LcX0Qf8HkV9OrG4V7YxU3pJk6TnMm5CdX8B9tRi1Lw2Qn7F4ZzJk8WvP1GrZ6Sx0JoH5C3oV7fNi2/shc/wms/wms?service=WMS&version=1.1.1&request=GetFeatureInfo&format=image%2Fpng&transparent=true&layers=29_524_shc_2015-17&query_layers=29_524_shc_2015-17&exceptions=application%2Fvnd.ogc.se_inimage&srs=EPSG:4326&width=101&X=50&Y=50&height=101&feature_count=50&info_format=application%2Fjson&bbox=75.37744666654068,16.502710826230246,75.39744666654069,16.52271082623025&HIDE_GEOMETRY=true"

# 2. Mã Bang và Mã Huyện (Để lấy tọa độ khung bản đồ)
STATE_CODE = "29"
DISTRICT_CODE = "524" # Bagalkote

# 3. Độ chia lưới (Càng lớn càng kỹ nhưng càng lâu)
GRID_SIZE = 8 # Chia thành 8x8 = 64 ô nhỏ. Nếu thiếu dữ liệu hãy tăng lên 10 hoặc 12.

# --- HÀM XỬ LÝ ---

def get_district_bbox():
    """Lấy tọa độ khung bao quanh (Bounding Box) của quận"""
    url = f"https://soilhealth.dac.gov.in/public/layers?state_code={STATE_CODE}&district_code={DISTRICT_CODE}"
    try:
        r = requests.get(url, verify=False)
        if r.status_code == 200:
            data = r.json()
            bbox = data.get("bbox", {})
            # Trả về: minx, miny, maxx, maxy
            return bbox.get("minx"), bbox.get("miny"), bbox.get("maxx"), bbox.get("maxy")
    except Exception as e:
        print(f"Lỗi lấy BBOX: {e}")
    return None, None, None, None

def scan_grid():
    # 1. Phân tích URL gốc để lấy phần cơ sở (Base URL + Token) và các tham số
    parsed = urllib.parse.urlparse(RAW_WMS_URL)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    params = dict(urllib.parse.parse_qsl(parsed.query))
    
    # 2. Lấy khung tọa độ của cả quận
    minx, miny, maxx, maxy = get_district_bbox()
    if not minx:
        print("❌ Không lấy được tọa độ quận. Kiểm tra lại mã quận/bang.")
        return

    print(f"🌍 Tọa độ quận: {minx}, {miny} -> {maxx}, {maxy}")
    
    # 3. Tính toán bước nhảy để chia lưới
    step_x = (maxx - minx) / GRID_SIZE
    step_y = (maxy - miny) / GRID_SIZE
    
    all_features = {} # Dùng dict để tự loại bỏ trùng lặp theo ID
    
    print(f"🚀 Bắt đầu quét lưới {GRID_SIZE}x{GRID_SIZE} ({GRID_SIZE*GRID_SIZE} requests)...")
    
    total_req = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://soilhealth.dac.gov.in/"
    }

    # 4. Vòng lặp quét từng ô
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            # Tính tọa độ ô nhỏ (Sub-bbox)
            curr_minx = minx + (i * step_x)
            curr_maxx = minx + ((i + 1) * step_x)
            curr_miny = miny + (j * step_y)
            curr_maxy = miny + ((j + 1) * step_y)
            
            bbox_str = f"{curr_minx},{curr_miny},{curr_maxx},{curr_maxy}"
            
            # Cập nhật params
            params['bbox'] = bbox_str
            params['width'] = '200'  # Giả lập màn hình nhỏ
            params['height'] = '200'
            params['X'] = '100'      # Click vào giữa
            params['Y'] = '100'
            params['feature_count'] = '100' # Cố gắng lấy tối đa 100 điểm mỗi ô
            
            try:
                # Gửi request WMS
                r = requests.get(base_url, params=params, headers=headers, verify=False, timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    features = data.get('features', [])
                    
                    for f in features:
                        f_id = f.get('id')
                        # Lưu vào dict với key là ID để lọc trùng
                        if f_id:
                            # Trích xuất properties và tọa độ
                            props = f.get('properties', {})
                            # Thử lấy tọa độ từ geometry nếu có (WMS đôi khi trả về null geometry nhưng có trong properties)
                            # Nếu WMS này trả về JSON chuẩn GeoJSON:
                            if f.get('geometry') and f['geometry']['type'] == 'Point':
                                props['Longitude'] = f['geometry']['coordinates'][0]
                                props['Latitude'] = f['geometry']['coordinates'][1]
                            
                            all_features[f_id] = props
                            
                    print(f"   Grid [{i},{j}]: Tìm thấy {len(features)} điểm. (Tổng tích lũy: {len(all_features)})")
                else:
                    print(f"   Grid [{i},{j}]: Lỗi {r.status_code}")
                    
            except Exception as e:
                print(f"   Grid [{i},{j}]: Lỗi kết nối - {e}")
            
            total_req += 1
            # time.sleep(0.5) # Nghỉ nhẹ nếu server chặn, nhưng web này có vẻ chịu tải tốt

    # 5. Xuất kết quả
    if all_features:
        final_data = list(all_features.values())
        df = pd.DataFrame(final_data)
        filename = f"Soil_Bagalkote_Scanned.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print("\n" + "="*50)
        print(f"🎉 HOÀN TẤT! Đã vét được {len(final_data)} điểm dữ liệu duy nhất.")
        print(f"📂 File lưu tại: {filename}")
        print("="*50)
    else:
        print("❌ Không tìm thấy dữ liệu nào. Kiểm tra lại Token URL.")

if __name__ == "__main__":
    scan_grid()