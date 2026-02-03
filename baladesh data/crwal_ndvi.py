import ee
import pandas as pd

# 1. Khởi tạo kết nối
try:
    # Dùng Project ID của bạn
    ee.Initialize(project='gen-lang-client-0272496285') 
    print("Kết nối GEE thành công!")
except Exception as e:
    print("Lỗi kết nối (hãy kiểm tra lại project ID hoặc chạy lệnh 'earthengine authenticate'): ", e)
    exit()

def get_bangladesh_ndvi_2022():
    print("Đang tải bản đồ 64 huyện và tính toán NDVI... Vui lòng đợi.")

    # A. Lấy bản đồ hành chính 64 huyện của Bangladesh (Level 2)
    # FAO GAUL là bộ dữ liệu chuẩn có sẵn trong Google Earth Engine
    districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

    # B. Lấy dữ liệu vệ tinh MODIS cho năm 2022
    # Bạn có thể sửa tháng ở dòng filterDate nếu muốn lấy theo mùa vụ (ví dụ: lúa Boro)
    dataset = ee.ImageCollection("MODIS/061/MOD13Q1") \
        .filterDate('2022-01-01', '2022-12-31') \
        .select('NDVI')

    # Tính ảnh trung bình của cả năm 2022 và nhân hệ số tỷ lệ 0.0001
    mean_ndvi_image = dataset.mean().multiply(0.0001)

    # C. Tính toán giá trị trung bình cho từng huyện (Reduce Regions)
    # Hàm này sẽ chạy trên server Google, nhanh hơn vòng lặp for
    district_ndvi = mean_ndvi_image.reduceRegions(
        collection=districts,
        reducer=ee.Reducer.mean(),
        scale=250  # Độ phân giải của MODIS là 250m
    )

    # D. Chuyển dữ liệu từ Server GEE về máy (Client-side)
    # Lưu ý: ADM2_NAME là tên Huyện trong dataset này
    data = district_ndvi.select(['ADM2_NAME', 'mean']).getInfo()

    # E. Xử lý dữ liệu thành DataFrame
    results = []
    for feature in data['features']:
        properties = feature['properties']
        district_name = properties.get('ADM2_NAME')
        ndvi_value = properties.get('mean')
        
        results.append({
            'District_Name': district_name,
            'NDVI_Average_2022': ndvi_value
        })

    # F. Tạo bảng và lưu file CSV
    df = pd.DataFrame(results)
    
    # Sắp xếp theo tên huyện cho đẹp
    df = df.sort_values(by='District_Name')
    
    # Lưu file
    output_filename = 'Bangladesh_NDVI_2022_64Districts.csv'
    df.to_csv(output_filename, index=False)
    
    print(f"\nThành công! Đã lưu dữ liệu vào file: {output_filename}")
    print(df.head()) # In thử 5 dòng đầu

# Chạy hàm
if __name__ == "__main__":
    get_bangladesh_ndvi_2022()