import pandas as pd
import os

# Tên file cần chia
INPUT_FILE = 'iowa_crops_2000_2024_full.csv'

def split_csv_half(filename):
    print(f"--- Đang đọc file: {filename} ---")
    
    if not os.path.exists(filename):
        print(f"Lỗi: Không tìm thấy file '{filename}' trong thư mục này.")
        return

    # 1. Đọc dữ liệu
    df = pd.read_csv(filename)
    total_rows = len(df)
    print(f"Tổng số dòng dữ liệu: {total_rows}")

    # 2. Tính vị trí giữa
    midpoint = total_rows // 2

    # 3. Cắt đôi (Slicing)
    # Phần 1: Từ đầu đến giữa
    part1 = df.iloc[:midpoint]
    # Phần 2: Từ giữa đến cuối
    part2 = df.iloc[midpoint:]

    # 4. Lưu ra 2 file mới
    output1 = 'iowa_crops_part1.csv'
    output2 = 'iowa_crops_part2.csv'

    part1.to_csv(output1, index=False)
    part2.to_csv(output2, index=False)

    print("\n--- HOÀN TẤT ---")
    print(f"Đã lưu: {output1} ({len(part1)} dòng)")
    print(f"Đã lưu: {output2} ({len(part2)} dòng)")

if __name__ == "__main__":
    split_csv_half(INPUT_FILE)