import ee
import time
import os
import requests
import rasterio
import numpy as np
import pandas as pd
from rasterio.io import MemoryFile

# ================= CẤU HÌNH =================
# Đường dẫn lưu file (Dùng dấu / hoặc \\)
OUTPUT_FOLDER = "C:/Bangladesh_NDVI_2022_Final" 

# Kích thước lưới (tăng lên 0.05 cho nhanh hơn, code mới đã xử lý được lỗi thiếu band)
GRID_SIZE_DEG = 0.05 
SCALE_M = 10 

# Giá trị đánh dấu dữ liệu hỏng (Flag value)
NODATA_VAL = -2.0 

# ================= KHỞI TẠO =================
try:
    ee.Initialize(project='gen-lang-client-0272496285')
except:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# ================= HÀM XỬ LÝ =================

def mask_s2_clouds(image):
    qa = image.select('QA60')
    mask = qa.bitwiseAnd(1<<10).eq(0).And(qa.bitwiseAnd(1<<11).eq(0))
    return image.updateMask(mask).divide(10000)

def generate_grid(roi_geometry, grid_size):
    bounds = roi_geometry.bounds().getInfo()['coordinates'][0]
    xs = [p[0] for p in bounds]
    ys = [p[1] for p in bounds]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    grid_polys = []
    x_curr = xmin
    while x_curr < xmax:
        y_curr = ymin
        while y_curr < ymax:
            x_next = min(x_curr + grid_size, xmax)
            y_next = min(y_curr + grid_size, ymax)
            rect = ee.Geometry.Rectangle([x_curr, y_curr, x_next, y_next])
            grid_polys.append(rect)
            y_curr += grid_size
        x_curr += grid_size
    return grid_polys

