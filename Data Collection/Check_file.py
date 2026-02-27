import pandas as pd 
df = pd.read_csv("Process_Bangladesh_ndvi_data.csv")
print(len(df["District"].unique()))
print(df.isnull().sum())
rows_with_null = df[df.isnull().any(axis=1)]
print(rows_with_null)