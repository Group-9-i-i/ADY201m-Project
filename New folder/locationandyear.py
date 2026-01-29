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
def season_to_dates(year, season):
    if season.lower() == 'kharif':
        return f"{year}-06-01", f"{year}-10-31"
    elif season.lower() == 'rabi':
        return f"{year}-10-01", f"{year+1}-03-31"
    elif season.lower() == 'zaid':
        return f"{year}-03-01", f"{year}-06-30"
    else:
        return None, None
df['lat'] = df['Location'].map(lambda x: location_dict[x][0])
df['lon'] = df['Location'].map(lambda x: location_dict[x][1])
