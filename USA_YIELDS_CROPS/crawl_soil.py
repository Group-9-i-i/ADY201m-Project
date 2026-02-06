import requests
import pandas as pd
import io
import time
import os
from datetime import datetime

# ================= CẤU HÌNH =================
# 1. Danh sách đầy đủ 50 Bang + DC
STATE_FIPS = {
    'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06', 'CO': '08', 
    'CT': '09', 'DE': '10', 'DC': '11', 'FL': '12', 'GA': '13', 'HI': '15', 
    'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19', 'KS': '20', 'KY': '21', 
    'LA': '22', 'ME': '23', 'MD': '24', 'MA': '25', 'MI': '26', 'MN': '27', 
    'MS': '28', 'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 
    'NJ': '34', 'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39', 
    'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45', 'SD': '46', 
    'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50', 'VA': '51', 'WA': '53', 
    'WV': '54', 'WI': '55', 'WY': '56'
}

# 2. Mapping Mã chất (USGS pCode) -> Tên nguyên tố
PARAM_MAP = {
    '01040': 'Cu', '01042': 'Cu', # Copper
    '00925': 'Mg', # Magnesium
    '01000': 'As', '01002': 'As', # Arsenic
    '01049': 'Pb', '01051': 'Pb', # Lead
    '01090': 'Zn', '01092': 'Zn', # Zinc
    '01046': 'Fe', '01045': 'Fe', # Iron
    '01056': 'Mn', # Manganese
    '00915': 'Ca', # Calcium
    '00935': 'K',  # Potassium
    '00666': 'P', '00665': 'P',   # Phosphorus
    '01025': 'Cd', # Cadmium
    '01030': 'Cr', # Chromium
    '01065': 'Ni', # Nickel
    '71900': 'Hg', '71890': 'Hg'  # Mercury
}

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"

def process_dataframe(df, state_name):
    """Hàm xử lý và xoay (pivot) bảng dữ liệu"""
    if df is None or df.empty:
        return None

    # [QUAN TRỌNG] Ép kiểu USGSPCode thành string và bù số 0 (ví dụ: 915 -> 00915)
    if 'USGSPCode' in df.columns:
        df['USGSPCode'] = df['USGSPCode'].astype(str).str.zfill(5)
    else:
        return None

    # 1. Lọc lấy các chất cần thiết
    df_filtered = df[df['USGSPCode'].isin(PARAM_MAP.keys())].copy()
    
    if df_filtered.empty:
        return None

    # 2. Tạo cột Element (Cu, Mg...)
    df_filtered['Element'] = df_filtered['USGSPCode'].map(PARAM_MAP)
    
    # 3. Làm sạch giá trị đo (chuyển về số)
    df_filtered['ResultMeasureValue'] = pd.to_numeric(df_filtered['ResultMeasureValue'], errors='coerce')
    df_filtered = df_filtered.dropna(subset=['ResultMeasureValue'])
    
    # 4. Thêm thông tin Bang và Năm
    df_filtered['State'] = state_name
    # Xử lý ngày tháng: Cắt 4 ký tự đầu làm năm
    df_filtered['Year'] = df_filtered['ActivityStartDate'].astype(str).str[:4]
    
    # 5. Pivot: Xoay bảng để mỗi chất thành 1 cột
    # Gom nhóm theo Năm, Bang, Ngày để gộp các kết quả đo trong cùng 1 ngày
    df_pivot = df_filtered.pivot_table(
        index=['Year', 'State', 'ActivityStartDate'],
        columns='Element',
        values='ResultMeasureValue',
        aggfunc='mean' # Lấy trung bình nếu 1 ngày đo nhiều lần
    ).reset_index()
    
    return df_pivot

