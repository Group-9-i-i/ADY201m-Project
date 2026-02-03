import pandas as pd
df = pd.read_csv('Master_Dataset_cleaned.csv')
print(df.isna().sum())