import pandas as pd
from sqlalchemy import create_engine

# đọc csv
df = pd.read_csv("Agri_Data_Cleaned.csv", encoding="utf-8-sig")



print(df.head())
print(df.info())

engine = create_engine(
    "mssql+pyodbc://@LAPTOP-NVSURACC\\SQLEXPRESS/testdb"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)




df.to_sql(
    "DATA 3",
    engine,
    if_exists="replace",
    index=False,
    chunksize=1000   # import nhanh hơn
)

print("Import xong")
