import requests
import pandas as pd
import os
import time
from tqdm import tqdm

# URL API USDA
SDA_URL = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"

# Danh sách 50 Bang + DC
ALL_US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 
    'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 
    'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 
    'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 
    'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

def get_counties_for_state(state_abbr):
    """
    Lấy danh sách mã vùng (Area Symbols) của một bang.
    """
    query = f"""
    SELECT DISTINCT areasymbol 
    FROM legend 
    WHERE areasymbol LIKE '{state_abbr}%' 
    AND LEN(areasymbol) = 5 
    """
    payload = {"format": "JSON", "query": query}
    try:
        r = requests.post(SDA_URL, data=payload, timeout=30)
        if r.status_code == 200 and "Table" in r.json():
            data = r.json()['Table']
            if len(data) > 1:
                return [row[0] for row in data[1:]]
    except Exception as e:
        print(f"Lỗi lấy danh sách quận cho {state_abbr}: {e}")
    return []

def get_full_soil_data_by_area(area_symbol):
    """
    Lấy TOÀN BỘ dữ liệu (Full Columns) cho 1 mã vùng.
    Không dùng hàm AVG(), không Group By, lấy tất cả cột của bảng Component và Chorizon.
    """
    
    # Query này lấy:
    # 1. Thông tin bản đồ (Mapunit)
    # 2. Toàn bộ thông tin thành phần đất (Component - c.*)
    # 3. Toàn bộ thông tin lớp đất (Chorizon - ch.*)
    # 4. Bỏ qua lọc độ sâu và tỷ lệ % để lấy hết mọi thứ.
    
    query = f"""
    SELECT 
        l.areasymbol AS State_County_Code,
        mu.musym AS Map_Unit_Symbol,
        mu.muname AS Map_Unit_Name,
        c.compname AS Component_Name,
        c.comppct_r AS Component_Percent,
        c.taxclname AS Taxonomy_Class,
        -- Lấy toàn bộ thuộc tính vật lý/hóa học của lớp đất
        ch.* FROM legend l
    INNER JOIN mapunit mu ON mu.lkey = l.lkey
    INNER JOIN component c ON c.mukey = mu.mukey
    INNER JOIN chorizon ch ON ch.cokey = c.cokey
    WHERE l.areasymbol = '{area_symbol}'
    -- KHÔNG LỌC ĐỘ SÂU (Lấy cả đất sâu)
    -- KHÔNG LỌC TỶ LỆ (Lấy cả đất phụ)
    ORDER BY mu.musym, c.comppct_r DESC, ch.hzdept_r
    """

    payload = {"format": "JSON+COLUMNNAME", "query": query}
    
    try:
        # Tăng timeout lên 60s vì dữ liệu trả về rất lớn
        response = requests.post(SDA_URL, data=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if "Table" in data and len(data['Table']) > 1:
                columns = data['Table'][0]
                rows = data['Table'][1:]
                return pd.DataFrame(rows, columns=columns)
            
    except Exception as e:
        # Nếu lỗi quá tải, thử in ra để biết
        # print(f"Lỗi tải {area_symbol}: {e}")
        pass
        
    return None

# --- CHƯƠNG TRÌNH CHÍNH ---

output_folder = "US_Soil_Data_FULL"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

print(f"Bắt đầu tải DỮ LIỆU ĐẦY ĐỦ (FULL RAW DATA) cho {len(ALL_US_STATES)} bang...")
print("CẢNH BÁO: File sẽ rất lớn và chứa hàng trăm cột dữ liệu.")
print("-" * 50)

for state in ALL_US_STATES:
    filename = f"{output_folder}/full_soil_data_{state}.csv"
    
    if os.path.exists(filename):
        print(f"[SKIP] Bang {state} đã có file, bỏ qua.")
        continue

    print(f"\n>> Đang xử lý Bang: {state}")
    
    counties = get_counties_for_state(state)
    if not counties:
        print(f"   [!] Không tìm thấy quận nào cho bang {state}.")
        continue
    
    print(f"   -> Tìm thấy {len(counties)} khu vực. Đang tải chi tiết...")
    
    state_data = []
    
    # Sử dụng tqdm để hiện tiến độ
    for area in tqdm(counties, desc=f"   Tải {state}", unit="quận"):
        df = get_full_soil_data_by_area(area)
        if df is not None:
            state_data.append(df)
        time.sleep(0.2) # Nghỉ lâu hơn chút để server kịp xử lý query nặng
    
    # Lưu file
    if state_data:
        try:
            print(f"   -> Đang gộp dữ liệu bang {state} (có thể mất vài phút)...")
            final_df = pd.concat(state_data, ignore_index=True)
            
            final_df.to_csv(filename, index=False)
            print(f"   [OK] Đã lưu: {filename}")
            print(f"        Kích thước: {len(final_df)} dòng x {len(final_df.columns)} cột")
        except Exception as e:
            print(f"   [ERROR] Lỗi khi lưu file bang {state}: {e}")
    else:
        print(f"   [EMPTY] Bang {state} không trả về dữ liệu.")

print("\n" + "="*50)
print("HOÀN TẤT.")