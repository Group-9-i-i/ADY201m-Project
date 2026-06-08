import ee
import time
import pandas as pd
import io
import os

# 1. Khởi tạo
try:
    ee.Initialize(project='gen-lang-client-0272496285')
    print("Đã kết nối thành công.")
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project='gen-lang-client-0272496285')

def split_list(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def run_bangladesh_super_split():
    # --- CẤU HÌNH ---
    FINAL_FILENAME = "Bangladesh_Salinity_Full_2022.csv"
    NUM_SPLIT = 12  # Chia làm 12 phần (Mỗi phần chỉ khoảng 5 huyện -> Cực nhẹ)
    all_dataframes = [] 
    
    print(">>> Đang tải danh sách ranh giới hành chính...")
    base_fc = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
    
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
        print(f" ĐANG XỬ LÝ THÁNG {month}/2022")
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
            
            print(f"  [Nhóm {part_id}/{NUM_SPLIT}] Đang gửi yêu cầu cho {len(chunk)} huyện... ", end="", flush=True)

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
                    print(f"OK! (Mất {elapsed:.2f}s) - Lấy được {len(df_part)} dòng.")
                else:
                    print(f"Rỗng (Mất {elapsed:.2f}s).")

            except Exception as e:
                print(f"\nLỖI tại Nhóm {part_id}: {e}")
                print("   -> Đang nghỉ 5s rồi thử lại nhóm kế tiếp...")
                time.sleep(5)

        # Tổng kết tháng
        current_rows = sum(len(d) for d in all_dataframes)
        print(f"-> Kết thúc tháng {month}. Tổng dữ liệu hiện có: {current_rows} dòng.")

    # --- LƯU FILE ---
    print("\n------------------------------------------------")
    if all_dataframes:
        print("Đang gộp file...")
        final_df = pd.concat(all_dataframes, ignore_index=True)
        
        print("Đang xử lý dữ liệu lỗi (bên crawl)...")
        final_df['Salinity_Index_Raw'] = final_df['Salinity_Index_Raw'].replace(-9999, np.nan)
        final_df = final_df.sort_values(by=['ADM2_NAME', 'Year', 'Month'])
        final_df['Salinity_Index_Raw'] = final_df.groupby('ADM2_NAME')['Salinity_Index_Raw'].transform(lambda g: g.interpolate(method='linear', limit_direction='both').bfill().ffill())
        if final_df['Salinity_Index_Raw'].isna().sum() > 0:
            final_df['Salinity_Index_Raw'] = final_df['Salinity_Index_Raw'].fillna(0)
            
        district_map = {
            'Barisal': 'Barishal', 'Bogra': 'Bogura', 'Brahamanbaria': 'Brahmanbaria',
            'Chittagong': 'Chattogram', 'Comilla': 'Cumilla', "Cox's Bazar": 'CoxsBazar',
            'Jessore': 'Jashore', 'Jhalokati': 'Jhallokati', 'Khagrachhari': 'Khagrachari',
            'Maulvibazar': 'Moulvibazar', 'Nawabganj': 'Chapai Nawabganj',
            'Netrakona': 'Netrokona', 'Panchagarh': 'Panchagar'
        }
        final_df['District'] = final_df['ADM2_NAME'].replace(district_map)
        
        print(f"HOÀN TẤT CRAWL VÀ XỬ LÝ LỖI!")
        print(f"Tổng số dòng: {len(final_df)}")
        return final_df
    else:
        print("Không thu thập được dữ liệu nào.")
        return None

def merge_datasets(df_salinity):
    # Tên các file đầu vào và đầu ra
    main_data_path = 'Bangladesh_main_data.csv'
    output_path = 'Process_Bangladesh_Salinity_data.csv'

    if not os.path.exists(main_data_path):
        print(f"Lỗi: Không tìm thấy file dữ liệu main.")
        return

    print("Đang đọc dữ liệu main...")
    try:
        df_main = pd.read_csv(main_data_path)
    except Exception as e:
        print(f"Lỗi khi đọc file CSV: {e}")
        return

    # District đã được chuẩn hóa ở bước crawl

    def get_season(month):
        if month in [11, 12, 1, 2, 3]: return 'Rabi'
        elif month in [4, 5, 6]: return 'Kharif 1'
        elif month in [7, 8, 9, 10]: return 'Kharif 2'
        return None

    print("Đang phân loại mùa vụ...")
    df_salinity['Season'] = df_salinity['Month'].apply(get_season)

    print("Đang tính toán độ mặn trung bình theo mùa...")
    salinity_agg = df_salinity.groupby(['District', 'Season'])['Salinity_Index_Raw'].mean().reset_index()
    salinity_agg.rename(columns={'Salinity_Index_Raw': 'Avg_Salinity_Index'}, inplace=True)

    print("Đang ghép dữ liệu...")
    merged_df = pd.merge(df_main, salinity_agg, on=['District', 'Season'], how='left')

    print(f"Đang lưu kết quả vào file '{output_path}'...")
    merged_df.to_csv(output_path, index=False)
    print("Hoàn tất!")

if __name__ == "__main__":
    df_salinity_result = run_bangladesh_super_split()
    if df_salinity_result is not None:
        merge_datasets(df_salinity_result)