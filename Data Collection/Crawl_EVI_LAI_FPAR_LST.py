import ee
import requests
import pandas as pd
import numpy as np
import io

# ===============================
# 1. INITIALIZE
# ===============================
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("[OK] Connected to GEE.")
except:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

# ===============================
# 2. LOAD DATA
# ===============================
print("Setting up datasets...")

bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(['EVI'])
col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H")
col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(['LST_Day_1km'])
col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(['ssm'])


# ===============================
# 3. PROCESS FUNCTION
# ===============================
def process_safe_month(month_offset):

    start_date = ee.Date('2022-01-01').advance(month_offset, 'month')
    end_date = start_date.advance(1, 'month')

    # ---- Generic safe band loader ----
    def get_safe_band(collection, band_name, scale, new_name, valid_max=None):

        filtered = collection.select(band_name).filterDate(start_date, end_date)

        def compute():
            img = filtered.mean()

            # Mask invalid values if needed
            if valid_max:
                img = img.updateMask(img.lt(valid_max))

            img = img.multiply(scale).rename(new_name)
            return img

        img = ee.Image(
            ee.Algorithms.If(
                filtered.size().gt(0),
                compute(),
                ee.Image.constant(-9999).rename(new_name)
            )
        )

        return img.unmask(-9999)


    # ---- Apply bands ----
    img_evi = get_safe_band(col_evi, 'EVI', 0.0001, 'EVI')
    img_lai = get_safe_band(col_lai_fpar, 'Lai_500m', 0.1, 'LAI')
    
    # FIX QUAN TRỌNG Ở ĐÂY
    img_fpar = get_safe_band(
        col_lai_fpar,
        'Fpar_500m',
        0.01,           # đúng scale
        'FPAR',
        valid_max=200   # bỏ pixel lỗi (>=249)
    )

    img_lst = get_safe_band(col_lst, 'LST_Day_1km', 0.02, 'LST_Kelvin')
    img_sm = get_safe_band(col_soil, 'ssm', 1.0, 'Soil_Moisture_mm')

    final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])

    # ---- Reducer: mean + pixel count ----
    reducer = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.count(),
        sharedInputs=True
    )

    stats = final_image.reduceRegions(
        collection=bangladesh_districts,
        reducer=reducer,
        scale=500
    )

    return stats.map(lambda f: f.set({
        'Month': start_date.get('month'),
        'Year': start_date.get('year')
    }))


# ===============================
# 4. RUN PROCESS
# ===============================
print("Processing monthly data...")

months = ee.List.sequence(0, 11)
nested = ee.FeatureCollection(months.map(process_safe_month))
full_data = nested.flatten()

print("Generating download link...")

download_url = full_data.getDownloadURL(
    filetype='csv',
    selectors=[
        'ADM2_NAME',
        'ADM2_CODE',
        'Month',
        'Year',
        'EVI_mean',
        'LAI_mean',
        'FPAR_mean',
        'LST_Kelvin_mean',
        'Soil_Moisture_mm_mean',
        'FPAR_count'   # thêm count để debug
    ]
)

response = requests.get(download_url)

if response.status_code == 200:
    print("[SUCCESS] Data downloaded successfully.")
    df_evi = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
    
    # ==============================================================================
    # --- BƯỚC XỬ LÝ LỖI (DATA CLEANING) TẠI BƯỚC CRAWL ---
    # ==============================================================================
    print("Đang xử lý và tự động điền dữ liệu thiếu (bên crawl)...")
    cols_to_fix = ['EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm']
    for col in cols_to_fix:
        if col in df_evi.columns:
            df_evi[col] = df_evi[col].replace(-9999, np.nan)
            
    df_evi = df_evi.sort_values(by=['ADM2_NAME', 'Year', 'Month'])

    def fill_missing_values(group):
        group = group.interpolate(method='linear', limit_direction='both')
        group = group.bfill().ffill()
        return group

    for col in cols_to_fix:
        if col in df_evi.columns:
            df_evi[col] = df_evi.groupby('ADM2_NAME')[col].transform(fill_missing_values)
            if df_evi[col].isna().sum() > 0:
                 df_evi[col] = df_evi[col].fillna(0)
    
    district_corrections = {
        'Barisal': 'Barishal', 'Chittagong': 'Chattogram', 'Comilla': 'Cumilla',
        "Cox's Bazar": 'CoxsBazar', 'Jessore': 'Jashore', 'Bogra': 'Bogura',
        'Jhalokati': 'Jhallokati', 'Brahamanbaria': 'Brahmanbaria',
        'Khagrachhari': 'Khagrachari', 'Maulvibazar': 'Moulvibazar',
        'Netrakona': 'Netrokona', 'Nawabganj': 'Chapai Nawabganj',
        'Panchagarh': 'Panchagar'
    }
    df_evi['ADM2_NAME'] = df_evi['ADM2_NAME'].replace(district_corrections)
    df_evi.rename(columns={'ADM2_NAME': 'District'}, inplace=True)
    print("-> Đã xử lý lỗi dữ liệu (Interpolation & District Names).")
    
