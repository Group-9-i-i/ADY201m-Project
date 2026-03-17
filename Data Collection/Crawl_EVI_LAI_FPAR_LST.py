import ee
import requests

# ===============================
# 1. INITIALIZE
# ===============================
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("[OK] Connected to GEE.")
except:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

# ===============================
# 2. LOAD DATA
# ===============================
print("Setting up datasets...")

bangladesh_districts = ee.FeatureCollection("FAO/GAUL/2015/level2") \
    .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))

col_evi = ee.ImageCollection("MODIS/061/MOD13Q1").select(['EVI'])
col_lai_fpar = ee.ImageCollection("MODIS/061/MOD15A2H")
col_lst = ee.ImageCollection("MODIS/061/MOD11A2").select(['LST_Day_1km'])
col_soil = ee.ImageCollection("NASA_USDA/HSL/SMAP10KM_soil_moisture").select(['ssm'])


# ===============================
# 3. PROCESS FUNCTION
# ===============================
def process_safe_month(month_offset):

    start_date = ee.Date('2022-01-01').advance(month_offset, 'month')
    end_date = start_date.advance(1, 'month')

    # ---- Generic safe band loader ----
    def get_safe_band(collection, band_name, scale, new_name, valid_max=None):

        filtered = collection.select(band_name).filterDate(start_date, end_date)

        def compute():
            img = filtered.mean()

            # Mask invalid values if needed
            if valid_max:
                img = img.updateMask(img.lt(valid_max))

            img = img.multiply(scale).rename(new_name)
            return img

        img = ee.Image(
            ee.Algorithms.If(
                filtered.size().gt(0),
                compute(),
                ee.Image.constant(-9999).rename(new_name)
            )
        )

        return img.unmask(-9999)


    # ---- Apply bands ----
    img_evi = get_safe_band(col_evi, 'EVI', 0.0001, 'EVI')
    img_lai = get_safe_band(col_lai_fpar, 'Lai_500m', 0.1, 'LAI')
    
    # 🔥 FIX QUAN TRỌNG Ở ĐÂY
    img_fpar = get_safe_band(
        col_lai_fpar,
        'Fpar_500m',
        0.01,           # đúng scale
        'FPAR',
        valid_max=200   # bỏ pixel lỗi (>=249)
    )

    img_lst = get_safe_band(col_lst, 'LST_Day_1km', 0.02, 'LST_Kelvin')
    img_sm = get_safe_band(col_soil, 'ssm', 1.0, 'Soil_Moisture_mm')

    final_image = img_evi.addBands([img_lai, img_fpar, img_lst, img_sm])

    # ---- Reducer: mean + pixel count ----
    reducer = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.count(),
        sharedInputs=True
    )

    stats = final_image.reduceRegions(
        collection=bangladesh_districts,
        reducer=reducer,
        scale=500
    )

    return stats.map(lambda f: f.set({
        'Month': start_date.get('month'),
        'Year': start_date.get('year')
    }))


# ===============================
# 4. RUN PROCESS
# ===============================
print("Processing monthly data...")

months = ee.List.sequence(0, 11)
nested = ee.FeatureCollection(months.map(process_safe_month))
full_data = nested.flatten()

print("Generating download link...")

download_url = full_data.getDownloadURL(
    filetype='csv',
    selectors=[
        'ADM2_NAME',
        'ADM2_CODE',
        'Month',
        'Year',
        'EVI_mean',
        'LAI_mean',
        'FPAR_mean',
        'LST_Kelvin_mean',
        'Soil_Moisture_mm_mean',
        'FPAR_count'   # thêm count để debug
    ]
)

response = requests.get(download_url)

if response.status_code == 200:
    filename = 'Bangladesh_EVI_LAI_FPAR_LST_data.csv'
    with open(filename, 'wb') as f:
        f.write(response.content)
    print("[SUCCESS] File saved:", filename)
else:
    print("Download failed:", response.status_code)