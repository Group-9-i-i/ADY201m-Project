import requests
import pandas as pd
import time
import json

# --- CẤU HÌNH QUAN TRỌNG ---
# 1. Header (Copy y nguyên từ tab Network của bạn vào đây)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
    # Quan trọng: Nếu web có check đăng nhập/phiên, bạn phải paste dòng Cookie vào dưới
    # "Cookie": "YOUR_COOKIE_HERE", 
    "Referer": "https://soilhealth.dac.gov.in/slusi-visualisation/",
}

# 2. Danh sách Mã huyện (District Code) của Karnataka
# Trong ảnh bạn gửi: Bagalkote có code là 524 (DISTRICT_L: "524")
# Bạn có thể tìm thêm các mã khác bằng cách đổi huyện trên web và soi request 'layers?'
district_codes = [524] # Thêm các mã khác vào đây: [524, 525, 526...]

# --- HÀM TẢI DỮ LIỆU WFS ---
def get_soil_data_wfs(dist_code):
    print(f"🔄 Đang tải dữ liệu huyện mã {dist_code}...")
    
    # URL CỦA GEOSERVER (Đã chuyển từ WMS sang WFS)
    # typeName=shc:soil_sample_points : Đây là tên lớp dữ liệu thấy trong ảnh của bạn
    # CQL_FILTER=DISTRICT_L={dist_code} : Lệnh lọc chỉ lấy dữ liệu của huyện đó
    
    url = "https://soilhealth4.dac.gov.in/geoserver/shc/ows"
    
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "shc:soil_sample_points",
        "outputFormat": "application/json",
        "CQL_FILTER": f"DISTRICT_L={dist_code}" # Lọc theo mã huyện
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            features = data.get('features', [])
            
            if not features:
                print(f"⚠️ Không có dữ liệu cho huyện {dist_code}")
                return []
            
            print(f"✅ Tìm thấy {len(features)} mẫu đất!")
            
            # Trích xuất dữ liệu từ 'properties' (giống trong ảnh image_9c2841.png)
            parsed_data = []
            for item in features:
                props = item.get('properties', {})
                # Lấy ID để biết năm (ví dụ: 29_524_shc_2015-17...)
                feature_id = item.get('id', '')
                
                # Cố gắng tách năm từ ID hoặc gán mặc định nếu cần
                # Trong ảnh ID có dạng: "29_524_shc_2015-17.333" -> Năm là 2015-17
                year_cycle = "Unknown"
                if "shc_" in feature_id:
                    try:
                        parts = feature_id.split("shc_")[1] # Lấy phần sau shc_
                        year_cycle = parts.split(".")[0]    # Lấy phần trước dấu chấm
                    except:
                        pass

                record = {
                    "District_Code": props.get("DISTRICT_L"),
                    "District_Name": props.get("DISTRICT"),
                    "Block": props.get("BLOCK"),
                    "Year_Cycle": year_cycle, # Năm lấy từ ID
                    "N (Nitrogen)": props.get("N"),
                    "P (Phosphorus)": props.get("P"),
                    "K (Potassium)": props.get("K"),
                    "pH": props.get("pH"),
                    "EC": props.get("EC"),
                    "OC (Organic Carbon)": props.get("OC"),
                    "S (Sulphur)": props.get("S"),
                    "Zn": props.get("Zn"),
                    "Fe": props.get("Fe"),
                    "Cu": props.get("Cu"),
                    "Mn": props.get("Mn"),
                    "Lat": props.get("Lat") if "Lat" in props else None, # GeoServer WFS thường trả geometry riêng
                    "Lon": props.get("Lon") if "Lon" in props else None
                }
                
                # Nếu properties không có Lat/Lon, lấy từ geometry
                if item.get('geometry') and item['geometry']['type'] == 'Point':
                    coords = item['geometry']['coordinates']
                    record["Lon"] = coords[0]
                    record["Lat"] = coords[1]
                    
                parsed_data.append(record)
                
            return parsed_data
        else:
            print(f"❌ Lỗi HTTP {response.status_code}: {response.text[:100]}")
            return []

    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        return []

# --- CHẠY CHƯƠNG TRÌNH ---
all_results = []
for code in district_codes:
    data = get_soil_data_wfs(code)
    all_results.extend(data)
    time.sleep(2) # Nghỉ nhẹ

if all_results:
    df = pd.DataFrame(all_results)
    filename = "Karnataka_Soil_Data_WFS.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\n🎉 HOÀN TẤT! Đã lưu {len(df)} dòng dữ liệu vào {filename}")
else:
    print("\n❌ Không lấy được dữ liệu nào. Hãy kiểm tra lại Header/Cookie.")