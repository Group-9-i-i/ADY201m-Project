import pandas as pd
import numpy as np

# 1. Tải bộ dữ liệu chính
# Thêm tên thư mục "New folder/" vào trước tên file
df = pd.read_csv('New folder/data_enriched_npk.csv')

# Kiểm tra nhanh dữ liệu ban đầu
print("Số dòng/cột ban đầu:", df.shape)
print(df.info())

# Danh sách cột cần giữ và tên mới tương ứng
# Mapping: Tên cũ -> Tên mới
rename_map = {
    'Location': 'Khu vực',
    # 'Tiểu bang': Chưa có, sẽ tạo thêm
    'Rainfall': 'Lượng mưa trung bình',
    'Temperature': 'Nhiệt độ trung bình của năm',
    'Irrigation': 'Tỷ lệ đất được tưới tiêu',
    # 'Tổng lượng phân bón': Sẽ tính từ N, P, K (dù dữ liệu đang rỗng)
    'Crops': 'Loại cây ở khu vực đó',
    'yeilds': 'Năng suất trung bình của khu vực'
}

# Tạo cột Tiểu bang (Giả định dữ liệu này chủ yếu ở Karnataka dựa trên tên file weather, bạn có thể map lại nếu cần)
df['Tiểu bang'] = 'Karnataka'

# Tính Tổng lượng phân bón (Hiện tại cột N, P, K trong file rỗng, ta cứ tạo cột tổng để giữ cấu trúc)
# Sử dụng fillna(0) để tránh lỗi cộng NaN nếu bạn muốn mặc định là 0
df['Tổng lượng phân bón tiêu thụ trong năm'] = df['N'].fillna(0) + df['P'].fillna(0) + df['K'].fillna(0)

# Đổi tên các cột hiện có
df = df.rename(columns=rename_map)

# Chỉ giữ lại các cột đúng yêu cầu (Loại bỏ Year, Area, Humidity, price, Season, Soil type...)
required_columns = [
    'Khu vực', 'Tiểu bang', 'Lượng mưa trung bình', 'Nhiệt độ trung bình của năm',
    'Tỷ lệ đất được tưới tiêu', 'Tổng lượng phân bón tiêu thụ trong năm',
    'Loại cây ở khu vực đó', 'Năng suất trung bình của khu vực'
]

# Lọc lấy danh sách cột cuối cùng
df_clean = df[required_columns].copy()

print("Các cột sau khi lọc:", df_clean.columns.tolist())

# Kiểm tra số lượng dòng trùng
print(f"Số dòng trùng lặp: {df_clean.duplicated().sum()}")

# Xóa trùng lặp
df_clean = df_clean.drop_duplicates()


# Kiểm tra dữ liệu thiếu
print(df_clean.isnull().sum())

# Cấu hình danh sách các cột số cần điền dữ liệu
numeric_cols = ['Lượng mưa trung bình', 'Nhiệt độ trung bình của năm',
                'Tổng lượng phân bón tiêu thụ trong năm', 'Năng suất trung bình của khu vực']

for col in numeric_cols:
    # Nếu cột thiếu dữ liệu > 0
    if df_clean[col].isnull().sum() > 0:
        # Cách 1: Điền bằng trung vị (Median) - Tốt nếu dữ liệu có outlier
        median_val = df_clean[col].median()
        df_clean[col].fillna(median_val, inplace=True)
        print(f"Đã điền cột '{col}' bằng giá trị: {median_val}")

# Nếu vẫn còn dòng thiếu (ví dụ ở cột chữ như Khu vực), ta xóa bỏ
df_clean.dropna(inplace=True)

# 1. Chuẩn hóa chuỗi (Xóa khoảng trắng đầu/cuối ở các cột chữ)
str_cols = ['Khu vực', 'Tiểu bang', 'Loại cây ở khu vực đó', 'Tỷ lệ đất được tưới tiêu']
for col in str_cols:
    df_clean[col] = df_clean[col].astype(str).str.strip()

# 2. Xử lý lỗi chính tả cụ thể (Ví dụ từ yêu cầu của bạn)
# Thay thế toàn bộ các biến thể sai thành đúng
correction_map = {
    'karnartakaka': 'Karnataka',
    'karnataka': 'Karnataka', # Viết hoa chữ cái đầu
    'Kasaragodu': 'Kasaragod' # Ví dụ chuẩn hóa tên quận
}
df_clean['Tiểu bang'] = df_clean['Tiểu bang'].replace(correction_map)

# 3. Kiểm tra cột 'Tỷ lệ đất được tưới tiêu'
# Lưu ý: Trong file gốc cột này là "Drip", "Basin"... (dạng chữ).
# Nếu yêu cầu là "Tỷ lệ" (số %), bạn cần dữ liệu bổ sung để map.
# Tạm thời ta giữ nguyên định dạng chữ để đảm bảo nhất quán.

# Hàm xử lý Outlier bằng phương pháp IQR (Interquartile Range)
def remove_outliers(df, column):
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    # Lọc bỏ các giá trị ngoài vùng này
    # Hoặc gán lại giá trị trần/sàn (tùy nghiệp vụ)
    # Ở đây tôi demo cách lọc bỏ dòng
    initial_len = len(df)
    df_result = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
    print(f"Cột {column}: Đã xóa {initial_len - len(df_result)} dòng outliers.")
    return df_result

# Áp dụng cho Lượng mưa và Năng suất
df_clean = remove_outliers(df_clean, 'Lượng mưa trung bình')
df_clean = remove_outliers(df_clean, 'Năng suất trung bình của khu vực')

# Xử lý cứng các lỗi logic (như ví dụ trong ảnh)
# Ví dụ: Loại bỏ nếu năng suất < 0 (nếu có)
df_clean = df_clean[df_clean['Năng suất trung bình của khu vực'] >= 0]

df_clean.to_csv('Cleaned_Crop_Data.csv', index=False)