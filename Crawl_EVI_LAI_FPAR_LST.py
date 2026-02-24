import ee
import requests # Thêm thư viện này để tải file từ URL

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
        filtered = collection.select(band_name).filterDate(start_date, end_date)
        
        img = ee.Algorithms.If(
            filtered.size().gt(0),
            filtered.mean().multiply(scale).rename(new_name), 
            ee.Image.constant(-9999).rename(new_name)
        )
        return ee.Image(img)

    img_evi = get_safe_band(col_evi, 'EVI', 0.0001, 'EVI')
    img_lai = get_safe_band(col_lai_fpar, 'Lai_500m', 0.1, 'LAI')
    img_fpar = get_safe_band(col_lai_fpar, 'Fpar_500m', 0.1, 'FPAR')
    img_lst = get_safe_band(col_lst, 'LST_Day_1km', 0.02, 'LST_Kelvin')
    img_sm = get_safe_band(col_soil, 'ssm', 1.0, 'Soil_Moisture_mm')

    final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])
    
    final_image = final_image.set({
        'month': start_date.get('month'),
        'year': start_date.get('year')
    })

    stats = final_image.reduceRegions(
        collection=bangladesh_districts,
        reducer=ee.Reducer.mean(),
        scale=500 
    )
    
    return stats.map(lambda f: f.set({
        'Month': start_date.get('month'),
        'Year': start_date.get('year')
    }))

# --- BƯỚC 4: YÊU CẦU XỬ LÝ VÀ TẢI TRỰC TIẾP VỀ MÁY ---
print("--- Đang yêu cầu GEE xử lý và tạo link tải trực tiếp... ---")
print("Lưu ý: Quá trình này có thể mất vài phút. Vui lòng không tắt chương trình.")

months = ee.List.sequence(0, 11)
list_of_collections = months.map(process_safe_month)
nested_collection = ee.FeatureCollection(list_of_collections)
full_data = nested_collection.flatten()

try:
    # Lấy URL tải xuống trực tiếp dưới dạng CSV
    download_url = full_data.getDownloadURL(
        filetype='csv',
        selectors=['ADM2_NAME', 'ADM2_CODE', 'Month', 'Year', 'EVI', 'LAI', 'FPAR', 'LST_Kelvin', 'Soil_Moisture_mm']
    )
    
    print(f"Đã tạo link tải thành công trên server GEE.")
    print("Đang tiến hành tải file về máy tính...")
    
    # Dùng thư viện requests để tải file từ URL
    response = requests.get(download_url)
    
    if response.status_code == 200:
        filename = 'Bangladesh_EVI_LAI_FPAR_LST_data.csv'
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"[THÀNH CÔNG] Dữ liệu đã được lưu trực tiếp vào file: {filename}")
    else:
        print(f"[LỖI] Không thể tải file. Mã HTTP: {response.status_code}")

except Exception as e:
    print("\n[LỖI] Quá trình tính toán trực tiếp thất bại. Lỗi chi tiết:")
    print(e)
    print("\n=> NGUYÊN NHÂN: Thuật toán có thể quá nặng khiến server GEE bị Timeout (quá thời gian chờ phản hồi).")
    print("=> GIẢI PHÁP: Nếu gặp lỗi này, bạn bắt buộc phải dùng lệnh Export.table.toDrive() như code cũ để cho phép GEE chạy ngầm trên server, sau đó lên Google Drive tải thủ công.")