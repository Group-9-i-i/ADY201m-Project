import ee
import pandas as pd

# Khởi tạo kết nối
try:
    # Điền Project ID bạn đã tạo ở Bước 1 vào đây
    ee.Initialize(project='uiia') 
    print("Kết nối thành công!")
except Exception as e:
    print("Lỗi kết nối: ", e)

# Hàm lấy NDVI (Dùng dữ liệu vệ tinh MODIS)
def get_ndvi(lat, lon, year):
    point = ee.Geometry.Point([lon, lat])
    # Lọc vệ tinh tháng 6 đến tháng 11 (mùa vụ chính)
    collection = ee.ImageCollection("MODIS/061/MOD13Q1") \
        .filterBounds(point) \
        .filter(ee.Filter.calendarRange(year, year, 'year')) \
        .filter(ee.Filter.calendarRange(6, 11, 'month'))
    
    mean_ndvi = collection.select('NDVI').mean()
    result = mean_ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point,
        scale=250
    ).getInfo()
    
    return result['NDVI'] * 0.0001 if result and 'NDVI' in result else None

# Chạy thử cho Mangalore 2004
print(f"NDVI: {get_ndvi(12.8698, 74.8430, 2004)}")