import pandas as pd
from geopy.geocoders import Nominatim
import time


df = pd.read_csv("data_season.csv")
df.columns = df.columns.str.strip()

cols = ['Year', 'Location', 'Season']
df = df[cols]
locations = df['Location'].dropna().unique().tolist()

geolocator = Nominatim(user_agent="ndvi_project")

location_dict = {}

for loc in locations:
    geo = geolocator.geocode(loc)
    if geo:
        location_dict[loc] = (geo.latitude, geo.longitude)
    time.sleep(1)
print(location_dict)  
