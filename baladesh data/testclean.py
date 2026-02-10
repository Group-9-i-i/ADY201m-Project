import pandas as pd

df = pd.read_csv("ket_qua_ghep.csv")
print(df.head())
print(df.columns)
print(df.info())
print(df.describe())
print(df.isnull().sum())
print(df["District"].unique())
