import requests
import pandas as pd
from datetime import datetime
from time import sleep
import numpy as np

def get_season(month):
    if month in [11, 12, 1, 2]:
        return "Rabi"
    elif month in [3, 4, 5, 6]:
        return "Kharif 1"
    elif month in [7, 8, 9, 10]:
        return "Kharif 2"
    else:
        return None

def fetch_nasa(lat, lon):
    # Cập nhật: Thêm WS2M, WS2M_MAX, WS2M_MIN vào danh sách parameters
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        "?parameters=PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,WS2M,WS2M_MAX,WS2M_MIN"
        "&community=AG"
        f"&latitude={lat}"
        f"&longitude={lon}"
        "&start=20220101"
        "&end=20221231"
        "&format=JSON"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]["parameter"]

def nasa_to_df(data):
    rows = []
    # Dùng list các ngày từ T2M để duyệt qua tất cả các tham số
    for d in data["T2M"]:
        rows.append({
            "Date": datetime.strptime(d, "%Y%m%d"),
            "Rainfall": data["PRECTOTCORR"][d],
            "Temp_Mean": data["T2M"][d],
            "Temp_Max": data["T2M_MAX"][d],
            "Temp_Min": data["T2M_MIN"][d],
            # Cập nhật: Bóc tách thêm dữ liệu gió từ JSON
            "Wind_Mean": data["WS2M"][d],
            "Wind_Max": data["WS2M_MAX"][d],
            "Wind_Min": data["WS2M_MIN"][d],
        })
    df = pd.DataFrame(rows)
    df["Month"] = df["Date"].dt.month
    df["Season"] = df["Month"].apply(get_season)
    return df

def aggregate_season(df, district):
    out = (
        df.groupby("Season")
        .agg(
            Rainfall=("Rainfall", "sum"),
            Temp_Mean=("Temp_Mean", "mean"),
            Temp_Max=("Temp_Max", "max"),
            Temp_Min=("Temp_Min", "min"),
            Heat_Stress_Days=("Temp_Max", lambda x: (x > 35).sum()),
            # Cập nhật: Thêm luật tổng hợp cho các cột gió (trung bình, lớn nhất, nhỏ nhất) theo mùa
            Wind_Mean=("Wind_Mean", "mean"),
            Wind_Max=("Wind_Max", "max"),
            Wind_Min=("Wind_Min", "min")
        )
        .reset_index()
    )
    out["District"] = district
    out["Year"] = 2022
    return out

# --- VÒNG LẶP CHÍNH (Giữ nguyên) ---
coords = pd.read_csv("Bangladesh_districts_coords_data.csv")
all_data = []

for _, row in coords.iterrows():
    name = row["district"]
    lat = row["lat"]
    lon = row["lon"]

    print(f"Fetching weather for {name}")
    try:
        raw = fetch_nasa(lat, lon)
        daily = nasa_to_df(raw)
        seasonal = aggregate_season(daily, name)
        all_data.append(seasonal)
    except Exception as e:
        print(f"Failed {name}: {e}")

    sleep(1)

final_df = pd.concat(all_data, ignore_index=True)

# --- XỬ LÝ LỖI (DATA CLEANING) BÊN CRAWL ---
print("Đang xử lý dữ liệu lỗi (bên crawl)...")
final_df['District'] = final_df['District'].astype(str).str.strip().str.title()
for col in final_df.select_dtypes(include=[np.number]).columns:
    if final_df[col].isna().sum() > 0:
        final_df[col] = final_df.groupby('District')[col].transform(lambda x: x.fillna(x.median()))

print("DONE FETCHING")

def process_weather_data(weather_df):
    print("1. Đang đọc dữ liệu Main...")
    try:
        main_df = pd.read_csv('Bangladesh_main_data.csv')
    except FileNotFoundError as e:
        print(f"Lỗi đọc file: {e}")
        return

    # Tên District đã được chuẩn hóa ở bước crawl
    valid_districts = main_df['District'].dropna().unique()
    missing_in_main = set(weather_df['District']) - set(valid_districts)
    if missing_in_main:
        print(f"Cảnh báo: Có các huyện không khớp với file main: {missing_in_main}")
    else:
        print(" -> 100% tên District đã khớp với file Bangladesh_main_data.csv!")

    print("3. Tính toán các chỉ số dự đoán năng suất cây trồng...")
    weather_df['Temp_Range'] = weather_df['Temp_Max'] - weather_df['Temp_Min']
    weather_df['Wind_Range'] = weather_df['Wind_Max'] - weather_df['Wind_Min']
    weather_df['Rain_Temp_Ratio'] = weather_df['Rainfall'] / (weather_df['Temp_Mean'] + 0.001)
    
    conditions = [
        (weather_df['Heat_Stress_Days'] == 0),
        (weather_df['Heat_Stress_Days'] > 0) & (weather_df['Heat_Stress_Days'] <= 15),
        (weather_df['Heat_Stress_Days'] > 15)
    ]
    choices = ['Low Risk', 'Moderate Risk', 'High Risk']
    weather_df['Extreme_Heat_Risk'] = np.select(conditions, choices, default='Unknown')

    weather_df['Is_Extreme_Heat'] = np.where(weather_df['Temp_Max'] > 38, 1, 0)

    cols_to_round = ['Rain_Temp_Ratio', 'Temp_Range', 'Wind_Range']
    weather_df[cols_to_round] = weather_df[cols_to_round].round(2)

    output_filename = 'Bangladesh_weather_data_procces.csv'
    weather_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"\nHOÀN TẤT! Đã tạo ra file '{output_filename}' thành công.")

process_weather_data(final_df)