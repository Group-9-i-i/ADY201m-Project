import requests
import pandas as pd
import io

def get_faostat_npk_data(country_code, year, output_file="bangladesh_npk_2022.csv"):
    """
    Hàm lấy dữ liệu NPK từ FAOSTAT API (Domain: Fertilizers by Nutrient).
    
    Parameters:
    - country_code (int): Mã vùng FAO (Bangladesh = 16)
    - year (int): Năm cần lấy (2022)
    - output_file (str): Tên file CSV đầu ra
    """
    
    # 1. Cấu hình Endpoint và Parameters
    # Base URL của FAOSTAT API (JSON output)
    base_url = "https://fenixservices.fao.org/faostat/api/v1/en/data/RFN"
    
    # Các mã số (Codes) quan trọng để "đào" đúng dữ liệu:
    # area: 16 (Bangladesh)
    # year: 2022
    # item: 3102 (Nitrogen), 3103 (Phosphate P2O5), 3104 (Potash K2O)
    # element: 5157 (Agricultural Use - Lượng dùng trong nông nghiệp)
    
    params = {
        'area': country_code,
        'year': year,
        'item': '3102,3103,3104',  # Lấy cả 3 loại dinh dưỡng N, P, K
        'element': '5157',         # Chỉ lấy lượng sử dụng (Agricultural Use)
        'pageSize': 100            # Số lượng bản ghi tối đa (đủ cho 3 loại phân)
    }

    print(f"Dang gửi request tới FAOSTAT cho mã vùng {country_code}, năm {year}...")
    
    try:
        # 2. Gửi Request GET
        response = requests.get(base_url, params=params)
        response.raise_for_status() # Báo lỗi nếu kết nối hỏng
        
        # 3. Xử lý dữ liệu trả về (JSON)
        data = response.json()
        
        # Kiểm tra xem có dữ liệu trong phần 'data' hay không
        if 'data' in data and len(data['data']) > 0:
            records = data['data']
            
            # Chuyển thành DataFrame cho đẹp
            df = pd.DataFrame(records)
            
            # Lọc các cột quan trọng để hiển thị
            cols_to_keep = ['Area', 'Item', 'Element', 'Year', 'Unit', 'Value', 'Flag']
            # Lưu ý: Tên cột trong API đôi khi viết thường hoặc hoa tùy phiên bản, nên ta kiểm tra
            available_cols = [c for c in cols_to_keep if c in df.columns]
            final_df = df[available_cols]

            print("\n--- KẾT QUẢ TÌM THẤY ---")
            print(final_df.to_string(index=False))
            
            # Lưu ra file CSV để dùng sau này
            final_df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"\nĐã lưu dữ liệu vào file: {output_file}")
            
            return final_df
        else:
            print("Không tìm thấy dữ liệu nào với các tham số này (Có thể FAO chưa update 2022 cho mục này).")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Lỗi kết nối API: {e}")
        return None
    except Exception as e:
        print(f"Lỗi xử lý dữ liệu: {e}")
        return None

# --- CHẠY CHƯƠNG TRÌNH ---
# Mã FAO của Bangladesh là 16
if __name__ == "__main__":
    df_result = get_faostat_npk_data(country_code=16, year=2022)