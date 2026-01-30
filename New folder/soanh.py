import pandas as pd

# --- CẤU HÌNH ---
# Thay tên 2 file csv của bạn vào đây
FILE_1 = "data_season_with_ndvi_fixed.csv" # File gốc (ví dụ file NASA)
FILE_2 = "Karnataka_Weather_Wind_2004_2025_Full.csv" # File cần so sánh (ví dụ file OpenMeteo)

# Tên cột chứa tên quận trong mỗi file (thường là 'District' hoặc 'name')
COL_NAME_1 = "District"
COL_NAME_2 = "District"

def compare_csv_columns():
    try:
        # 1. Đọc dữ liệu
        print(f"Đang đọc file 1: {FILE_1}...")
        df1 = pd.read_csv(FILE_1)
        
        print(f"Đang đọc file 2: {FILE_2}...")
        df2 = pd.read_csv(FILE_2)

        # 2. Lấy danh sách quận và chuẩn hóa (xóa khoảng trắng thừa, đưa về dạng chuỗi)
        # Dùng set() để loại bỏ các quận trùng lặp trong chính file đó
        districts_1 = set(df1[COL_NAME_1].astype(str).str.strip())
        districts_2 = set(df2[COL_NAME_2].astype(str).str.strip())

        print("\n" + "="*50)
        print("KẾT QUẢ SO SÁNH:")
        print("="*50)
        
        # 3. Tìm điểm chung và riêng
        # Intersection (&): Phần giao nhau (có ở cả 2)
        common = districts_1 & districts_2
        
        # Difference (-): Phần hiệu (có ở A mà không có ở B)
        only_in_1 = districts_1 - districts_2
        only_in_2 = districts_2 - districts_1

        # 4. In kết quả
        print(f"✅ Số lượng quận TRÙNG NHAU: {len(common)}")
        if len(common) > 0:
            print(f"Danh sách: {sorted(list(common))}")
        
        print("-" * 50)
        
        print(f"1️⃣  Số quận CHỈ CÓ ở {FILE_1}: {len(only_in_1)}")
        if len(only_in_1) > 0:
            print(f"Danh sách: {sorted(list(only_in_1))}")
        else:
            print("(Không có, file 2 bao gồm tất cả quận của file 1)")

        print("-" * 50)

        print(f"2️⃣  Số quận CHỈ CÓ ở {FILE_2}: {len(only_in_2)}")
        if len(only_in_2) > 0:
            print(f"Danh sách: {sorted(list(only_in_2))}")
        else:
            print("(Không có, file 1 bao gồm tất cả quận của file 2)")
            
    except FileNotFoundError as e:
        print(f"❌ Lỗi: Không tìm thấy file. Hãy kiểm tra lại tên file.\nChi tiết: {e}")
    except KeyError as e:
        print(f"❌ Lỗi: Không tìm thấy tên cột '{e}'. Hãy kiểm tra lại tên cột trong file CSV.")
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")

if __name__ == "__main__":
    compare_csv_columns()