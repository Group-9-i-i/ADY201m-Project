import pandas as pd
df = pd.read_csv("kk.csv", encoding="utf-8-sig")
print(df.head())
print(df.info())    
print("Read xong")
