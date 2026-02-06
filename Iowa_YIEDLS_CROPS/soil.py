import requests
import pandas as pd
import time
import os

# --- CẤU HÌNH ---
YOUR_API_KEY = "B78E0F65-2875-3F09-B2B7-9EB201AA8842" # Key của bạn
STATE = "IOWA"
START_YEAR = 2000
END_YEAR = 2024
OUTPUT_FOLDER = "iowa_management_data"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def get_nass_data(api_key, params, filename_desc):
    """
    Hàm chung để tải dữ liệu từ USDA NASS dựa trên tham số truyền vào
    """
    base_url = "http://quickstats.nass.usda.gov/api/api_GET/"
    
    # Thêm các tham số mặc định
    params['key'] = api_key
    params['state_name'] = STATE
    params['format'] = 'JSON'
    
    print(f"--- Đang tải dữ liệu: {filename_desc} ---")
    
    # Chia nhỏ theo năm để tránh lỗi quá tải nếu cần, hoặc tải gói lớn
    # Với dữ liệu quản lý, thường tải 1 lần là được vì nó nhẹ hơn dữ liệu Yield
    try:
        response = requests.get(base_url, params=params, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                df = pd.DataFrame(data['data'])
                print(f"-> Thành công! Tải được {len(df)} dòng.")
                
                # Lưu file
                outfile = os.path.join(OUTPUT_FOLDER, f"iowa_{filename_desc}.csv")
                df.to_csv(outfile, index=False)
                print(f"-> Đã lưu: {outfile}")
                return df
            else:
                print("-> Không có dữ liệu trả về.")
                return None
        else:
            print(f"-> Lỗi API: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"-> Lỗi kết nối: {e}")
        return None

def main_management_mining():
    
    # 1. DỮ LIỆU TIẾN ĐỘ GIEO TRỒNG & THU HOẠCH (CROP PROGRESS)
    # Giúp xác định: Ngày bắt đầu vụ và ngày kết thúc vụ chính xác từng năm
    params_progress = {
        'sector_desc': 'CROPS',
        'commodity_desc': 'CORN', # Hoặc SOYBEANS
        'statisticcat_desc': 'PROGRESS',
        'unit_desc': 'PCT PLANTED', # Lấy phần trăm gieo trồng
        'year__GE': str(START_YEAR) # Lấy từ năm 2000 trở đi
    }
    # Lấy cả tiến độ thu hoạch
    params_harvest = params_progress.copy()
    params_harvest['unit_desc'] = 'PCT HARVESTED'
    
    print("\n[1/4] Tải dữ liệu Ngày Gieo/Gặt (Crop Progress)...")
    get_nass_data(YOUR_API_KEY, params_progress, "corn_planting_progress")
    get_nass_data(YOUR_API_KEY, params_harvest, "corn_harvest_progress")
    
    
    # 2. DỮ LIỆU MẬT ĐỘ GIEO TRỒNG (PLANT POPULATION)
    # Cho biết nông dân gieo dày hay thưa (Cây/mẫu)
    params_pop = {
        'sector_desc': 'CROPS',
        'commodity_desc': 'CORN',
        'statisticcat_desc': 'PLANT POPULATION',
        'unit_desc': 'PLANTS / ACRE',
        'year__GE': str(START_YEAR)
    }
    
    print("\n[2/4] Tải dữ liệu Mật độ cây trồng (Plant Population)...")
    get_nass_data(YOUR_API_KEY, params_pop, "corn_plant_population")


    # 3. DỮ LIỆU PHÂN BÓN (FERTILIZER APPLICATIONS)
    # Lượng Nitơ, Phốt pho, Kali bón cho cây
    # Lưu ý: Dữ liệu này nằm ở sector 'ENVIRONMENTAL'
    params_fertilizer = {
        'sector_desc': 'ENVIRONMENTAL',
        'group_desc': 'FIELD CROPS',
        'commodity_desc': 'CORN',
        'statisticcat_desc': 'APPLICATIONS', # Số lần bón và lượng bón
        'year__GE': str(START_YEAR)
    }
    
    print("\n[3/4] Tải dữ liệu Phân bón (Fertilizer)...")
    get_nass_data(YOUR_API_KEY, params_fertilizer, "corn_fertilizer_use")


    # 4. DỮ LIỆU THUỐC TRỪ SÂU/HÓA CHẤT (CHEMICAL/PESTICIDE)
    # Loại thuốc, lượng dùng (lbs/acre)
    params_chemical = {
        'sector_desc': 'ENVIRONMENTAL',
        'group_desc': 'FIELD CROPS',
        'commodity_desc': 'CORN',
        'statisticcat_desc': 'TREATED', # Diện tích được xử lý thuốc
        'year__GE': str(START_YEAR)
    }
    
    print("\n[4/4] Tải dữ liệu Thuốc trừ sâu (Pesticides)...")
    get_nass_data(YOUR_API_KEY, params_chemical, "corn_pesticide_use")

if __name__ == "__main__":
    main_management_mining()