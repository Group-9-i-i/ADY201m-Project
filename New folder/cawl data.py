import requests
import pandas as pd
import time
from datetime import datetime

# --- CẤU HÌNH ---
START_YEAR = 2004
END_YEAR = 2024 # NASA thường cập nhật chậm vài tháng, nên để 2024 là an toàn nhất để full dữ liệu.

# Danh sách tọa độ các quận tại Karnataka (NASA cần tọa độ, không dùng tên quận)
karnataka_districts = {
    "Bagalkot": {"lat": 16.1691, "lon": 75.6968},
    "Ballari": {"lat": 15.1394, "lon": 76.9214},
    "Belagavi": {"lat": 15.8497, "lon": 74.4977},
    "Bengaluru Urban": {"lat": 12.9716, "lon": 77.5946},
    "Bengaluru Rural": {"lat": 13.2175, "lon": 77.5600},
    "Bidar": {"lat": 17.9104, "lon": 77.5199},
    "Chamarajanagar": {"lat": 11.9261, "lon": 76.9437},
    "Chikkamagaluru": {"lat": 13.3153, "lon": 75.7754},
    "Chitradurga": {"lat": 14.2261, "lon": 76.4003},
    "Dakshina Kannada": {"lat": 12.9141, "lon": 74.8560},
    "Davangere": {"lat": 14.4644, "lon": 75.9218},
    "Dharwad": {"lat": 15.4589, "lon": 75.0078},
    "Gadag": {"lat": 15.4200, "lon": 75.6297},
    "Hassan": {"lat": 13.0033, "lon": 76.1004},
    "Haveri": {"lat": 14.7965, "lon": 75.3991},
    "Kalaburagi": {"lat": 17.3297, "lon": 76.8343},
    "Kodagu": {"lat": 12.3375, "lon": 75.8069},
    "Kolar": {"lat": 13.1382, "lon": 78.1291},
    "Koppal": {"lat": 15.3524, "lon": 76.1558},
    "Mandya": {"lat": 12.5222, "lon": 76.8967},
    "Mysuru": {"lat": 12.2958, "lon": 76.6394},
    "Raichur": {"lat": 16.2076, "lon": 77.3463},
    "Ramanagara": {"lat": 12.7209, "lon": 77.2799},
    "Shivamogga": {"lat": 13.9299, "lon": 75.5681},
    "Tumakuru": {"lat": 13.3396, "lon": 77.1010},
    "Udupi": {"lat": 13.3409, "lon": 74.7421},
    "Uttara Kannada": {"lat": 14.8058, "lon": 74.5518},
    "Vijayapura": {"lat": 16.8302, "lon": 75.7100},
    "Yadgir": {"lat": 16.7629, "lon": 77.1442}
}

# Các chỉ số nông nghiệp cần lấy:
# T2M: Nhiệt độ trung bình (C)
# RH2M: Độ ẩm tương đối (%)
# WS2M: Tốc độ gió (m/s)
# PRECTOTCOR: Lượng mưa (mm/tháng)
# ALLSKY_SFC_SW_DWN: Bức xạ mặt trời (kWh/m^2/day) - Cực quan trọng cho quang hợp
PARAMETERS = "T2M,RH2M,WS2M,PRECTOTCOR,ALLSKY_SFC_SW_DWN"

# Đường dẫn API NASA (Dạng trung bình tháng - Monthly Average)
# Nếu bạn muốn từng ngày (Daily), đổi 'monthly' thành 'daily' nhưng file sẽ rất nặng.
BASE_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

def get_climate_data(district, lat, lon):
    params = {
        "parameters": PARAMETERS,
        "community": "AG", # AG = Agroklimatology (Nông nghiệp)
        "longitude": lon,
        "latitude": lat,
        "start": START_YEAR,
        "end": END_YEAR,
        "format": "JSON"
    }
    
    print(f"--> Đang tải dữ liệu cho quận: {district}...")
    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if "properties" not in data:
            print(f"Lỗi API cho {district}")
            return []

        records = []
        param_data = data["properties"]["parameter"]
        
        # Duyệt qua các mốc thời gian (NASA trả về dạng key "YYYYMM")
        # Chúng ta lấy key từ nhiệt độ để làm chuẩn thời gian
        time_keys = sorted(param_data["T2M"].keys())
        
        for key in time_keys:
            # Bỏ qua các key năm tổng kết (thường kết thúc bằng 13, ví dụ 200413)
            if key.endswith("13"): 
                continue
                
            year = key[:4]
            month = key[4:]
            
            # Lọc chỉ số, nếu lỗi (-999) thì thay bằng None
            def get_val(param_name, key):
                val = param_data[param_name].get(key)
                return val if val != -999 else None

            records.append({
                "District": district,
                "Year": year,
                "Month": month,
                "Temperature_C": get_val("T2M", key),
                "Humidity_%": get_val("RH2M", key),
                "Wind_Speed_m_s": get_val("WS2M", key),
                "Rainfall_mm": get_val("PRECTOTCOR", key),
                "Solar_Radiation": get_val("ALLSKY_SFC_SW_DWN", key)
            })
        return records

    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return []

# --- CHẠY CHƯƠNG TRÌNH ---
full_data = []
print("Bắt đầu thu thập dữ liệu NASA POWER (2004 - 2024)...")

for district, coords in karnataka_districts.items():
    district_data = get_climate_data(district, coords["lat"], coords["lon"])
    full_data.extend(district_data)
    # Nghỉ xíu để tránh spam server NASA
    time.sleep(0.5)

# Lưu file
if full_data:
    df = pd.DataFrame(full_data)
    filename = "Karnataka_Crop_Weather_2004_2024.csv"
    df.to_csv(filename, index=False)
    print(f"\n✅ XONG! Đã lưu file: {filename}")
    print(f"Tổng số dòng dữ liệu: {len(df)}")
    print(df.head())
else:
    print("❌ Không lấy được dữ liệu nào.")