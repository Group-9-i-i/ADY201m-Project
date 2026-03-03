import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

# 1. Đọc dữ liệu đã chuẩn bị
X_train = pd.read_csv('X_train.csv')
y_train = pd.read_csv('y_train.csv').values.ravel()
X_test = pd.read_csv('X_test.csv')
y_test = pd.read_csv('y_test.csv').values.ravel()

# 2. Xây dựng Pipeline chuẩn mực (Scaling + Model)
# Pipeline giúp gói gọn các bước xử lý, đảm bảo không bao giờ tính toán trên tập Test
pipeline = Pipeline([
    ('scaler', StandardScaler()),       # Chuẩn hóa dữ liệu (quan trọng cho Ridge/Lasso)
    ('model', Ridge(random_state=42))   # Ridge Regression (L2) chuyên trị Overfitting
])

# 3. Tìm tham số Alpha tối ưu bằng Cross-Validation (Chỉ trên tập Train)
param_grid = {
    'model__alpha': [0.1, 1, 10, 50, 100, 200, 500] 
}

cv = KFold(n_splits=5, shuffle=True, random_state=42)

grid_search = GridSearchCV(
    estimator=pipeline,
    param_grid=param_grid,
    cv=cv,
    scoring='r2',
    n_jobs=-1,
    verbose=1
)

# 4. Huấn luyện
print("Đang tìm tham số tối ưu...")
grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_

print(f"Tham số Alpha tốt nhất: {grid_search.best_params_['model__alpha']}")

# 5. Đánh giá kết quả (Final Evaluation)
y_pred_train = best_model.predict(X_train)
y_pred_test = best_model.predict(X_test)

r2_train = r2_score(y_train, y_pred_train)
r2_test = r2_score(y_test, y_pred_test)

print("-" * 30)
print(f"R2 Score (Train): {r2_train:.4f}")
print(f"R2 Score (Test):  {r2_test:.4f}")
print(f"Độ lệch (Overfitting): {r2_train - r2_test:.4f}")
print("-" * 30)

if (r2_train - r2_test) < 0.05:
    print("Mô hình RẤT TỐT về mặt tổng quát hóa (Không Overfitting).")
else:
    print("Cần tăng Alpha thêm để giảm Overfitting.")