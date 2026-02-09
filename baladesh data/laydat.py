import requests
import pandas as pd
from time import sleep
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SOIL_LAYERS = {
    "phh2o": "pH",
    "soc": "Organic_Carbon",
    "nitrogen": "Nitrogen",
    "clay": "Clay",
    "sand": "Sand",
    "silt": "Silt",
    "bdod": "Bulk_Density"
}

DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


def create_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_soilgrids(lat, lon, depth):
    params = {
        "lat": lat,
        "lon": lon,
        "depth": depth,
        "property": list(SOIL_LAYERS.keys())
    }

    try:
        r = session.get(BASE_URL, params=params, timeout=40)
        r.raise_for_status()
        return r.json()["properties"]["layers"]
    except Exception:
        return None


def parse_layers(layers):
    values = {}
    for layer in layers:
        name = layer["name"]
        try:
            values[name] = layer["depths"][0]["values"]["mean"]
        except Exception:
            values[name] = None
    return values


def collect_soil_data(district_csv):
    districts = pd.read_csv(district_csv)
    records = []

    for _, row in districts.iterrows():
        name = row["District"]
        lat = row["Latitude"]
        lon = row["Longitude"]

        print(f"🌍 {name}")
        depth_values = {k: [] for k in SOIL_LAYERS}

        for depth in DEPTHS:
            layers = fetch_soilgrids(lat, lon, depth)
            if layers is None:
                continue

            parsed = parse_layers(layers)
            for k, v in parsed.items():
                if v is not None:
                    depth_values[k].append(v)

            sleep(1)

        if all(len(v) == 0 for v in depth_values.values()):
            print(f"❌ No soil data for {name}")
            continue

        soil = {}
        for k, values in depth_values.items():
            soil[SOIL_LAYERS[k]] = sum(values) / len(values) if values else None

        soil["District"] = name
        records.append(soil)
        sleep(2)

    return pd.DataFrame(records)


# ===== MAIN =====
session = create_session()

if __name__ == "__main__":
    df = collect_soil_data("bangladesh_district_coords.csv")
    df.to_csv("bangladesh_soil_features_0_30cm.csv", index=False)
    print("✅ Saved bangladesh_soil_features_0_30cm.csv")
