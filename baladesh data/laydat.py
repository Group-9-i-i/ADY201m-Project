import requests
import pandas as pd
from time import sleep
SOIL_LAYERS = {
    "phh2o": "pH",
    "soc": "Organic_Carbon",
    "nitrogen": "Nitrogen",
    "clay": "Clay",
    "sand": "Sand",
    "silt": "Silt",
    "bdod": "Bulk_Density"
}

DEPTH = "0-30cm"
def fetch_soilgrids(lat, lon):
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lat": lat,
        "lon": lon,
        "depth": DEPTH,
        "property": list(SOIL_LAYERS.keys())
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]["layers"]
def parse_soil(layers):
    out = {}
    for layer in layers:
        name = layer["name"]
        value = layer["depths"][0]["values"]["mean"]
        out[SOIL_LAYERS[name]] = value
    return out
def collect_soil_data(district_csv):
    districts = pd.read_csv(district_csv)
    records = []

    for _, row in districts.iterrows():
        name = row["District"]
        lat = row["Latitude"]
        lon = row["Longitude"]

        print(f"🌍 Fetching soil for {name}")
        try:
            layers = fetch_soilgrids(lat, lon)
            soil = parse_soil(layers)
            soil["District"] = name
            records.append(soil)
        except Exception as e:
            print(f"❌ Failed {name}: {e}")

        sleep(1)

    return pd.DataFrame(records)
if __name__ == "__main__":
    soil_df = collect_soil_data("bangladesh_district_coords.csv")
    soil_df.to_csv("bangladesh_soil_features.csv", index=False)
    print("✅ Saved bangladesh_soil_features.csv")
