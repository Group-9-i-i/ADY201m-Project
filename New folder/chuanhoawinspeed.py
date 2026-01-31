import pandas as pd

# 1. Đọc dữ liệu
df_season = pd.read_csv('data_season_with_ndvi_fixed.csv')
df_weather = pd.read_csv('Karnataka_Weather_Wind_2004_2025_Full.csv')

# 2. Xử lý file Thời tiết (Aggregating Daily to Yearly)
# Chuyển cột Date sang dạng datetime để lấy năm
df_weather['Date'] = pd.to_datetime(df_weather['Date'])
df_weather['Year'] = df_weather['Date'].dt.year

# Tính trung bình tốc độ gió theo từng Quận và Năm
weather_yearly = df_weather.groupby(['District', 'Year'])['Wind_Speed_10m_kmh'].mean().reset_index()
weather_yearly.rename(columns={'Wind_Speed_10m_kmh': 'Avg_Yearly_Wind_Speed_kmh'}, inplace=True)

# 3. Xử lý tên Quận (District Mapping)
# Một số quận có tên khác nhau giữa 2 file, cần map lại để ghép được
district_mapping = {
    'Chikmangaluru': 'Chikkamagaluru',
    'Davangere': 'Davanagere',
    'Gulbarga': 'Kalaburagi',
    'Mangalore': 'Dakshina Kannada',
    'Bangalore': 'Bangalore Urban',
    'Madikeri': 'Kodagu' # Madikeri là thủ phủ của Kodagu
}

# Tạo cột District đã chuẩn hóa trong file season để dùng cho việc ghép
df_season['District_Mapped'] = df_season['District'].map(district_mapping).fillna(df_season['District'])

# Chuẩn hóa format text (xóa khoảng trắng thừa nếu có)
df_season['District_Mapped'] = df_season['District_Mapped'].astype(str).str.strip()
weather_yearly['District'] = weather_yearly['District'].astype(str).str.strip()

# 4. Ghép dữ liệu (Merge)
# Ghép file season với weather_yearly dựa trên Quận (đã map) và Năm
df_merged = pd.merge(
    df_season, 
    weather_yearly, 
    left_on=['District_Mapped', 'Year'], 
    right_on=['District', 'Year'], 
    how='left',
    suffixes=('', '_weather') # Xử lý nếu trùng tên cột
)

# Xóa các cột phụ không cần thiết sau khi ghép
df_merged.drop(columns=['District_Mapped', 'District_weather'], errors='ignore', inplace=True)

# 5. Lưu kết quả
output_file = 'data_season_with_wind_merged.csv'
df_merged.to_csv(output_file, index=False)

print(f"Đã ghép xong! Kết quả lưu tại: {output_file}")
print(df_merged[['Year', 'District', 'Avg_Yearly_Wind_Speed_kmh']].head())