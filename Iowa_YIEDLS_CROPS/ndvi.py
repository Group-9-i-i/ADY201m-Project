import ee
import pandas as pd
import os
import time

# --- CẤU HÌNH ---
# ĐÃ CẬP NHẬT PROJECT ID CỦA BẠN
MY_PROJECT_ID = 'gen-lang-client-0272496285'

START_YEAR = 2000
END_YEAR = 2024
OUTPUT_DIR = "iowa_gee_raw_counties"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_raw_county_data():
    # 1. Khởi tạo GEE với Project ID cụ thể
    print(f"--- Đang kết nối GEE với Project: {MY_PROJECT_ID} ---")
    try:
        ee.Initialize(project=MY_PROJECT_ID)
        print("-> Xác thực thành công!")
    except Exception as e:
        print(f"-> Chưa xác thực hoặc lỗi token: {e}")
        print("-> Đang mở trình duyệt để cấp quyền lại...")
        ee.Authenticate()
        ee.Initialize(project=MY_PROJECT_ID)

    # 2. Lấy biên giới 99 Quận của Iowa
    iowa_counties = ee.FeatureCollection('TIGER/2018/Counties') \
                      .filter(ee.Filter.eq('STATEFP', '19')) \
                      .select(['GEOID', 'NAME'])

    print(f"-> Đã tải bản đồ Iowa (99 Quận).")

    # 3. Định nghĩa hàm trích xuất dữ liệu (Reducer)
    # tileScale=16 là 'bí kíp' để không bị lỗi 'User memory limit exceeded'
    def extract_data(image, band_list, scale):
        stats = image.reduceRegions(
            collection=iowa_counties,
            reducer=ee.Reducer.mean(),
            scale=scale,
            tileScale=16 
        )
        date = image.date().format('YYYY-MM-dd')
        return stats.map(lambda f: f.set('date', date))

    # --- VÒNG LẶP THEO NĂM ---
    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n--- Đang xử lý năm {year} ---")
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        # ======================================================
        # PHẦN A: NDVI & EVI (MOD13Q1 - 250m - 16 ngày)
        # ======================================================
        print("   + Đang tải NDVI/EVI...", end=" ")
        try:
            mod13 = ee.ImageCollection('MODIS/006/MOD13Q1') \
                      .filterDate(start_date, end_date) \
                      .select(['NDVI', 'EVI'])

            # Scale: Nhân 0.0001
            mod13_scaled = mod13.map(lambda img: img.multiply(0.0001) \
                                                    .set('system:time_start', img.get('system:time_start')))

            # Trích xuất
            ndvi_features = mod13_scaled.map(lambda img: extract_data(img, ['NDVI', 'EVI'], 500)).flatten()
            
            # Tải về
            ndvi_data = ndvi_features.getInfo()['features']
            
            rows_ndvi = []
            for f in ndvi_data:
                props = f['properties']
                rows_ndvi.append({
                    'date': props.get('date'),
                    'county_code': props.get('GEOID'),
                    'county_name': props.get('NAME'),
                    'NDVI': props.get('NDVI'),
                    'EVI': props.get('EVI')
                })
            
            if rows_ndvi:
                df_ndvi = pd.DataFrame(rows_ndvi)
                # Lưu file
                filename = os.path.join(OUTPUT_DIR, f"iowa_ndvi_evi_counties_{year}.csv")
                df_ndvi.to_csv(filename, index=False)
                print(f"OK ({len(df_ndvi)} dòng)")
            else:
                print("Không có dữ liệu.")

        except Exception as e:
            print(f"Lỗi tải NDVI: {e}")

        # ======================================================
        # PHẦN B: LAI & FPAR (MCD15A3H - 500m - 4 ngày)
        # ======================================================
        print("   + Đang tải LAI/FPAR...", end=" ")
        try:
            mod15 = ee.ImageCollection('MODIS/006/MCD15A3H') \
                      .filterDate(start_date, end_date) \
                      .select(['Lai', 'Fpar'])

            # Scale: LAI*0.1, FPAR*0.01
            def scale_mod15(img):
                lai = img.select('Lai').multiply(0.1)
                fpar = img.select('Fpar').multiply(0.01)
                return lai.addBands(fpar).set('system:time_start', img.get('system:time_start'))

            mod15_scaled = mod15.map(scale_mod15)

            # Trích xuất (Scale 1000m để nhanh hơn chút, vẫn đủ tốt cho cấp quận)
            lai_features = mod15_scaled.map(lambda img: extract_data(img, ['Lai', 'Fpar'], 1000)).flatten()
            
            # Tải về
            lai_data = lai_features.getInfo()['features']
            
            rows_lai = []
            for f in lai_data:
                props = f['properties']
                rows_lai.append({
                    'date': props.get('date'),
                    'county_code': props.get('GEOID'),
                    'county_name': props.get('NAME'),
                    'LAI': props.get('Lai'),
                    'FPAR': props.get('Fpar')
                })
            
            if rows_lai:
                df_lai = pd.DataFrame(rows_lai)
                # Lưu file
                filename = os.path.join(OUTPUT_DIR, f"iowa_lai_fpar_counties_{year}.csv")
                df_lai.to_csv(filename, index=False)
                print(f"OK ({len(df_lai)} dòng)")
            else:
                print("Không có dữ liệu.")

        except Exception as e:
            print(f"Lỗi tải LAI: {e}")

if __name__ == "__main__":
    get_raw_county_data()