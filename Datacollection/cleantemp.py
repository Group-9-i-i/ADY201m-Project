import pandas as pd
import numpy as np
import os

# --- CẤU HÌNH ---
crop_file = 'data_enriched_npk.csv'
weather_file = 'Karnataka_Weather_Wind_2004_2025_Full.csv'
ndvi_file = 'data_season_with_ndvi_fixed.csv'
output_file = 'Cleaned_Master_Dataset_For_Training.csv'

base_dir = os.path.dirname(os.path.abspath(__file__))

# =========================
# LOAD DATA
# =========================
print("⏳ Đang đọc dữ liệu...")
df_crop = pd.read_csv(os.path.join(base_dir, crop_file))
df_weather = pd.read_csv(os.path.join(base_dir, weather_file))
df_ndvi = pd.read_csv(os.path.join(base_dir, ndvi_file))

# =========================
# WEATHER → SEASONAL AGG
# =========================
print("⚙️ Xử lý weather theo mùa vụ...")

df_weather['Date'] = pd.to_datetime(df_weather['Date'])
df_weather['Year'] = df_weather['Date'].dt.year
df_weather['Month'] = df_weather['Date'].dt.month
df_weather['District'] = df_weather['District'].str.strip().str.title()

# Map month → season (chuẩn Karnataka)
def get_season(m):
    if m in [6,7,8,9]:
        return 'Kharif'
    elif m in [10,11,12,1,2]:
        return 'Rabi'
    else:
        return 'Summer'

df_weather['Season'] = df_weather['Month'].apply(get_season)

# Gộp theo District + Year + Season
weather_agg = df_weather.groupby(
    ['District','Year','Season']
).agg({
    'Temp_Avg_C': 'mean',
    'Precipitation_mm': 'sum',
    'Wind_Speed_10m_kmh': 'mean'
}).reset_index()

weather_agg.rename(columns={
    'Temp_Avg_C': 'Temperature',
    'Precipitation_mm': 'Rainfall',
    'Wind_Speed_10m_kmh': 'Wind_Speed'
}, inplace=True)

# =========================
# CROP CLEAN
# =========================
if 'Location' in df_crop.columns:
    df_crop.rename(columns={'Location': 'District'}, inplace=True)

df_crop['District'] = df_crop['District'].str.strip().str.title()
df_crop['Season'] = df_crop['Season'].astype(str).str.strip().str.title()

district_map = {
    'Mangalore': 'Dakshina Kannada',
    'Mysuru': 'Mysore',
    'Bengaluru': 'Bangalore Urban',
    'Gulbarga': 'Kalaburagi',
    'Belgaum': 'Belagavi',
    'Bijapur': 'Vijayapura',
    'Shimoga': 'Shivamogga',
    'Chikmagalur': 'Chikkamagaluru'
}
df_crop['District'] = df_crop['District'].replace(district_map)

# Drop weather cũ
for col in ['Rainfall', 'Temperature', 'Wind Speed']:
    if col in df_crop.columns:
        df_crop = df_crop.drop(columns=[col])

# =========================
# NDVI CLEAN
# =========================
df_ndvi = df_ndvi[['Year','District','NDVI']].copy()
df_ndvi['District'] = df_ndvi['District'].str.strip().str.title()
df_ndvi = df_ndvi.drop_duplicates(['Year','District'])

# =========================
# MERGE — SEASONAL
# =========================
print("🔗 Merge theo District + Year + Season")

df_master = pd.merge(
    df_crop,
    weather_agg,
    on=['District','Year','Season'],
    how='left'
)

df_master = pd.merge(
    df_master,
    df_ndvi,
    on=['District','Year'],
    how='left'
)

# =========================
# DATA CLEANING
# =========================

if 'yeilds' in df_master.columns:
    df_master.rename(columns={'yeilds': 'Yield'}, inplace=True)

if 'price' in df_master.columns:
    df_master.rename(columns={'price': 'Price'}, inplace=True)

if 'Soil type' in df_master.columns:
    df_master.rename(columns={'Soil type': 'Soil_Type'}, inplace=True)

target_cols = [
    'Year','District','Area','Rainfall','Temperature','Humidity',
    'Soil_Type','Irrigation','Crops','Season','NDVI',
    'Wind_Speed','Yield','Price'
]

for col in target_cols:
    if col not in df_master.columns:
        df_master[col] = np.nan

df_clean = df_master[target_cols].copy()

# Drop duplicates
df_clean = df_clean.drop_duplicates()

# Fill numeric median
num_cols = [
    'Area','Rainfall','Temperature','Humidity',
    'NDVI','Wind_Speed','Yield','Price'
]

for col in num_cols:
    df_clean[col] = df_clean[col].fillna(df_clean[col].median())

# Fill categorical mode
cat_cols = ['Soil_Type','Irrigation','Crops','Season']

for col in cat_cols:
    mode = df_clean[col].mode()
    df_clean[col] = df_clean[col].fillna(mode[0] if not mode.empty else "Unknown")

# Normalize text
for col in ['District','Soil_Type','Irrigation','Crops','Season']:
    df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

# Outlier filters
df_clean = df_clean[(df_clean['Yield'] > 0) & (df_clean['Area'] > 0)]
df_clean = df_clean[df_clean['Rainfall'] < 20000]
# =========================
# FEATURE ENGINEERING
# =========================

df_clean['RainTemp_Interaction'] = (
    df_clean['Rainfall'] * df_clean['Temperature']
)
# ======================================
# FEATURE ENGINEERING
# ======================================

print("🔧 Feature engineering...")

# Interaction feature
df_clean['RainTemp_Interaction'] = (
    df_clean['Rainfall'] * df_clean['Temperature']
)

# ======================================
# ENCODING CATEGORICAL
# ======================================

print("🔤 Encoding categorical columns...")

cat_cols = ['District', 'Season', 'Irrigation', 'Soil_Type', 'Crops']

# In số lượng category để quyết định encode
for c in cat_cols:
    print(f"{c}: {df_clean[c].nunique()} unique")

# -------- One-Hot cho cột ít category --------
onehot_cols = []

for c in ['District','Season','Irrigation','Soil_Type']:
    if df_clean[c].nunique() <= 20:
        onehot_cols.append(c)

print("One-hot columns:", onehot_cols)

df_encoded = pd.get_dummies(
    df_clean,
    columns=onehot_cols,
    drop_first=True
)

# -------- Encode Crops tùy cardinality --------
if df_clean['Crops'].nunique() <= 20:
    print("🌾 Crops → One-Hot")
    df_encoded = pd.get_dummies(
        df_encoded,
        columns=['Crops'],
        drop_first=True
    )
else:
    print("🌾 Crops → Label Encoding")
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    df_encoded['Crops_enc'] = le.fit_transform(df_clean['Crops'])
    df_encoded = df_encoded.drop(columns=['Crops'])

# ======================================
# FINAL CHECK
# ======================================

print("Shape before encode:", df_clean.shape)
print("Shape after encode :", df_encoded.shape)

print("\nColumns preview:")
print(df_encoded.columns[:20])

# ======================================
# SAVE TRAINING DATASET
# ======================================

output_encoded = "Training_Dataset_Encoded.csv"

out_path = os.path.join(base_dir, output_encoded)
df_encoded.to_csv(out_path, index=False)

print("✅ Training dataset saved:", out_path)
print(df_encoded.head())



# =========================
# SAVE
# =========================
out_path = os.path.join(base_dir, output_file)
df_clean.to_csv(out_path, index=False)

print("✅ DONE:", out_path)
print(df_clean.head())
