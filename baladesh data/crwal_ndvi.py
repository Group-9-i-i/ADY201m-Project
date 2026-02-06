import ee
import pandas as pd

# 1. Khởi tạo kết nối
try:
    # Thay Project ID của bạn vào đây
    ee.Initialize(project='gen-lang-client-0272496285') 
    print("Kết nối GEE thành công!")
except Exception as e:
    print("Lỗi kết nối: ", e)
    exit()

def get_bangladesh_crop_seasons_2022():
    print("Đang xử lý dữ liệu cho 3 mùa vụ (Boro, Aus, Aman)...")

    # A. Lấy bản đồ 64 huyện
    districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

    # B. Định nghĩa 3 mùa vụ chính tại Bangladesh năm 2022
    # Start/End: Thời gian cây phát triển mạnh nhất để lấy NDVI
    # Harvest: Thời gian thu hoạch điển hình
    seasons = [
        {
            'name': 'Boro', # Mùa quan trọng nhất, năng suất cao nhất
            'start': '2022-01-15', 
            'end': '2022-04-15', 
            'harvest_window': 'April-May 2022'
        },
        {
            'name': 'Aus', 
            'start': '2022-05-01', 
            'end': '2022-07-30', 
            'harvest_window': 'July-August 2022'
        },
        {
            'name': 'Aman', # Mùa lúa mùa mưa
            'start': '2022-08-15', 
            'end': '2022-11-15', 
            'harvest_window': 'November-December 2022'
        }
    ]

    all_data = []

    # C. Vòng lặp qua từng mùa để lấy dữ liệu
    for season in seasons:
        print(f" -> Đang tính toán mùa: {season['name']}...")
        
        # Lọc ảnh vệ tinh trong khoảng thời gian của mùa vụ đó
        dataset = ee.ImageCollection("MODIS/061/MOD13Q1") \
            .filterDate(season['start'], season['end']) \
            .select('NDVI')

        # Lấy giá trị lớn nhất (max) của mùa vụ (thể hiện lúc cây xanh tốt nhất/sắp thu hoạch)
        # Dùng .max() tốt hơn .mean() khi muốn dự đoán năng suất tối đa
        ndvi_image = dataset.max().multiply(0.0001)

        # Tính toán cho từng huyện
        district_ndvi = ndvi_image.reduceRegions(
            collection=districts,
            reducer=ee.Reducer.mean(),
            scale=250
        )

        # Lấy dữ liệu về
        features = district_ndvi.select(['ADM2_NAME', 'mean']).getInfo()['features']

        # Đưa vào danh sách kết quả
        for ft in features:
            props = ft['properties']
            all_data.append({
                'District_Name': props.get('ADM2_NAME'),
                'Season': season['name'],
                'NDVI_Value': props.get('mean'), # NDVI trung bình của huyện trong mùa đó
                'Sowing_Date_Approx': season['start'], # Ngày gieo trồng ước tính
                'Harvest_Window': season['harvest_window'], # Thời gian thu hoạch
                'Year': 2022
            })

    # D. Xuất ra CSV
    df = pd.DataFrame(all_data)
    
    # Sắp xếp để dễ nhìn: Theo Huyện rồi đến Mùa
    df = df.sort_values(by=['District_Name', 'Sowing_Date_Approx'])
    
    filename = 'Bangladesh_NDVI_Seasons_2022.csv'
    df.to_csv(filename, index=False)
    
    print(f"\nĐã xong! File lưu tại: {filename}")
    print("Dữ liệu mẫu:")
    print(df.head())

if __name__ == "__main__":
    get_bangladesh_crop_seasons_2022()