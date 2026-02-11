import ee
import pandas as pd
from calendar import monthrange
import time
import os

# Cấu hình dự án
PROJECT_ID = 'gen-lang-client-0272496285'
OUTPUT_FILE = 'bangladesh_ndvi_2022_tier1_fast.csv'

# Kết nối GEE
def init_gee():
    try:
        ee.Initialize(project=PROJECT_ID)
    except Exception as e:
        print(f" -> Lỗi kết nối GEE: {e}")

# --- CẤU HÌNH TẦNG 1 (SIÊU TỐC) ---
TIER1_SCALE = 2000       # Độ phân giải 2000m (2km) - Rất nhanh
TIER1_SIMPLIFY = 500     # Làm mượt biên giới 500m

def process_month_fast(month, year=2022):
    # 1. Tối ưu hình học (Simplify mạnh hơn)
    bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh')) \
        .map(lambda f: f.simplify(maxError=TIER1_SIMPLIFY)) 

    # 2. Hàm lọc mây & tính NDVI
    def get_ndvi_image(image):
        qa = image.select('QA60')
        # Mask mây cơ bản
        mask = qa.bitwiseAnd(1<<10).eq(0).And(qa.bitwiseAnd(1<<11).eq(0))
        # Mask thêm giá trị 0 (No data)
        return image.updateMask(mask).normalizedDifference(['B8', 'B4']).rename('NDVI') \
            .copyProperties(image, ['system:time_start'])

    _, last_day = monthrange(year, month)
    start_date = f'{year}-{month:02d}-01'
    end_date = f'{year}-{month:02d}-{last_day}'

    # Lấy ảnh
    collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(bangladesh_districts) \
        .filterDate(start_date, end_date) \
        .map(get_ndvi_image)

    # Dùng max() để lấy pixel tốt nhất trong tháng
    monthly_ndvi = collection.max().clip(bangladesh_districts)

    # 3. Reduce với cấu hình Tầng 1
    stats = monthly_ndvi.reduceRegions(
        collection=bangladesh_districts,
        reducer=ee.Reducer.mean(),
        scale=TIER1_SCALE,  # 2000m
        tileScale=16        # Chia rất nhỏ để không bị treo
    )
    
    return stats.select(['ADM2_NAME', 'mean'], retainGeometry=False)

# --- MAIN LOOP ---
init_gee()

# Nếu file chưa tồn tại, tạo mới
if not os.path.exists(OUTPUT_FILE):
    pd.DataFrame(columns=['District', 'Month', 'Year', 'NDVI_Mean']).to_csv(OUTPUT_FILE, index=False)

print(f"Bắt đầu chạy TẦNG 1 (Scale {TIER1_SCALE}m) - Ưu tiên tốc độ...")

# Chạy từng tháng một để an toàn nhất
for month in range(1, 13):
    print(f"\n--- Tháng {month}/2022 ---")
    try:
        # Lấy dữ liệu
        stats_obj = process_month_fast(month)
        
        # Tải về (Đây là bước quyết định)
        features = stats_obj.getInfo()['features']
        
        # Xử lý kết quả
        month_data = []
        missing_count = 0
        
        for ft in features:
            props = ft['properties']
            val = props.get('mean', None)
            
            if val is None:
                missing_count += 1
                
            month_data.append({
                'District': props.get('ADM2_NAME', 'Unknown'),
                'Month': month,
                'Year': 2022,
                'NDVI_Mean': val
            })
            
        # Lưu ngay lập tức (Append)
        df_month = pd.DataFrame(month_data)
        df_month.to_csv(OUTPUT_FILE, mode='a', header=False, index=False)
        
        print(f" -> Đã lưu xong. Số huyện có dữ liệu: {len(features) - missing_count}/{len(features)}")
        if missing_count > 0:
            print(f" -> Cảnh báo: Có {missing_count} huyện bị thiếu dữ liệu (do mây hoặc lỗi).")
            
    except Exception as e:
        print(f" -> LỖI NẶNG TẠI THÁNG {month}: {e}")
        # Nếu lỗi connection, thử ngủ 10s rồi init lại
        time.sleep(10)
        init_gee()

print(f"\nHOÀN TẤT! File kết quả: {OUTPUT_FILE}")