def process_tile_to_csv(tile_geom, district_name, tile_index, roi_full):
    try:
        intersection = tile_geom.intersection(roi_full, 10)
        
        monthly_images = []
        
        # --- BƯỚC 1: TẠO 12 BANDS (KỂ CẢ THIẾU DỮ LIỆU) ---
        for m in range(1, 13):
            band_name = f'NDVI_{m:02d}'
            s_date = f'2022-{m:02d}-01'
            e_date = f'2022-{m:02d}-28' if m == 2 else f'2022-{m:02d}-30'
            
            # Lấy ảnh và lọc mây
            col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(intersection) \
                .filterDate(s_date, e_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60)) \
                .map(mask_s2_clouds)
            
            # Tính NDVI
            ndvi_col = col.map(lambda img: img.normalizedDifference(['B8', 'B4']).rename(band_name))
            
            # Lấy trung vị (Median)
            img_median = ndvi_col.median()
            
            # *** KỸ THUẬT QUAN TRỌNG: UNMASK ***
            # Nếu pixel bị mây che hoặc không có ảnh, giá trị sẽ là Masked (Rỗng).
            # Ta dùng .unmask(-2) để ép nó thành giá trị -2.
            # Điều này đảm bảo ảnh tải về LUÔN CÓ DỮ LIỆU (dù là dữ liệu giả -2).
            img_final = img_median.unmask(NODATA_VAL).rename(band_name).float()
            
            monthly_images.append(img_final)

        # Gộp thành 1 ảnh 12 bands
        full_stack = ee.Image.cat(monthly_images).clip(intersection)
        
        # --- BƯỚC 2: TẢI VỀ ---
        url = full_stack.getDownloadURL({
            'scale': SCALE_M,
            'crs': 'EPSG:4326',
            'region': intersection,
            'format': 'GEO_TIFF'
        })
        
        response = requests.get(url)
        if response.status_code != 200:
            return False

        with MemoryFile(response.content) as memfile:
            with memfile.open() as dataset:
                data = dataset.read() # Shape: (12, H, W)
                
                # Tạo tọa độ
                height, width = data.shape[1], data.shape[2]
                cols, rows = np.meshgrid(np.arange(width), np.arange(height))
                xs, ys = rasterio.transform.xy(dataset.transform, rows, cols)
                
                lons = np.array(xs).flatten()
                lats = np.array(ys).flatten()
                
                data_dict = {'latitude': lats, 'longitude': lons}
                
                # Đưa dữ liệu vào Dictionary
                for i in range(12):
                    # Thay thế giá trị -2 (NODATA) bằng NaN của Numpy để dễ xử lý sau này
                    band_data = data[i].flatten()
                    # Lưu ý: So sánh float nên dùng np.isclose hoặc ngưỡng
                    band_data = np.where(band_data <= -1.5, np.nan, band_data)
                    data_dict[f'NDVI_{i+1:02d}'] = band_data
                
                df = pd.DataFrame(data_dict)
                
                # --- BƯỚC 3: XỬ LÝ SỐ LIỆU KHOA HỌC (PANDAS) ---
                
                # 3.1. Loại bỏ những điểm ảnh "chết" (NaN cả năm)
                # Ví dụ: Mặt nước, hoặc nơi mây che phủ 12/12 tháng
                ndvi_cols = [f'NDVI_{i+1:02d}' for i in range(12)]
                df = df.dropna(how='all', subset=ndvi_cols)
                
                if df.empty:
                    return False
                
                # 3.2. Nội suy tuyến tính (Linear Interpolation)
                # Đây là phương pháp khoa học: Điền giá trị thiếu dựa trên xu hướng
                # của tháng trước và tháng sau.
                # axis=1 nghĩa là nội suy theo hàng ngang (theo thời gian của từng điểm ảnh)
                df[ndvi_cols] = df[ndvi_cols].interpolate(method='linear', axis=1, limit_direction='both')
                
                # 3.3. Xử lý các tháng đầu/cuối vẫn còn NaN (Backward/Forward Fill)
                # Nếu tháng 1 bị thiếu, interpolate không tính được, ta dùng tháng 2 đắp sang.
                df[ndvi_cols] = df[ndvi_cols].bfill(axis=1).ffill(axis=1)

                # Làm tròn số liệu
                df['latitude'] = df['latitude'].round(6)
                df['longitude'] = df['longitude'].round(6)
                df[ndvi_cols] = df[ndvi_cols].round(4)

                # Lưu CSV
                csv_name = f"{district_name}_Tile{tile_index:03d}.csv"
                save_path = os.path.join(OUTPUT_FOLDER, csv_name)
                df.to_csv(save_path, index=False)
                
                return len(df)

    except Exception as e:
        print(f"   [Error Tile {tile_index}] {e}")
        return False

# ================= MAIN LOOP =================

bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

dist_list = bangladesh_districts.aggregate_array('ADM2_NAME').getInfo()
dist_list = sorted(list(set(dist_list)))

print(f"Tổng số huyện: {len(dist_list)}")

for dist_name in dist_list:
    safe_name = dist_name.replace(" ", "_").replace("'", "")
    print(f"\n>>> Đang xử lý: {dist_name}")
    
    roi_dist = bangladesh_districts.filter(ee.Filter.eq('ADM2_NAME', dist_name)).geometry()
    
    try:
        # Tăng Grid size lên 0.05 để giảm số lượng request (nhanh hơn)
        # Vì code mới đã xử lý được lỗi thiếu band nên có thể tải file to hơn chút
        tiles = generate_grid(roi_dist, GRID_SIZE_DEG) 
        print(f"    Số mảnh (Tiles): {len(tiles)}")
    except Exception as e:
        print(f"    Lỗi Grid: {e}")
        continue

    for i, tile in enumerate(tiles):
        print(f"    -> Tile {i+1}/{len(tiles)}...", end=" ")
        
        start = time.time()
        res = process_tile_to_csv(tile, safe_name, i, roi_dist)
        end = time.time()
        
        if res:
            print(f"OK ({res} dòng) - {end-start:.1f}s")
        else:
            print("Trống.")
        
        time.sleep(1) # Nghỉ nhẹ

print("\nHOÀN TẤT.")