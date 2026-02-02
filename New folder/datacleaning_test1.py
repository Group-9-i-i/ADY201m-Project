import pandas as pd
import numpy as np

# 1. Tải bộ dữ liệu chính
df = pd.read_csv('data_enriched_npk.csv')

# Kiểm tra nhanh dữ liệu ban đầu
print("Số dòng/cột ban đầu:", df.shape)
print(df.info())