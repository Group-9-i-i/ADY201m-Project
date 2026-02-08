import ee

# --- BƯỚC 1: KHỞI TẠO ---
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("[OK] Kết nối GEE thành công.")
except:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

# --- BƯỚC 2: CHUẨN BỊ DỮ LIỆU ---
print("--- Đang thiết lập dữ liệu... ---")

bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

# ĐỊNH NGHĨA CÁC BỘ DỮ LIỆU
col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(['EVI'])
col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H").select(['Lai_500m', 'Fpar_500m'])
col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(['LST_Day_1km'])
col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(['ssm'])

# --- BƯỚC 3: HÀM XỬ LÝ AN TOÀN ---
def process_safe_month(month_offset):
    start_date = ee.Date('2022-01-01').advance(month_offset, 'month')
    end_date = start_date.advance(1, 'month')
    
    # Hàm con: Lấy dữ liệu an toàn
    def get_safe_band(collection, band_name, scale, new_name):
        # Select đúng 1 band
        filtered = collection.select(band_name).filterDate(start_date, end_date)
        
        # Kiểm tra nếu có ảnh thì lấy Mean, không thì trả về -9999
        img = ee.Algorithms.If(
            filtered.size().gt(0),
            filtered.mean().multiply(scale).rename(new_name), 
            ee.Image.constant(-9999).rename(new_name)
        )
        return ee.Image(img)

    # Lấy từng chỉ số
    img_evi = get_safe_band(col_evi, 'EVI', 0.0001, 'EVI')
    img_lai = get_safe_band(col_lai_fpar, 'Lai_500m', 0.1, 'LAI')
    img_fpar = get_safe_band(col_lai_fpar, 'Fpar_500m', 0.1, 'FPAR')
    img_lst = get_safe_band(col_lst, 'LST_Day_1km', 0.02, 'LST_Kelvin')
    img_sm = get_safe_band(col_soil, 'ssm', 1.0, 'Soil_Moisture_mm')

    # Ghép lại thành 1 ảnh
    final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])
    
    # Gán thời gian
    final_image = final_image.set({
        'month': start_date.get('month'),
        'year': start_date.get('year')
    })

    # Tính toán thống kê
    stats = final_image.reduceRegions(
        collection=bangladesh_districts,
        reducer=ee.Reducer.mean(),
        scale=500 
    )
    
    # Thêm cột thời gian
    return stats.map(lambda f: f.set({
        'Month': start_date.get('month'),
        'Year': start_date.get('year')
    }))

# --- BƯỚC 4: GỬI LỆNH EXPORT (ĐÃ SỬA LỖI COLLECTION OF COLLECTIONS) ---
print("--- Đang xử lý và gửi Task... ---")

months = ee.List.sequence(0, 11)

# 1. Map qua danh sách tháng -> Tạo ra một List chứa các FeatureCollection
list_of_collections = months.map(process_safe_month)

# 2. Biến List đó thành FeatureCollection -> Lúc này nó là "Collection of Collections" (lồng nhau)
nested_collection = ee.FeatureCollection(list_of_collections)

# 3. QUAN TRỌNG NHẤT: .flatten() để đập bẹp các collection con thành 1 bảng phẳng
full_data = nested_collection.flatten()

task = ee.batch.Export.table.toDrive(
    collection=full_data,
    description='Bangla_Env_Data_No_Errors', 
    folder='GEE_Bangladesh_Data',
    fileNamePrefix='Bangladesh_Env_Indicators_2022_Success',
    fileFormat='CSV',
    selectors=['ADM2_NAME', 'ADM2_CODE', 'Month', 'Year', 'EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm']
)

task.start()

print(f"\n[THÀNH CÔNG] Đã gửi Task ID: {task.id}")
print("Code này đã sửa lỗi 'Collection of Collections'. Chúc mừng bạn!")
print("Link: https://code.earthengine.google.com/tasks")