import pandas as pd
import numpy as np

def process_weather_data():
    print("1. Đang đọc dữ liệu...")
    # Đọc 2 file dữ liệu
    main_df = pd.read_csv('Bangladesh_main_data.csv')
    weather_df = pd.read_csv('bangladesh_weather_data.csv')

    # -------------------------------------------------------------------
    # BƯỚC 1: CHUẨN HÓA TÊN DISTRICT (DISTRICT STANDARDIZATION)
    # -------------------------------------------------------------------
    print("2. Chuẩn hóa tên District...")
    # Lấy danh sách 64 huyện chuẩn từ file main
    valid_districts = main_df['District'].dropna().unique()
    
    # Dọn dẹp chuỗi (xóa khoảng trắng thừa, viết hoa chữ cái đầu)
    weather_df['District'] = weather_df['District'].astype(str).str.strip().str.title()
    
    # Kiểm tra xem có huyện nào bị lệch tên không
    missing_in_main = set(weather_df['District']) - set(valid_districts)
    if missing_in_main:
        print(f"Cảnh báo: Có các huyện không khớp với file main: {missing_in_main}")
        # Nếu sau này có lệch (VD: Jhalokati vs Jhallokati), bạn có thể thêm từ điển map vào đây:
        # district_map = {'Jhalokati': 'Jhallokati'}
        # weather_df['District'] = weather_df['District'].replace(district_map)
    else:
        print(" -> 100% tên District đã khớp với file Bangladesh_main_data.csv!")

    # -------------------------------------------------------------------
    # BƯỚC 2: TÍNH TOÁN CÁC CHỈ SỐ MỚI (FEATURE ENGINEERING)
    # -------------------------------------------------------------------
    print("3. Tính toán các chỉ số dự đoán năng suất cây trồng...")
    
    # 2.1. Biên độ nhiệt (Diurnal Temperature Range - DTR)
    weather_df['Temp_Range'] = weather_df['Temp_Max'] - weather_df['Temp_Min']
    
    # 2.2. Biên độ gió (Wind Speed Range)
    weather_df['Wind_Range'] = weather_df['Wind_Max'] - weather_df['Wind_Min']
    
    # 2.3. Tỷ lệ Mưa/Nhiệt độ (Rainfall to Temperature Ratio - Proxy cho khô hạn)
    # Tránh lỗi chia cho 0 nếu Temp_Mean = 0 bằng cách cộng thêm 1 epsilon nhỏ
    weather_df['Rain_Temp_Ratio'] = weather_df['Rainfall'] / (weather_df['Temp_Mean'] + 0.001)
    
    # 2.4. Phân loại Rủi ro Sốc Nhiệt (Heat Stress Risk Category)
    # Chuyển đổi liên tục sang dạng Categorical (Low, Moderate, High)
    conditions = [
        (weather_df['Heat_Stress_Days'] == 0),
        (weather_df['Heat_Stress_Days'] > 0) & (weather_df['Heat_Stress_Days'] <= 15),
        (weather_df['Heat_Stress_Days'] > 15)
    ]
    choices = ['Low Risk', 'Moderate Risk', 'High Risk']
    weather_df['Extreme_Heat_Risk'] = np.select(conditions, choices, default='Unknown')

    # 2.5 (Tùy chọn) Chỉ báo nắng nóng cực đoan (Binary Indicator)
    # Rất hữu ích cho các mô hình Machine Learning (Random Forest, XGBoost)
    weather_df['Is_Extreme_Heat'] = np.where(weather_df['Temp_Max'] > 38, 1, 0)

    # Làm tròn các cột số thực cho đẹp (2 chữ số thập phân)
    cols_to_round = ['Rain_Temp_Ratio', 'Temp_Range', 'Wind_Range']
    weather_df[cols_to_round] = weather_df[cols_to_round].round(2)

    # -------------------------------------------------------------------
    # BƯỚC 3: XUẤT FILE MỚI
    # -------------------------------------------------------------------
    output_filename = 'Bangladesh_weather_data_procces.csv'
    weather_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    
    print(f"\nHOÀN TẤT! Đã tạo ra file '{output_filename}' thành công.")
    print("Các cột mới được thêm vào:")
    print(" - Temp_Range")
    print(" - Wind_Range")
    print(" - Rain_Temp_Ratio")
    print(" - Extreme_Heat_Risk")
    print(" - Is_Extreme_Heat")

if __name__ == "__main__":
    process_weather_data()