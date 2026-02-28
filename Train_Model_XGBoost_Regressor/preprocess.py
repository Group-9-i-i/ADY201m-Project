import pandas as pd
import numpy as np
import statsmodels.api as sm
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder

# 1. Load dữ liệu và tạo biến mục tiêu
df = pd.read_csv('Agri_Data_Cleaned.csv')
df['Yield'] = df['Production'] / df['Area'] # Tạo biến năng suất

# 2. Loại bỏ các cột không dùng cho training
# - 'Year', 'Compaction_Risk': Chỉ có 1 giá trị duy nhất (Constant)
# - 'Production', 'Area': Đã dùng để tính Yield
# - 'AP Ratio': Tương đương Yield
cols_to_drop = ['Production', 'Area', 'AP Ratio', 'Year', 'Compaction_Risk']
df_model = df.drop(columns=cols_to_drop)

# 3. Xử lý dữ liệu Categorical (Mã hóa)
# Chuyển đổi các cột chữ sang số để mô hình có thể chạy
le = LabelEncoder()
cat_cols = df_model.select_dtypes(include=['object']).columns
for col in cat_cols:
    df_model[col] = le.fit_transform(df_model[col].astype(str))

# Tách biến độc lập (X) và biến mục tiêu (y)
X = df_model.drop(columns=['Yield'])
y = df_model['Yield']

# ---------------------------------------------------------
# PHƯƠNG PHÁP 1: Dùng P-value của Linear Regression
# ---------------------------------------------------------
# Thêm hằng số intercept cho mô hình OLS
X_const = sm.add_constant(X)
model_ols = sm.OLS(y, X_const).fit()

print("--- TOP 10 BIẾN CÓ P-VALUE CAO NHẤT (Nên cân nhắc loại bỏ) ---")
# P-value > 0.05 thường được coi là không có ý nghĩa thống kê
print(model_ols.pvalues.sort_values(ascending=False).head(10))

# ---------------------------------------------------------
# PHƯƠNG PHÁP 2: Dùng Feature Importance của Gradient Boosting (XGBoost)
# ---------------------------------------------------------
model_gb = GradientBoostingRegressor(random_state=42)
model_gb.fit(X, y)

feature_importance = pd.Series(model_gb.feature_importances_, index=X.columns)
print("\n--- TOP 10 BIẾN CÓ ĐỘ QUAN TRỌNG THẤP NHẤT (Nên cân nhắc loại bỏ) ---")
print(feature_importance.sort_values().head(10))

# ---------------------------------------------------------
# PHƯƠNG PHÁP 3: Kiểm tra Tương quan (Correlation)
# ---------------------------------------------------------
# Tìm các cặp biến có tương quan > 0.95 (có thể suy ra lẫn nhau)
corr_matrix = X.corr().abs()
upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
high_corr_features = [column for column in upper.columns if any(upper[column] > 0.95)]

print("\n--- CÁC BIẾN CÓ TƯƠNG QUAN CAO (> 0.95) ---")
for col in high_corr_features:
    print(f"- {col} (Có thể bị dư thừa do tương quan với biến khác)")