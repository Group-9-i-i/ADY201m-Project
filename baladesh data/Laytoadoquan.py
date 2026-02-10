import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from rapidfuzz import process

# ======================
# load csv
# ======================
df = pd.read_csv("kk.csv")

# ======================
# danh sách chuẩn
# ======================
BD_DISTRICTS = [
"Bagerhat","Bandarban","Barguna","Barisal","Bhola","Bogura","Brahmanbaria",
"Chandpur","Chattogram","Chuadanga","Cox's Bazar","Cumilla","Dhaka","Dinajpur",
"Faridpur","Feni","Gaibandha","Gazipur","Gopalganj","Habiganj","Jamalpur",
"Jashore","Jhalokati","Jhenaidah","Joypurhat","Khagrachhari","Khulna","Kishoreganj",
"Kurigram","Kushtia","Lakshmipur","Lalmonirhat","Madaripur","Magura","Manikganj",
"Meherpur","Moulvibazar","Munshiganj","Mymensingh","Naogaon","Narail","Narayanganj",
"Narsingdi","Natore","Netrokona","Nilphamari","Noakhali","Pabna","Panchagarh",
"Patuakhali","Pirojpur","Rajbari","Rajshahi","Rangamati","Rangpur","Satkhira",
"Shariatpur","Sherpur","Sirajganj","Sunamganj","Sylhet","Tangail","Thakurgaon"
]

# ======================
# fuzzy fix
# ======================
def fix_name(name):
    match, score, _ = process.extractOne(name, BD_DISTRICTS)
    return match if score > 85 else name

df["district_clean"] = df["District"].apply(fix_name)

# ======================
# geocoder config chuẩn
# ======================
geolocator = Nominatim(
    user_agent="bd_geo_project_student",
    timeout=10
)

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.2,
    max_retries=3,
    error_wait_seconds=2
)

# ======================
# query function chuẩn
# ======================
def get_coords(name):
    query = f"{name}, Bangladesh"
    loc = geocode(query)

    if loc:
        return loc.latitude, loc.longitude
    return None, None

# ======================
# run
# ======================
df[["lat","lon"]] = df["district_clean"].apply(
    lambda x: pd.Series(get_coords(x))
)

# ======================
# save
# ======================
out = df[["district_clean","lat","lon"]]
out.columns = ["district","lat","lon"]
out.to_csv("bd_district_coords.csv", index=False)

print("\n✅ DONE — stable version")
