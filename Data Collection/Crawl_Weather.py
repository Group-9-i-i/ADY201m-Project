import requests
import pandas as pd
import numpy as np
from datetime import datetime
from time import sleep

COORDS_FILE = "Bangladesh_districts_coords_data.csv"
MAIN_DATA_FILE = 'Bangladesh_main_data.csv'
OUTPUT_FILE = 'Bangladesh_weather_data_procces.csv'
YEAR = 2022

def get_season(month):
    if month in [11, 12, 1, 2]: return "Rabi"
    if month in [3, 4, 5, 6]: return "Kharif 1"
    if month in [7, 8, 9, 10]: return "Kharif 2"
    return None

def fetch_nasa(lat, lon):
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        "?parameters=PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,WS2M,WS2M_MAX"
        "&community=AG"
        f"&latitude={lat}&longitude={lon}"
        f"&start={YEAR}0101&end={YEAR}1231&format=JSON"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]["parameter"]

def nasa_to_df(data):
    rows = [{
        "Date": datetime.strptime(d, "%Y%m%d"),
        "Rainfall": data["PRECTOTCORR"][d],
        "Temp_Mean": data["T2M"][d],
        "Temp_Max": data["T2M_MAX"][d],
        "Temp_Min": data["T2M_MIN"][d],
        "Wind_Mean": data["WS2M"][d],
        "Wind_Max": data["WS2M_MAX"][d],
    } for d in data["T2M"]]
    
    df = pd.DataFrame(rows)
    df["Month"] = df["Date"].dt.month
    df["Season"] = df["Month"].apply(get_season)
    return df

def aggregate_season(df, district):
    out = df.groupby("Season").agg(
        Rainfall=("Rainfall", "sum"),
        Temp_Mean=("Temp_Mean", "mean"),
        Temp_Max=("Temp_Max", "max"),
        Temp_Min=("Temp_Min", "min"),
        Heat_Stress_Days=("Temp_Max", lambda x: (x > 35).sum()),
        Wind_Mean=("Wind_Mean", "mean"),
        Wind_Max=("Wind_Max", "max")
    ).reset_index()
    out["District"] = district
    out["Year"] = YEAR
    return out

def crawl_data():
    try:
        coords = pd.read_csv(COORDS_FILE)
    except FileNotFoundError:
        return None

    all_data = []
    for _, row in coords.iterrows():
        try:
            raw = fetch_nasa(row["lat"], row["lon"])
            daily = nasa_to_df(raw)
            seasonal = aggregate_season(daily, row["district"])
            all_data.append(seasonal)
        except Exception:
            pass
        sleep(1)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

def clean_data(df):
    df['District'] = df['District'].astype(str).str.strip().str.title()
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().sum() > 0:
            df[col] = df.groupby('District')[col].transform(lambda x: x.fillna(x.median()))
    return df

def feature_engineering(df):
    df['Rain_Temp_Ratio'] = (df['Rainfall'] / (df['Temp_Mean'] + 0.001)).round(2)
    return df

def merge_and_save(df):
    try:
        main_df = pd.read_csv(MAIN_DATA_FILE)
        valid_districts = main_df['District'].dropna().unique()
        missing = set(df['District']) - set(valid_districts)
    except FileNotFoundError:
        pass
        
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    print(f"Bắt đầu quy trình xử lý Weather...")
    df_raw = crawl_data()
    if df_raw is not None and not df_raw.empty:
        df_clean = clean_data(df_raw)
        df_final = feature_engineering(df_clean)
        merge_and_save(df_final)
        print(f"Đã lưu kết quả tại {OUTPUT_FILE}")
    else:
        print("Không có dữ liệu.")