import pandas as pd
from geopy.geocoders import Nominatim #thư viện lấy tọa độ của openstreetmap
from geopy.extra.rate_limiter import RateLimiter #thư viện delay tốc độ quét tọa độ của openstreetmap

# 1. Danh sách 64 quận chuẩn từ SQL của bạn
raw_districts = """
Bagerhat, Bandarban, Barguna, Barishal, Bhola, Bogura, Brahmanbaria, 
Chandpur, Chapai Nawabganj, Chattogram, Chuadanga, CoxsBazar, Cumilla, 
Dhaka, Dinajpur, Faridpur, Feni, Gaibandha, Gazipur, Gopalganj, 
Habiganj, Jamalpur, Jashore, Jhallokati, Jhenaidah, Joypurhat, 
Khagrachari, Khulna, Kishoreganj, Kurigram, Kushtia, Lakshmipur, 
Lalmonirhat, Madaripur, Magura, Manikganj, Meherpur, Moulvibazar, 
Munshiganj, Mymensingh, Naogaon, Narail, Narayanganj, Narsingdi, 
Natore, Netrokona, Nilphamari, Noakhali, Pabna, Panchagar, 
Patuakhali, Pirojpur, Rajbari, Rajshahi, Rangamati, Rangpur, 
Satkhira, Shariatpur, Sherpur, Sirajganj, Sunamganj, Sylhet, 
Tangail, Thakurgaon
"""

# Chuyển chuỗi trên thành list và làm sạch khoảng trắng
DISTRICT_LIST = [d.strip() for d in raw_districts.replace("\n", "").split(",")]

# 2. Cấu hình Geocoder
geolocator = Nominatim(user_agent="tim_toa _do_Bangladesh", timeout=10) # gửi request đến OpenstreetMap để lấy tọa độ
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=2) # điều tốc độ gửi request tránh bị đánh dấu IP spam

def get_coordinates(district_name):
    # Xử lý các tên viết dính để Nominatim dễ tìm hơn
    search_name = district_name
    if district_name == "CoxsBazar": search_name = "Cox's Bazar"
    if district_name == "Panchagar": search_name = "Panchagarh"
    
    query = f"{search_name}, Bangladesh"
    try:
        loc = geocode(query)
        if loc:
            return loc.latitude, loc.longitude
    except:
        pass
    return None, None

# 3. Chạy và tạo file kết quả
print(f"Đang lấy tọa độ cho {len(DISTRICT_LIST)} quận.")

data = []
for dist in DISTRICT_LIST:
    lat, lon = get_coordinates(dist)
    data.append({"district": dist, "lat": lat, "lon": lon})
    print(f"{dist}: {lat}, {lon}")

# 4. Lưu file 64 dòng duy nhất
df_final = pd.DataFrame(data)
df_final.to_csv("bangladesh_64_districts_coords.csv", index=False)

print("\n--- HOÀN THÀNH ---")
print('YASSSSSSS!')