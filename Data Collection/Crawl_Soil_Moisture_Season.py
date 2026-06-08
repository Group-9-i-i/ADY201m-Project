import ee
import pandas as pd
import time
from tqdm import tqdm
import os
import numpy as np

# ---------------------------------------------------------
# 1. CẤU HÌNH (CONFIGURATION)
# ---------------------------------------------------------
PROJECT_ID = 'gen-lang-client-0272496285'
YEAR = 2022
COUNTRY = 'Bangladesh'

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

def process_soil_moisture_data(sm_df):
    print("1. Tính toán các chỉ số nông nghiệp (Feature Engineering)...")

    print("3. Tính toán các chỉ số nông nghiệp (Feature Engineering)...")
    sm_df['Rootzone_Surface_Diff'] = sm_df['sm_rootzone'] - sm_df['sm_surface']
    sm_df['Moisture_Ratio'] = sm_df['sm_rootzone'] / (sm_df['sm_surface'] + 0.001)
    
    conditions = [
        (sm_df['sm_rootzone'] < 0.15),
        (sm_df['sm_rootzone'] >= 0.15) & (sm_df['sm_rootzone'] < 0.25),
        (sm_df['sm_rootzone'] >= 0.25)
    ]
    choices = ['High Stress', 'Moderate', 'Optimal']
    sm_df['Water_Availability_Cat'] = np.select(conditions, choices, default='Unknown')

    sm_df['Rootzone_Surface_Diff'] = sm_df['Rootzone_Surface_Diff'].round(4)
    sm_df['Moisture_Ratio'] = sm_df['Moisture_Ratio'].round(4)

    output_filename = 'Bangladesh_Soil_Moisture_data_process.csv'
    cols = ['District', 'month', 'year', 'sm_surface', 'sm_rootzone', 'Rootzone_Surface_Diff', 'Moisture_Ratio', 'Water_Availability_Cat']
    final_cols = [c for c in cols if c in sm_df.columns] 
    sm_df = sm_df[final_cols]
    
    sm_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"\n✅ HOÀN TẤT! File '{output_filename}' đã được tạo thành công.")

if __name__ == "__main__":
    batches = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [10, 11, 12]
    ]

    pbar = tqdm(batches, desc="Tiến độ tổng")
    all_batches = []
    
    for current_batch in pbar:
        try:
            df_batch = process_batch(current_batch)
            
            if not df_batch.empty:
                all_batches.append(df_batch)
                print(f"  -> Đã tải xong {len(df_batch)} dòng cho batch {current_batch}")
            else:
                print(f"  -> Batch {current_batch} không có dữ liệu nào được tải về.")

        except Exception as e:
            print(f"\n[LỖI NGHIÊM TRỌNG] Batch {current_batch}: {e}")
            continue

        print("  -> Nghỉ 3 giây...")
        time.sleep(3) 
        
    print(f"\nHoàn tất quá trình tải!")
    
    if all_batches:
        final_sm_df = pd.concat(all_batches, ignore_index=True)
        
        # --- XỬ LÝ LỖI (DATA CLEANING) BÊN CRAWL ---
        print("Đang xử lý dữ liệu thiếu và chuẩn hóa tên huyện (bên crawl)...")
        final_sm_df = final_sm_df.rename(columns={'ADM2_NAME': 'District'})
        district_map = {
            'Barisal': 'Barishal', 'Bogra': 'Bogura', 'Brahamanbaria': 'Brahmanbaria',
            'Chittagong': 'Chattogram', 'Comilla': 'Cumilla', "Cox's Bazar": 'CoxsBazar',
            'Jessore': 'Jashore', 'Jhalokati': 'Jhallokati', 'Khagrachhari': 'Khagrachari',
            'Maulvibazar': 'Moulvibazar', 'Nawabganj': 'Chapai Nawabganj',
            'Netrakona': 'Netrokona', 'Panchagarh': 'Panchagar'
        }
        final_sm_df['District'] = final_sm_df['District'].astype(str).str.strip().replace(district_map)
        
        if 'ADM1_NAME' in final_sm_df.columns:
            final_sm_df = final_sm_df.drop(columns=['ADM1_NAME'])
            
        final_sm_df = final_sm_df.sort_values(by=['District', 'year', 'month'])
        final_sm_df['sm_rootzone'] = final_sm_df.groupby('District')['sm_rootzone'].transform(lambda g: g.interpolate().bfill().ffill())
        final_sm_df['sm_surface'] = final_sm_df.groupby('District')['sm_surface'].transform(lambda g: g.interpolate().bfill().ffill())
        
        process_soil_moisture_data(final_sm_df)
    else:
        print("Không có dữ liệu độ ẩm nào được thu thập!")