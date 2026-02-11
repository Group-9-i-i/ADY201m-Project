import ee
import pandas as pd
import time
from tqdm import tqdm
import os

# ---------------------------------------------------------
# 1. CẤU HÌNH (CONFIGURATION)
# ---------------------------------------------------------
PROJECT_ID = 'gen-lang-client-0272496285'
YEAR = 2022
COUNTRY = 'Bangladesh'
OUTPUT_FILE = 'Bangladesh_Soil_Moisture_2022_V2.csv' # Đổi tên file để không lẫn với file lỗi cũ

try:
    ee.Initialize(project=PROJECT_ID)
except:
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)

# ---------------------------------------------------------
# 2. HÀM XỬ LÝ (CORE FUNCTIONS)
# ---------------------------------------------------------

def get_bangladesh_districts():
    """Lấy ranh giới huyện (Level 2)"""
    return ee.FeatureCollection("FAO/GAUL/2015/level2") \
            .filter(ee.Filter.eq('ADM0_NAME', COUNTRY))

def get_monthly_data(month, roi):
    """
    Xử lý dữ liệu cho 1 tháng cụ thể với bộ dữ liệu MỚI.
    """
    start_date = ee.Date.fromYMD(YEAR, month, 1)
    end_date = start_date.advance(1, 'month')
    
    # --- THAY ĐỔI QUAN TRỌNG Ở ĐÂY ---
    # Sử dụng bộ dữ liệu mới: SPL4SMGP (Level 4 Soil Moisture)
    # Band 'sm_surface': Độ ẩm bề mặt
    # Band 'sm_rootzone': Độ ẩm vùng rễ
    dataset = ee.ImageCollection("NASA/SMAP/SPL4SMGP/007") \
                .filterDate(start_date, end_date) \
                .select(['sm_surface', 'sm_rootzone']) 
    
    # Tính trung bình tháng
    img_mean = dataset.mean()
    
    # Tính toán thống kê theo từng Huyện
    stats = img_mean.reduceRegions(
        collection=roi,
        reducer=ee.Reducer.mean(),
        scale=11000, # Bộ dữ liệu này có độ phân giải gốc là 9km-11km
        crs='EPSG:4326'
    )
    
    # Gán nhãn thời gian và lọc bỏ hình học
    # Lưu ý: Tên cột bây giờ sẽ là 'sm_surface' và 'sm_rootzone'
    return stats.map(lambda f: f.set({'month': month, 'year': YEAR})) \
                .select(['ADM2_NAME', 'ADM1_NAME', 'sm_surface', 'sm_rootzone', 'month', 'year'], retainGeometry=False)

def process_batch(months_batch):
    roi = get_bangladesh_districts()
    batch_features = []
    
    print(f"\n--- Đang tải dữ liệu batch tháng: {months_batch} (Dataset mới: SPL4SMGP/007) ---")
    
    for month in months_batch:
        fc_month = get_monthly_data(month, roi)
        
        # Tải dữ liệu về máy
        data_local = fc_month.getInfo() 
        
        if 'features' in data_local:
            # Kiểm tra xem có dữ liệu thực không
            if len(data_local['features']) > 0:
                for feat in data_local['features']:
                    props = feat['properties']
                    batch_features.append(props)
            else:
                 print(f"Cảnh báo: Tháng {month} trả về danh sách rỗng (có thể do lỗi server hoặc vùng chọn).")
        else:
            print(f"Cảnh báo: Không lấy được features tháng {month}")

    return pd.DataFrame(batch_features)

# ---------------------------------------------------------
# 3. CHƯƠNG TRÌNH CHÍNH
# ---------------------------------------------------------

if __name__ == "__main__":
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE) # Xóa file cũ để chạy lại cho sạch
        print("Đã xóa file cũ để chạy lại từ đầu với bộ dữ liệu mới.")

    batches = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [10, 11, 12]
    ]

    pbar = tqdm(batches, desc="Tiến độ tổng")
    
    for current_batch in pbar:
        try:
            df_batch = process_batch(current_batch)
            
            if not df_batch.empty:
                is_file_exists = os.path.isfile(OUTPUT_FILE)
                df_batch.to_csv(OUTPUT_FILE, mode='a', index=False, header=not is_file_exists)
                print(f"  -> Đã lưu xong {len(df_batch)} dòng vào {OUTPUT_FILE}")
            else:
                print(f"  -> Batch {current_batch} không có dữ liệu nào được tải về.")

        except Exception as e:
            print(f"\n[LỖI NGHIÊM TRỌNG] Batch {current_batch}: {e}")
            continue

        print("  -> Nghỉ 3 giây...")
        time.sleep(3) 
        
    print(f"\nHoàn tất! File kết quả: {OUTPUT_FILE}")