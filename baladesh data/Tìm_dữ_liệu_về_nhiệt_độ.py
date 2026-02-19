import requests
import pandas as pd
from datetime import datetime
from time import sleep
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
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        "?parameters=PRECTOTCORR,T2M,T2M_MAX,T2M_MIN"
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
    for d in data["T2M"]:
        rows.append({
            "Date": datetime.strptime(d, "%Y%m%d"),
            "Rainfall": data["PRECTOTCORR"][d],
            "Temp_Mean": data["T2M"][d],
            "Temp_Max": data["T2M_MAX"][d],
            "Temp_Min": data["T2M_MIN"][d],
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
            Heat_Stress_Days=("Temp_Max", lambda x: (x > 35).sum())
        )
        .reset_index()
    )
    out["District"] = district
    out["Year"] = 2022
    return out
coords = pd.read_csv("bangladesh_64_districts_coords.csv")
all_data = []

for _, row in coords.iterrows():
    name = row["district"]
    lat = row["lat"]
    lon = row["lon"]

    print(f"☁️ Fetching weather for {name}")
    try:
        raw = fetch_nasa(lat, lon)
        daily = nasa_to_df(raw)
        seasonal = aggregate_season(daily, name)
        all_data.append(seasonal)
    except Exception as e:
        print(f"❌ Failed {name}: {e}")

    sleep(1)
final_df = pd.concat(all_data, ignore_index=True)
final_df.to_csv("bangladesh_weather_2022_by_season.csv", index=False)

print("✅ DONE")