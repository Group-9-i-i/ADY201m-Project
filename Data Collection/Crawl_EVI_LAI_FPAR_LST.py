import ee
import requests
PROJECT_ID = "gen-lang-client-0272496285"

try:
    ee.Initialize(project=PROJECT_ID)
    print("Connected to GEE.")
except Exception:
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)
    print('Lỗi xác thực đang tải lại')

bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(
    ee.Filter.eq("ADM0_NAME", "Bangladesh")
)

col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(["EVI"]) # chỉ số thực vật tăng cường 
col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H") #chỉ số diện tích lá và chỉ số bức xạ quang hợp được hấp thụ
col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(["LST_Day_1km"]) # chỉ số nhiệt độ bề mặt đất vào ban ngày
col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(["ssm"]) # độ ẩm dất bề mặt
def get_safe_band(collection, band_name, scale, new_name, start_date, end_date, valid_max=None):
    filtered = collection.select(band_name).filterDate(start_date, end_date)

    mean_img = filtered.mean()
    if valid_max is not None:
        mean_img = mean_img.updateMask(mean_img.lt(valid_max))
    mean_img = mean_img.multiply(scale).rename(new_name)

    safe_img = ee.Image(
        ee.Algorithms.If(
            filtered.size().gt(0),
            mean_img,
            ee.Image.constant(-9999).rename(new_name)
        )
    )

    return safe_img.unmask(-9999)


def process_one_month(month_offset):
    base_year = 2022
    base_month = 1
    month_index = (base_month - 1) + month_offset
    target_year = base_year + (month_index // 12)
    target_month = (month_index % 12) + 1

    start_date = ee.Date.fromYMD(target_year, target_month, 1)
    end_date = start_date.advance(1, "month")

    img_evi = get_safe_band(col_evi, "EVI", 0.0001, "EVI", start_date, end_date)
    img_lai = get_safe_band(col_lai_fpar, "Lai_500m", 0.1, "LAI", start_date, end_date)
    img_fpar = get_safe_band(col_lai_fpar,"Fpar_500m",0.01,"FPAR",start_date,end_date,valid_max=200)
    img_lst = get_safe_band(col_lst, "LST_Day_1km", 0.02, "LST_Kelvin", start_date, end_date)
    img_sm = get_safe_band(col_soil, "ssm", 1.0, "Soil_Moisture_mm", start_date, end_date)

    final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])

    reducer = ee.Reducer.mean().combine(reducer2=ee.Reducer.count(),sharedInputs=True)
    stats = final_image.reduceRegions(collection=bangladesh_districts,reducer=reducer,cale=500)
    def add_time_props(feature):
        return feature.set({
            "Month": start_date.get("month"),
            "Year": start_date.get("year")
        })

    return stats.map(add_time_props)

print("Processing monthly data...")
all_months_data = []
for i in range(12):
    month_data = process_one_month(i)
    all_months_data.append(month_data)
full_data = ee.FeatureCollection(all_months_data).flatten()

print("Generating download link...")

download_url = full_data.getDownloadURL(
    filetype="csv",
    selectors=[
        "ADM2_NAME",
        "Month",
        "Year",
        "EVI_mean",
        "LAI_mean",
        "FPAR_mean",
        "LST_Kelvin_mean",
        "Soil_Moisture_mm_mean",
    ]
)

response = requests.get(download_url)
if response.status_code == 200:
    filename = "Bangladesh_EVI_LAI_FPAR_LST_data.csv"
    with open(filename, "wb") as f:
        f.write(response.content)
    print("File saved:", filename)
else:
    print("Download failed:", response.status_code)