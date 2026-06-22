import pandas as pd
import numpy as np
import os

# --- CẤU HÌNH: ĐẢM BẢO TÊN FILE ĐÚNG NHƯ BẠN ĐÃ CÓ ---
crop_file = 'data_enriched_npk.csv'
weather_file = 'Karnataka_Weather_Wind_2004_2025_Full.csv'
ndvi_file = 'data_season_with_ndvi_fixed.csv'
output_file = 'Cleaned_Master_Dataset_For_Training.csv'

# Lấy đường dẫn hiện tại (để tránh lỗi File Not Found)
base_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Load Data
print("⏳ Đang đọc dữ liệu...")
try:
    df_crop = pd.read_csv(os.path.join(base_dir, crop_file))
    df_weather = pd.read_csv(os.path.join(base_dir, weather_file))
    df_ndvi = pd.read_csv(os.path.join(base_dir, ndvi_file))
except FileNotFoundError:
    print("❌ Lỗi: Không tìm thấy file csv. Hãy đảm bảo chúng nằm cùng thư mục với file code.")
    exit()

# ==============================================================================
# GIAI ĐOẠN 1: CHUẨN BỊ & GHÉP DỮ LIỆU
# ==============================================================================

# --- A. Xử lý Weather (Gộp từ Ngày -> Năm) ---
print("⚙️ Đang xử lý dữ liệu thời tiết...")
df_weather['Date'] = pd.to_datetime(df_weather['Date'])
df_weather['Year'] = df_weather['Date'].dt.year
df_weather['District'] = df_weather['District'].str.strip().str.title()

weather_agg = df_weather.groupby(['District', 'Year']).agg({
    'Temp_Avg_C': 'mean',
    'Precipitation_mm': 'sum',
    'Wind_Speed_10m_kmh': 'mean'
}).reset_index()

weather_agg.rename(columns={
    'Temp_Avg_C': 'Temperature',
    'Precipitation_mm': 'Rainfall',
    'Wind_Speed_10m_kmh': 'Wind_Speed'
}, inplace=True)

# --- B. Xử lý Crop (Dataset Gốc) ---
if 'Location' in df_crop.columns:
    df_crop.rename(columns={'Location': 'District'}, inplace=True)
df_crop['District'] = df_crop['District'].str.strip().str.title()

# Map tên quận cho khớp với Weather (Dakshina Kannada vs Mangalore)
district_map = {
    'Mangalore': 'Dakshina Kannada', 'Mysuru': 'Mysore',
    'Bengaluru': 'Bangalore Urban', 'Gulbarga': 'Kalaburagi',
    'Belgaum': 'Belagavi', 'Bijapur': 'Vijayapura',
    'Shimoga': 'Shivamogga', 'Chikmagalur': 'Chikkamagaluru'
}
df_crop['District'] = df_crop['District'].replace(district_map)

# ⚠️ QUAN TRỌNG: Xóa cột thời tiết cũ trong file crop để dùng cột mới xịn hơn từ file weather
for col in ['Rainfall', 'Temperature', 'Wind Speed']:
    if col in df_crop.columns:
        df_crop = df_crop.drop(columns=[col])

# --- C. Xử lý NDVI ---
df_ndvi = df_ndvi[['Year', 'District', 'NDVI']].copy()
df_ndvi['District'] = df_ndvi['District'].str.strip().str.title()
df_ndvi = df_ndvi.drop_duplicates(subset=['Year', 'District'])

# --- D. Merge (Hợp nhất) ---
print("🔗 Đang hợp nhất dữ liệu...")
df_master = pd.merge(df_crop, weather_agg, on=['District', 'Year'], how='left')
df_master = pd.merge(df_master, df_ndvi, on=['District', 'Year'], how='left')

# ==============================================================================
# GIAI ĐOẠN 2: QUY TRÌNH 6 BƯỚC LÀM SẠCH (DATA CLEANING)
# ==============================================================================

# --- Bước 1: Lọc & Đổi tên cột ---
if 'yeilds' in df_master.columns: df_master.rename(columns={'yeilds': 'Yield'}, inplace=True)
if 'price' in df_master.columns: df_master.rename(columns={'price': 'Price'}, inplace=True)
if 'Soil type' in df_master.columns: df_master.rename(columns={'Soil type': 'Soil_Type'}, inplace=True)

target_cols = ['Year', 'District', 'Area', 'Rainfall', 'Temperature', 'Humidity', 
               'Soil_Type', 'Irrigation', 'Crops', 'Season', 'NDVI', 'Wind_Speed', 'Yield', 'Price']

# Tạo cột nếu thiếu (để tránh lỗi)
for col in target_cols:
    if col not in df_master.columns: df_master[col] = np.nan

df_clean = df_master[target_cols].copy()

# --- Bước 2: Xử lý Trùng lặp ---
df_clean = df_clean.drop_duplicates()

# --- Bước 3: Điền dữ liệu thiếu ---
print("🧹 Đang điền dữ liệu thiếu...")
# Cột số: Điền Median
for col in ['Area', 'Rainfall', 'Temperature', 'Humidity', 'NDVI', 'Wind_Speed', 'Yield', 'Price']:
    if df_clean[col].isnull().sum() > 0:
        df_clean[col] = df_clean[col].fillna(df_clean[col].median())
# Cột chữ: Điền Mode
for col in ['Soil_Type', 'Irrigation', 'Crops', 'Season']:
    if df_clean[col].isnull().sum() > 0:
        mode_val = df_clean[col].mode()[0] if not df_clean[col].mode().empty else "Unknown"
        df_clean[col] = df_clean[col].fillna(mode_val)

# --- Bước 4 & 5: Chuẩn hóa & Nhất quán ---
for col in ['District', 'Soil_Type', 'Irrigation', 'Crops', 'Season']:
    df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

df_clean['District'] = df_clean['District'].replace({'Karnartakaka': 'Karnataka'})

# --- Bước 6: Khử nhiễu (Outliers) ---
df_clean = df_clean[(df_clean['Yield'] > 0) & (df_clean['Area'] > 0)]
# Lọc mưa quá lớn (Logic: hiếm nơi nào > 20,000mm trừ Cherrapunji)
if 'Rainfall' in df_clean.columns:
    df_clean = df_clean[df_clean['Rainfall'] < 20000]

# --- LƯU FILE ---
df_clean.to_csv(os.path.join(base_dir, output_file), index=False)
print("-" * 40)
print(f"✅ THÀNH CÔNG! File sạch đã được lưu tại:\n{os.path.join(base_dir, output_file)}")
print("-" * 40)
print(df_clean.head())