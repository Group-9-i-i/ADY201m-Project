import ee
import pandas as pd
from geopy.geocoders import Nominatim
import time

# 1. Khởi tạo
ee.Initialize(project='gen-lang-client-0272496285')
geolocator = Nominatim(user_agent="geo_debug_fix")

# 2. Đọc file
df = pd.read_csv("data_season.csv")
df.columns = df.columns.str.strip()

print("🚀 Bắt đầu Debug riêng cho Chikmangaluru...")

# 3. Hàm sửa lỗi tọa độ thủ công cho địa danh này
def fix_chik_coords():
    # Tên chuẩn để Geopy có thể tìm thấy
    target_name = "Chikkamagaluru, Karnataka, India"
    print(f"📡 Đang thử lấy tọa độ chuẩn cho: {target_name}")
    
    try:
        location = geolocator.geocode(target_name)
        if location:
            print(f"✅ Tìm thấy! Lat: {location.latitude}, Lon: {location.longitude}")
            return location.latitude, location.longitude
        else:
            print("❌ Vẫn không tìm thấy tọa độ. Đang dùng tọa độ cứng (Fallback)...")
            return 13.3153, 75.7754 # Tọa độ trung tâm Chikkamagaluru
    except Exception as e:
        print(f"⚠️ Lỗi kết nối Geopy: {e}")
        return 13.3153, 75.7754

# Lấy tọa độ một lần duy nhất để dùng cho tất cả dòng Chikmangaluru
fix_lat, fix_lon = fix_chik_coords()

# 4. Kiểm tra thử 1 dòng cụ thể của Chikmangaluru với GEE
def test_gee_for_chik(lat, lon):
    print(f"📡 Đang kiểm tra dữ liệu vệ tinh tại ({lat}, {lon}) cho năm 2004...")
    try:
        point = ee.Geometry.Point([lon, lat])
        # Thử lấy dữ liệu mùa Zaid năm 2004 như trong ảnh của bạn
        collection = (ee.ImageCollection("MODIS/061/MOD13Q1")
                      .filterBounds(point)
                      .filterDate('2004-03-01', '2004-06-30'))
        
        count = collection.size().getInfo()
        if count > 0:
            ndvi_val = collection.select("NDVI").mean().reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=250
            ).getInfo()
            print(f"✅ Kết quả NDVI thu được: {ndvi_val['NDVI'] * 0.0001}")
        else:
            print("❌ Lỗi: Năm 2004 tại vị trí này không có dữ liệu vệ tinh MODIS.")
    except Exception as e:
        print(f"🚨 Lỗi GEE: {e}")

# Chạy test
test_gee_for_chik(fix_lat, fix_lon)

print("\n💡 LỜI KHUYÊN: Bạn nên dùng Notepad++ hoặc VS Code nhấn 'Replace All' đổi 'Chikmangaluru' thành 'Chikkamagaluru' trong file CSV trước khi chạy code chính.")