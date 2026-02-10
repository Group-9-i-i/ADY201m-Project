import ee
from datetime import datetime

# 1. Khởi tạo và xác thực (Chạy 1 lần đầu, các lần sau có thể comment lại dòng Authenticate)
# ee.Authenticate()

# Khởi tạo với Project ID của bạn
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("Khởi tạo GEE thành công!")
except Exception as e:
    print(f"Lỗi khởi tạo: {e}")

# 2. Cấu hình tham số
# Bộ dữ liệu pH đất (Độ sâu 0cm, đơn vị x10). Đây là dữ liệu TĨNH.
# Nếu bạn có dữ liệu động, hãy thay đổi ImageCollection tại đây.
DATASET_ID = "OpenLandMap/SOL/SOL_PH-H2O_USDA-4A1-1/v02"
BAND_NAME = 'b0' # pH đất bề mặt
SCALE = 250      # Độ phân giải gốc của bộ dữ liệu này là 250m. Muốn chi tiết nhất hãy giữ nguyên.
FOLDER_NAME = "GEE_Bangladesh_pH_2022" # Tên thư mục trên Google Drive

# 3. Lấy ranh giới hành chính Bangladesh (Level 2 = Huyện/District)
bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

# Lấy danh sách ID của các huyện để loop (chuyển về Client-side)
district_list = bangladesh_districts.aggregate_array('ADM2_NAME').getInfo()
print(f"Tổng số huyện tìm thấy: {len(district_list)}")

# 4. Hàm xử lý xuất dữ liệu
def export_district_ph(district_name, month, year=2022):
    # Lấy feature của huyện hiện tại
    roi = bangladesh_districts.filter(ee.Filter.eq('ADM2_NAME', district_name)).geometry()
    
    # Lấy dữ liệu ảnh
    # LƯU Ý: Vì OpenLandMap là ảnh tĩnh, ta load trực tiếp.
    # Nếu là dữ liệu động (như NDVI), bạn sẽ dùng .filterDate() ở đây.
    img = ee.Image(DATASET_ID).select(BAND_NAME).clip(roi)
    
    # Đặt tên file gợi nhớ: Huyen_Thang_Nam
    file_name = f"pH_{district_name}_{year}_{month:02d}"
    
    # Tạo task export
    task = ee.batch.Export.image.toDrive(
        image=img,
        description=file_name, # Tên task trong GEE
        folder=FOLDER_NAME,    # Thư mục Drive
        fileNamePrefix=file_name,
        region=roi,            # Cắt đúng theo hình dáng huyện
        scale=SCALE,           # Độ phân giải (250m)
        maxPixels=1e9,         # Tăng giới hạn pixel tối đa
        crs='EPSG:4326',       # Hệ tọa độ WGS84
        fileFormat='GeoTIFF'
    )
    
    task.start()
    print(f"Đã gửi task: {file_name}")

# 5. Thực thi vòng lặp (Cẩn thận: Số lượng task sẽ rất lớn!)
# Bangladesh có khoảng 64 quận/huyện. 64 huyện * 12 tháng = 768 tasks.
# GEE giới hạn khoảng 3000 task trong queue, nên số lượng này vẫn ổn.

print("Bắt đầu gửi request...")

for district in district_list:
    # Làm sạch tên huyện để tránh lỗi đặt tên file (bỏ dấu cách, ký tự lạ)
    clean_name = district.replace(" ", "_").replace("(", "").replace(")", "")
    
    # Lặp qua 12 tháng
    for month in range(1, 13):
        try:
            export_district_ph(district, month)
        except Exception as e:
            print(f"Lỗi khi export {district} tháng {month}: {e}")

print("Hoàn tất gửi task. Vui lòng kiểm tra https://code.earthengine.google.com/tasks")