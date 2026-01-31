import pandas as pd
df = pd.read_csv('data_season_with_ndvi_fixed.csv')
mb = df.groupby('Location')['yeilds'].mean()
isnull= df.isnull().sum()
print(df.describe())
print(df.duplicated().sum())
