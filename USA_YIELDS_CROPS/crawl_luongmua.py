import requests
import pandas as pd
import time
from datetime import datetime

# ================= CẤU HÌNH =================
API_TOKEN = 'UfgTNtgxCaUKkKBKbyxkhLzVFerhklZd'  # <--- Thay Token của bạn vào đây
BASE_URL = 'https://www.ncdc.noaa.gov/cdo-web/api/v2/data'
START_DATE = '2015-01-01'
END_DATE = '2025-12-31'

# Danh sách mã FIPS cho 50 bang + DC
# NOAA sử dụng mã FIPS số (VD: 01 cho Alabama)
US_STATES = {
    '01': 'Alabama', '02': 'Alaska', '04': 'Arizona', '05': 'Arkansas',
    '06': 'California', '08': 'Colorado', '09': 'Connecticut', '10': 'Delaware',
    '11': 'District of Columbia', '12': 'Florida', '13': 'Georgia', '15': 'Hawaii',
    '16': 'Idaho', '17': 'Illinois', '18': 'Indiana', '19': 'Iowa',
    '20': 'Kansas', '21': 'Kentucky', '22': 'Louisiana', '23': 'Maine',
    '24': 'Maryland', '25': 'Massachusetts', '26': 'Michigan', '27': 'Minnesota',
    '28': 'Mississippi', '29': 'Missouri', '30': 'Montana', '31': 'Nebraska',
    '32': 'Nevada', '33': 'New Hampshire', '34': 'New Jersey', '35': 'New Mexico',
    '36': 'New York', '37': 'North Carolina', '38': 'North Dakota', '39': 'Ohio',
    '40': 'Oklahoma', '41': 'Oregon', '42': 'Pennsylvania', '44': 'Rhode Island',
    '45': 'South Carolina', '46': 'South Dakota', '47': 'Tennessee', '48': 'Texas',
    '49': 'Utah', '50': 'Vermont', '51': 'Virginia', '53': 'Washington',
    '54': 'West Virginia', '55': 'Wisconsin', '56': 'Wyoming'
}

def get_state_rainfall(fips, state_name):
    """
    Lấy dữ liệu 10 năm cho 1 bang.
    Dataset: GSOM (Global Summary of the Month)
    Datatype: PRCP (Precipitation)
    """
    print(f"--> Đang tải dữ liệu cho: {state_name} ({fips})...")
    
    headers = {'token': API_TOKEN}
    params = {
        'datasetid': 'GSOM',
        'datatypeid': 'PRCP',
        'locationid': f'FIPS:{fips}',
        'startdate': START_DATE,
        'enddate': END_DATE,
        'limit': 1000,      # Tối đa 1000 bản ghi (10 năm x 12 tháng = 120 bản ghi, nên thoải mái)
        'units': 'metric'   # Trả về milimet (mm)
    }

    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        
        # Xử lý trường hợp API quá tải (Status 429) hoặc lỗi server (500)
        if response.status_code != 200:
            print(f"   [LỖI] API trả về mã {response.status_code} cho {state_name}")
            return []

        data = response.json()
        
        if 'results' in data:
            results = []
            for item in data['results']:
                # Trích xuất và làm sạch dữ liệu
                record = {
                    'State': state_name,
                    'FIPS': fips,
                    'Date': item['date'],
                    'Year': item['date'][:4],
                    'Month': item['date'][5:7],
                    'Precipitation_mm': item['value']
                }
                results.append(record)
            return results
        else:
            print(f"   [Cảnh báo] Không tìm thấy dữ liệu mưa cho {state_name}")
            return []
            
    except Exception as e:
        print(f"   [LỖI NGOẠI LỆ] {e}")
        return []

# ================= CHẠY CHƯƠNG TRÌNH =================
def main():
    if API_TOKEN == 'DÁN_TOKEN_CỦA_BẠN_VÀO_ĐÂY':
        print("LỖI: Bạn chưa nhập API Token. Vui lòng sửa dòng API_TOKEN trong code.")
        return

    all_data = []
    
    # Lặp qua từng bang
    for fips, name in US_STATES.items():
        state_data = get_state_rainfall(fips, name)
        all_data.extend(state_data)
        
        # Ngủ 0.2 giây giữa các lần gọi để tôn trọng giới hạn API của NOAA
        time.sleep(0.2) 

    # Tạo DataFrame và xuất file
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Sắp xếp cho đẹp
        df = df.sort_values(by=['State', 'Date'])
        
        # Xuất ra CSV
        filename = f'USA_Rainfall_2015_2025_{datetime.now().strftime("%Y%m%d")}.csv'
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ HOÀN THÀNH! Đã lấy được {len(df)} dòng dữ liệu.")
        print(f"📁 Dữ liệu đã được lưu vào file: {filename}")
        
        # Hiển thị mẫu 5 dòng đầu
        print(df.head())
    else:
        print("\n❌ Không lấy được dữ liệu nào. Vui lòng kiểm tra Token hoặc kết nối mạng.")

if __name__ == "__main__":
    main()