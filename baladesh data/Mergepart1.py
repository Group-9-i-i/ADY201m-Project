import pandas as pd

# 1. Đọc 2 file CSV vào DataFrame
df1 = pd.read_csv('kk_with_full_env_merged_final.csv')
df2 = pd.read_csv('bangladesh_soil_final_hybrid.csv')
df3 =pd.read_csv('bangladesh_weather_2022_by_season.csv')
tamthoi = pd.merge(df1, df2, on='District')
ket_qua = pd.merge(tamthoi, df3 ,                on=['District','Season'])

# 3. Lưu kết quả ra file mới
ket_qua.to_csv('ket_qua_ghep.csv', index=False, encoding='utf-8-sig')

print("Đã ghép xong và lưu vào file ket_qua_ghep.csv")