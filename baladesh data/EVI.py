import ee
import time

# 1. Khởi tạo
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("Đã kết nối thành công.")
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

def export_bangladesh_salinity_split_tasks():
    print("Đang chuẩn bị gửi 12 Tasks riêng biệt (mỗi tháng 1 file)...")

    # 2. Lấy ranh giới hành chính
    bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

    # 3. Hàm lọc mây (Masking) - ĐÃ SỬA
    # Dùng band SCL (Scene Classification Layer) thay vì QA60 để tránh lỗi thiếu band
    def maskS2clouds(image):
        scl = image.select('SCL')
        # SCL Classes:
        # 3: Cloud Shadows (Bóng mây)
        # 8: Cloud Medium Probability (Mây vừa)
        # 9: Cloud High Probability (Mây dày)
        # 10: Cirrus (Mây ti)
        # 11: Snow/Ice (Tuyết)
        
        # Giữ lại những pixel KHÔNG phải là các loại trên
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return image.updateMask(mask)

    # 4. Vòng lặp Python (Client-side)
    for month in range(1, 13):
        print(f" -> Đang thiết lập Task cho tháng {month}/2022...")

        # Tạo ngày
        start_date = ee.Date.fromYMD(2022, month, 1)
        end_date = start_date.advance(1, 'month')

        # Lấy ảnh và xử lý
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(bangladesh_districts) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) \
            .map(maskS2clouds) \
            .select(['B2', 'B4']) # Chọn band sau khi đã mask

        # Tính chỉ số độ mặn (NDSI hoặc Salinity Index tùy công thức của bạn)
        def add_si(img):
            si = img.expression(
                'sqrt(b("B2") * b("B4"))',
                {'B2': img.select('B2'), 'B4': img.select('B4')}
            ).rename('Salinity_Index_Raw')
            return img.addBands(si)

        # Tính trung bình tháng
        monthly_mean = s2.map(add_si).select('Salinity_Index_Raw').mean()

        # Reduce Regions
        stats = monthly_mean.reduceRegions(
            collection=bangladesh_districts,
            reducer=ee.Reducer.mean(),
            scale=100,      
            tileScale=16    
        )

        # Gán nhãn thời gian
        stats_with_date = stats.map(lambda f: f.set({
            'Month': month,
            'Year': 2022,
            'Salinity_Index_Raw': ee.Algorithms.If(f.get('mean'), f.get('mean'), -9999)
        }))

        # Cột cần xuất
        export_columns = ['ADM2_NAME', 'ADM1_NAME', 'Month', 'Year', 'Salinity_Index_Raw']

        # Tạo Task
        task_name = f'Bangladesh_Salinity_2022_Month_{month:02d}'
        task = ee.batch.Export.table.toDrive(
            collection=stats_with_date,
            description=task_name,
            folder='GEE_Exports_Split',
            fileNamePrefix=task_name,
            fileFormat='CSV',
            selectors=export_columns
        )

        # Gửi lệnh
        task.start()
        print(f"    [OK] Đã gửi Task ID: {task.id}")

    print("\n------------------------------------------------")
    print("Đã gửi xong 12 lệnh! Hãy kiểm tra Google Drive sau ít phút.")

if __name__ == "__main__":
    export_bangladesh_salinity_split_tasks()