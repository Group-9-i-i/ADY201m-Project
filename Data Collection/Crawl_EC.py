import ee # Xử dụng API của google earth
import time
import pandas as pd
import io # xử lý in / out của python

# 1. Khởi tạo
print('Hệ thống crawl EC bằng google map đang chạy...')
try:
    ee.Initialize(project='gen-lang-client-0272496285') 
    print("Đã kết nối thành công.")
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')
# hàm chia số lần gửi request lên google earth tránh bị limit
def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)) # công thức chia số lần gửi đảm bảo mỗi lần lệch nhau ít nhất

def run_bangladesh_super_split():
    # --- CẤU HÌNH ---
    FINAL_FILENAME = "Bangladesh_Salinity_Full_2022.csv"
    NUM_SPLIT = 12  
    all_dataframes = [] 
    
    print("Đang tải danh sách ranh giới hành chính...")
    # truy cập database để lấy danh giới hành chính
    base_fc = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    test_data = base_fc.limit(5).getInfo()
# In ra kết quả
    import pprint
    pprint.pprint(test_data)
    # Lấy danh sách tên huyện
    district_names = base_fc.aggregate_array('ADM2_NAME').getInfo()
    total_districts = len(district_names)
    
    # Chia nhỏ danh sách
    district_chunks = list(split_list(district_names, NUM_SPLIT)) 
    print(f"-> Tổng {total_districts} huyện. Đã chia thành {NUM_SPLIT} nhóm nhỏ (mỗi nhóm ~{len(district_chunks[0])} huyện).")

    # Hàm lọc mây
    def maskS2clouds(image):
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return image.updateMask(mask)

    # --- VÒNG LẶP ---
    for month in range(1, 13):
        print(f"\n==============================================")
        print(f" 📅 ĐANG XỬ LÝ THÁNG {month}/2022")
        print(f"==============================================")
        
        start_date = ee.Date.fromYMD(2022, month, 1)
        end_date = start_date.advance(1, 'month')

        s2_base = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) \
            .map(maskS2clouds) \
            .select(['B2', 'B4'])

        # Lặp qua từng nhóm nhỏ
        for i, chunk in enumerate(district_chunks):
            part_id = i + 1
            # Đo thời gian bắt đầu
            t_start = time.time()
            
            print(f"  ⏳ [Nhóm {part_id}/{NUM_SPLIT}] Đang gửi yêu cầu cho {len(chunk)} huyện... ", end="", flush=True)

            try:
                # 1. Chuẩn bị dữ liệu (Geometry)
                subset_fc = base_fc.filter(ee.Filter.inList('ADM2_NAME', chunk)) \
                    .map(lambda f: f.simplify(maxError=100)) # Làm nhẹ hình học
                
                s2_subset = s2_base.filterBounds(subset_fc)

                # 2. Tính toán
                def add_si(img):
                    si = img.expression(
                        'sqrt(b("B2") * b("B4"))',
                        {'B2': img.select('B2'), 'B4': img.select('B4')}
                    ).rename('Salinity_Index_Raw')
                    return img.addBands(si)

                monthly_mean = s2_subset.map(add_si).select('Salinity_Index_Raw').mean()
                
                stats = monthly_mean.reduceRegions(
                    collection=subset_fc,
                    reducer=ee.Reducer.mean(),
                    scale=100,      
                    tileScale=16
                )

                # 3. Format dữ liệu
                stats_final = stats.map(lambda f: f.set({
                    'Month': month, 
                    'Year': 2022,
                    'Salinity_Index_Raw': ee.Algorithms.If(f.get('mean'), f.get('mean'), -9999)
                }))

                export_cols = ['ADM2_NAME', 'ADM1_NAME', 'Month', 'Year', 'Salinity_Index_Raw']
                
                # 4. TẢI VỀ (getInfo - Khoảnh khắc quan trọng)
                # Dòng này sẽ mất vài giây để chạy
                data_json = stats_final.select(export_cols).getInfo()
                
                # Xử lý kết quả
                features = data_json['features']
                
                # Đo thời gian kết thúc
                elapsed = time.time() - t_start

                if len(features) > 0:
                    row_list = [f['properties'] for f in features]
                    df_part = pd.DataFrame(row_list)
                    
                    # Sắp xếp cột nếu cần
                    if not df_part.empty:
                         df_part = df_part[export_cols]
                    
                    all_dataframes.append(df_part)
                    print(f"✅ OK! (Mất {elapsed:.2f}s) - Lấy được {len(df_part)} dòng.")
                else:
                    print(f"⚠️ Rỗng (Mất {elapsed:.2f}s).")

            except Exception as e:
                print(f"\n❌ LỖI tại Nhóm {part_id}: {e}")
                print("   -> Đang nghỉ 5s rồi thử lại nhóm kế tiếp...")
                time.sleep(5)

        # Tổng kết tháng
        current_rows = sum(len(d) for d in all_dataframes)
        print(f"-> Kết thúc tháng {month}. Tổng dữ liệu hiện có: {current_rows} dòng.")

    # --- LƯU FILE ---
    print("\n------------------------------------------------")
    if all_dataframes:
        print("💾 Đang gộp và lưu file...")
        final_df = pd.concat(all_dataframes, ignore_index=True)
        final_df.to_csv(FINAL_FILENAME, index=False, encoding='utf-8-sig')
        print(f"🎉 HOÀN TẤT! File: {FINAL_FILENAME}")
        print(f"📊 Tổng số dòng: {len(final_df)}")
        print(final_df.head())
    else:
        print("❌ Không thu thập được dữ liệu nào.")

if __name__ == "__main__":
    run_bangladesh_super_split()