import pandas as pd 
from geopy.geocoders import Nominatim
from time import sleep

df = pd.read_csv('kk.csv')
df['District'] = df['District'].replace('Jhallokati', 'Jhalokati')

dislist = df['District'].unique().tolist()

geolocator = Nominatim(user_agent="bd_agri_project")

results = []

for d in dislist:
    print(f"📍 Locating {d}")
    try:
        location = geolocator.geocode(f"{d}, Bangladesh")
        if location:
            results.append({
                "District": d,
                "Latitude": location.latitude,
                "Longitude": location.longitude
            })
        else:
            print(f"⚠️ Not found: {d}")
    except Exception as e:
        print(f"❌ Error {d}: {e}")

    sleep(1)  
df_coords = pd.DataFrame(results)
df_coords.to_csv("bangladesh_district_coords.csv", index=False)

print("✅ Saved bangladesh_district_coords.csv")