def fetch_online():
    """Tải dữ liệu trực tiếp từ API cho 50 bang"""
    all_data = []
    print(f"Bắt đầu tải dữ liệu cho {len(STATE_FIPS)} bang/vùng lãnh thổ...\n")

    for state_abbr, fips in STATE_FIPS.items():
        print(f"--> [ONLINE] Đang tải bang: {state_abbr} (FIPS: {fips})...")
        
        params = {
            'statecode': f"US:{fips}",
            'pCode': ";".join(PARAM_MAP.keys()),
            'startDateLo': '01-01-2015',
            'startDateHi': '12-31-2025',
            'mimeType': 'csv',
            'dataProfile': 'resultPhysChem',
            'providers': 'NWIS'
        }
        
        try:
            # Tăng timeout lên 60s vì dữ liệu 10 năm khá nặng
            response = requests.get(BASE_URL, params=params, timeout=60)
            
            if response.status_code == 200:
                # Đọc CSV từ response, ép kiểu USGSPCode ngay từ đầu để tránh lỗi mất số 0
                csv_content = io.StringIO(response.content.decode('utf-8'))
                try:
                    df = pd.read_csv(csv_content, dtype={'USGSPCode': str}, low_memory=False)
                    
                    processed = process_dataframe(df, state_abbr)
                    if processed is not None:
                        all_data.append(processed)
                        print(f"    [OK] Lấy được {len(processed)} dòng dữ liệu đã xử lý.")
                    else:
                        print("    [Skip] Không có dữ liệu phù hợp.")
                except pd.errors.EmptyDataError:
                    print("    [Skip] Dữ liệu rỗng.")
            else:
                print(f"    [Lỗi] Server trả về code {response.status_code}")
                
        except Exception as e:
            print(f"    [Exception] Lỗi kết nối: {e}")
        
        # Nghỉ 1 giây để tránh bị chặn
        time.sleep(1)

    return all_data

def process_offline_file(file_path):
    """Xử lý file CSV đã có sẵn trên máy (nếu bạn tải thủ công)"""
    print(f"\n--> [OFFLINE] Đang đọc file: {file_path}")
    try:
        # Đọc file lớn theo từng phần (chunk) nếu cần, ở đây đọc hết 1 lần
        df = pd.read_csv(file_path, dtype={'USGSPCode': str}, low_memory=False)
        
        # Cố gắng lấy tên bang từ cột OrganizationIdentifier (ví dụ: USGS-CA -> CA)
        if 'OrganizationIdentifier' in df.columns:
            df['State_Extracted'] = df['OrganizationIdentifier'].astype(str).str.replace('USGS-', '')
            # Lấy danh sách các bang có trong file
            unique_states = df['State_Extracted'].unique()
            print(f"    Các bang tìm thấy trong file: {unique_states}")
            
            all_chunks = []
            for state in unique_states:
                # Lọc dữ liệu của từng bang để xử lý
                df_state = df[df['State_Extracted'] == state].copy()
                processed = process_dataframe(df_state, state)
                if processed is not None:
                    all_chunks.append(processed)
            
            return all_chunks
        else:
            print("    [Lỗi] Không tìm thấy cột OrganizationIdentifier để xác định bang.")
            return []
            
    except Exception as e:
        print(f"    [Lỗi] Không đọc được file: {e}")
        return []

# ================= MAIN =================
if __name__ == "__main__":
    # CHỌN CHẾ ĐỘ: True để tải mới (Online), False để dùng file cũ (Offline)
    MODE_ONLINE = True 
    
    final_data_list = []
    
    if MODE_ONLINE:
        final_data_list = fetch_online()
    else:
        # Nếu dùng offline, thay tên file của bạn vào đây
        final_data_list = process_offline_file('resultphyschem.csv')

    if final_data_list:
        final_df = pd.concat(final_data_list, ignore_index=True)
        
        # Sắp xếp cột cho đẹp
        cols = ['Year', 'State', 'ActivityStartDate'] + [c for c in final_df.columns if c not in ['Year', 'State', 'ActivityStartDate']]
        final_df = final_df[cols]
        
        filename = f"US_AllStates_FullData_{datetime.now().strftime('%Y%m%d')}.csv"
        final_df.to_csv(filename, index=False)
        print(f"\n[HOÀN TẤT] Dữ liệu tổng hợp đã lưu vào: {filename}")
        print(final_df.head())
    else:
        print("\n[THẤT BẠI] Không thu thập được dữ liệu nào.")