else:
    print("Download failed:", response.status_code)
    df_evi = None

# ===============================
# 5. PROCESS AND MERGE
# ===============================
def process_and_merge_data(df_evi):
    if df_evi is None:
        print("Không có dữ liệu EVI để xử lý.")
        return
    # --- 1. Đọc dữ liệu ---
    print("Đang đọc file Main...")
    try:
        # File dữ liệu chính (Main data)
        df_main = pd.read_csv('Bangladesh_main_data.csv')
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file. {e}")
        return

    # Các bước xử lý lỗi và chuẩn hóa đã được dời lên trên phần Crawl

    # --- 3. Định nghĩa mùa dựa trên tháng ---
    # Quy ước:
    # - Rabi: Tháng 12, 1, 2, 3 (Mùa đông/xuân)
    # - Kharif 1: Tháng 4, 5, 6, 7 (Đầu mùa mưa)
    # - Kharif 2: Tháng 8, 9, 10, 11 (Cuối mùa mưa/thu)
    
    def get_season(month):
        if month in [12, 1, 2, 3]:
            return 'Rabi'
        elif month in [4, 5, 6, 7]:
            return 'Kharif 1'
        elif month in [8, 9, 10, 11]:
            return 'Kharif 2'
        return 'Unknown'

    df_evi['Season'] = df_evi['Month'].apply(get_season)

    # --- 4. Gom nhóm dữ liệu EVI theo Quận, Năm và Mùa ---
    # Tính trung bình các chỉ số EVI, LAI, FPAR, LST cho mỗi mùa
    evi_seasonal = df_evi.groupby(['District', 'Year', 'Season'])[[
        'EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm'
    ]].mean().reset_index()

    print(f"Đã xử lý xong dữ liệu vệ tinh. Số dòng sau khi gộp theo mùa: {len(evi_seasonal)}")

    # --- 5. Gộp với file Main ---
    # Lưu ý: File Main có thể không có cột Year. 
    # Nếu gộp, mỗi dòng trong Main sẽ được nhân bản cho từng năm có trong file EVI.
    
    # Kiểm tra xem tên mùa trong file Main viết hoa hay thường để khớp
    # (Ví dụ: Main dùng "Kharif 1" hay "Kharif 1")
    # Ta sẽ chuẩn hóa về dạng Title case cho chắc chắn
    df_main['Season'] = df_main['Season'].astype(str).str.strip().str.title() 
    # Sửa lại Kharif 1/2 cho đúng định dạng nếu cần (ví dụ Main ghi "Kharif 1", code tạo ra "Kharif 1")
    
    print("Đang gộp dữ liệu...")
    merged_df = pd.merge(
        df_main, 
        evi_seasonal, 
        on=['District', 'Season'], # Gộp theo Quận và Mùa
        how='left' # Giữ lại tất cả dữ liệu từ file Main
    )

    # --- 6. Lưu kết quả ---
    output_filename = 'Process_Bangladesh_EVI_LAI_FPAR_LST_data.csv'
    merged_df.to_csv(output_filename, index=False)
    print(f"Thành công! File đã gộp được lưu tại: {output_filename}")
    print(merged_df[['District', 'Season', 'Soil_Moisture_mm']].head()) # In thử cột Soil Moisture để kiểm tra

process_and_merge_data(df_evi)