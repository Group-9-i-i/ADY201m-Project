import pandas as pd
import requests
import ee
import time
from bs4 import BeautifulSoup

# ==========================================
# CẤU HÌNH NGƯỜI DÙNG
# ==========================================
PROJECT_ID = 'gen-lang-client-0272496285'  # Project ID của bạn
INPUT_FILE = 'bangladesh_districts_coordinates.csv' # File tôi đã tạo cho bạn
OUTPUT_FILE = 'bangladesh_soil_ph_2022_final.csv'

# ==========================================
# PHƯƠNG PHÁP 1: SOILGRIDS API (Dễ nhất, không cần login)
# ==========================================
def get_soilgrids_ph(lat, lon):
    """Lấy dữ liệu pH từ ISRIC SoilGrids (pH nước, độ sâu 0-5cm)"""
    try:
        url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&depth=0-5cm"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # SoilGrids lưu giá trị nhân 10, cần chia 10 để ra pH chuẩn
            ph_value = data['properties']['layers'][0]['depths'][0]['values']['mean'] / 10
            return ph_value
    except Exception as e:
        print(f"Lỗi SoilGrids tại {lat}, {lon}: {e}")
        return None
    return None

# ==========================================
# PHƯƠNG PHÁP 2: GOOGLE EARTH ENGINE (Chính xác nhất về không gian)
# ==========================================
def get_gee_ph(districts_df):
    """Lấy dữ liệu pH từ OpenLandMap qua GEE"""
    print("\n[GEE] Đang khởi tạo Google Earth Engine...")
    try:
        # Thử khởi tạo với Project ID của bạn
        try:
            ee.Initialize(project=PROJECT_ID)
        except:
            ee.Authenticate()
            ee.Initialize(project=PROJECT_ID)
            
        print("[GEE] Đang tải dữ liệu OpenLandMap...")
        
        # 1. Lấy Image pH đất (OpenLandMap)
        soil_ph_image = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4A1H_M/v02").select('b0')
        
        results = []
        total = len(districts_df)
        
        # 2. Loop qua từng điểm để lấy giá trị (Sampling)
        # Lưu ý: Cách này nhanh hơn là tải toàn bộ Shapefile huyện nếu chỉ cần điểm đại diện
        for index, row in districts_df.iterrows():
            try:
                point = ee.Geometry.Point([row['lon'], row['lat']])
                # Lấy giá trị tại điểm với scale 250m
                ph_dict = soil_ph_image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point,
                    scale=250,
                    maxPixels=1e9
                ).getInfo()
                
                ph_val = ph_dict.get('b0')
                if ph_val is not None:
                    results.append(ph_val / 10) # Chia 10
                else:
                    results.append(None)
                    
                if index % 10 == 0:
                    print(f"[GEE] Đã xử lý {index}/{total} huyện...")
            except Exception as inner_e:
                print(f"Lỗi GEE tại {row['name']}: {inner_e}")
                results.append(None)
                
        return results

    except Exception as e:
        print(f"[GEE] Không thể chạy GEE (Lỗi Auth hoặc Mạng): {e}")
        # Trả về list None nếu GEE lỗi để code không bị dừng
        return [None] * len(districts_df)

# ==========================================
# MAIN PIPELINE
# ==========================================
def main():
    print("--- BẮT ĐẦU TỔNG HỢP DỮ LIỆU ĐẤT BANGLADESH ---")
    
    # 1. Đọc dữ liệu đầu vào
    try:
        df = pd.read_csv(INPUT_FILE)
        print(f"Đã tải {len(df)} huyện từ {INPUT_FILE}")
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file {INPUT_FILE}. Hãy tải file CSV tôi cung cấp trước.")
        return

    # 2. Chạy Phương pháp 1: SoilGrids
    print("\n--- BƯỚC 1: LẤY DỮ LIỆU TỪ SOILGRIDS API ---")
    soilgrids_results = []
    for index, row in df.iterrows():
        ph = get_soilgrids_ph(row['lat'], row['lon'])
        soilgrids_results.append(ph)
        print(f"SoilGrids - {row['name']}: {ph}")
        time.sleep(0.2) # Delay nhẹ để tránh overload API
    
    df['pH_SoilGrids'] = soilgrids_results

    # 3. Chạy Phương pháp 2: GEE
    print("\n--- BƯỚC 2: LẤY DỮ LIỆU TỪ GOOGLE EARTH ENGINE ---")
    # Hỏi user có muốn chạy GEE không vì cần login
    run_gee = input("Bạn có muốn chạy module GEE không? (y/n): ").lower().strip()
    
    if run_gee == 'y':
        gee_results = get_gee_ph(df)
        df['pH_GEE_OpenLandMap'] = gee_results
    else:
        print("Đã bỏ qua bước GEE.")
        df['pH_GEE_OpenLandMap'] = None

    # 4. Tính toán kết quả cuối cùng (Trung bình các nguồn)
    # Ưu tiên GEE, nếu không có thì dùng SoilGrids
    df['pH_Final_2022_Est'] = df['pH_GEE_OpenLandMap'].fillna(df['pH_SoilGrids'])

    # 5. Xuất file
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n--- HOÀN THÀNH! ---")
    print(f"Dữ liệu đã được lưu vào: {OUTPUT_FILE}")
    print(df.head())

if __name__ == "__main__":
    main()