import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import RandomizedSearchCV, KFold
from sklearn.linear_model import ElasticNetCV, RidgeCV, BayesianRidge
from sklearn.preprocessing import PowerTransformer, StandardScaler, RobustScaler, PolynomialFeatures
from sklearn.feature_selection import SelectFromModel, VarianceThreshold
from sklearn.pipeline import Pipeline
from sklearn.ensemble import (
    StackingRegressor, 
    HistGradientBoostingRegressor, 
    ExtraTreesRegressor,
    RandomForestRegressor
)
from sklearn.neighbors import KNeighborsRegressor
from sklearn.decomposition import PCA
from scipy.stats import pearsonr
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

# =====================================================================
# 1. ĐỌC VÀ CHUẨN BỊ DỮ LIỆU
# =====================================================================
X_train = pd.read_csv('X_train.csv')
y_train = pd.read_csv('y_train.csv').values.ravel()
X_test = pd.read_csv('X_test.csv')
y_test = pd.read_csv('y_test.csv').values.ravel()

def evaluate_model(y_true, y_pred, model_name, dataset_name):
    r2 = r2_score(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    corr, p_value = pearsonr(y_true, y_pred)
    
    print(f"--- {model_name} | {dataset_name} ---")
    print(f"R-squared : {r2:.4f}")
    print(f"MSE       : {mse:.4f}")
    print(f"P-value   : {p_value:.4e} (Độ tương quan: {corr:.4f})")
    print("-" * 50)
    return r2, mse, p_value

# =====================================================================
# 2. NÃO TRÁI: DÒNG CHẢY TUYẾN TÍNH & ĐA THỨC (LINEAR & SMOOTH)
# =====================================================================
print("Đang khởi tạo [Não Trái] - Tuyến tính với PowerTransformer và ElasticNet...\n")

# Dùng PowerTransformer (Yeo-Johnson) thay vì RobustScaler để ép mọi biến về phân phối chuẩn (Normal Distribution).
# Kết hợp VarianceThreshold để xóa các biến đa thức sinh ra bị hằng số/gần hằng số gây nhiễu.
linear_pipeline = Pipeline([
    ('scaler', PowerTransformer(method='yeo-johnson')), 
    ('poly', PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)),
    ('variance_filter', VarianceThreshold(threshold=0.01)),
    # Dùng ElasticNet (L1 + L2) thay vì Lasso (chỉ L1) để giữ lại các biến tương quan nhóm tốt hơn
    ('feature_selection', SelectFromModel(ElasticNetCV(cv=5, random_state=42, n_jobs=-1, l1_ratio=[0.5, 0.7, 0.9]))),
    ('elasticnet', ElasticNetCV(cv=5, random_state=42, n_jobs=-1, l1_ratio=[0.1, 0.5, 0.9, 0.95]))
])

# Thêm 1 nhánh Não Trái Phụ: PCA + Ridge để nén giảm chiều, giải quyết Multicollinearity triệt để
pca_ridge_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('pca', PCA(n_components=0.95, random_state=42)), # Giữ lại 95% lượng thông tin
    ('ridge', RidgeCV())
])

# =====================================================================
# 3. NÃO GIỮA: DÒNG CHẢY KHOẢNG CÁCH (PROXIMITY / KNN)
# =====================================================================
print("Đang khởi tạo [Não Giữa] - Không gian cục bộ với KNN...\n")
knn_pipeline = Pipeline([
    ('scaler', RobustScaler()), # KNN chuộng RobustScaler để không bị ảnh hưởng bởi Outlier
    ('knn', KNeighborsRegressor(n_neighbors=8, weights='distance', p=1)) # p=1 (Manhattan) mạnh hơn với Dữ liệu Tabular nhiều chiều
])

# =====================================================================
# 4. NÃO PHẢI: DÒNG CHẢY RỪNG SÂU & TĂNG CƯỜNG (TREE-BASED & GRADIENT BOOSTING)
# =====================================================================
print("Đang thiết lập [Não Phải] - Các siêu mô hình cây quy định độ cong và ngoại lệ...\n")

# 4.1. HistGradientBoosting (LightGBM nội bộ của Scikit-Learn - Tốc độ bàn thờ, chia bin cực tốt)
hgb_model = HistGradientBoostingRegressor(
    max_iter=1000, 
    learning_rate=0.03, 
    max_leaf_nodes=63, 
    min_samples_leaf=15, 
    l2_regularization=2.0,
    random_state=42
)

# 4.2. ExtraTrees (Tuyệt chiêu chống Overfitting của họ Rừng ngẫu nhiên)
et_model = ExtraTreesRegressor(
    n_estimators=600, 
    max_depth=15, 
    min_samples_split=5,
    max_features='sqrt', # Lấy ngẫu nhiên căn bậc 2 số lượng biến để phá vỡ sự kìm kẹp của các biến mạnh
    random_state=42, 
    n_jobs=-1
)

# 4.3. XGBoost (Tối ưu hóa bằng RandomizedSearchCV)
print("Đang tìm tham số tối đa sức mạnh cho XGBoost...\n")
xgb_base = xgb.XGBRegressor(random_state=42, objective='reg:squarederror')
xgb_param_dist = {
    'n_estimators': [800, 1000, 1500, 2000],
    'learning_rate': [0.01, 0.02, 0.05],
    'max_depth': [4, 5, 6, 7],         # Giảm độ sâu để nhường không gian cho Meta-Model tổng hợp
    'subsample': [0.6, 0.7, 0.8],
    'colsample_bytree': [0.5, 0.6, 0.8],
    'gamma': [0, 0.1, 0.5, 1],
    'min_child_weight': [3, 5, 7],
    'reg_alpha': [0.5, 1, 5, 10],      # Ép Regularization mạnh hơn
    'reg_lambda': [1, 5, 10, 20]
}

random_search_xgb = RandomizedSearchCV(
    estimator=xgb_base,
    param_distributions=xgb_param_dist,
    n_iter=50, 
    scoring='neg_mean_squared_error',
    cv=KFold(n_splits=5, shuffle=True, random_state=42),
    verbose=0,
    random_state=42,
    n_jobs=-1
)
random_search_xgb.fit(X_train, y_train)
best_xgb = random_search_xgb.best_estimator_
print(f"Tham số XGBoost tối ưu: {random_search_xgb.best_params_}\n")

# =====================================================================
# 5. BỘ NÃO TRUNG ƯƠNG: KẾT HỢP (STACKING) VỚI BAYESIAN RIDGE
# =====================================================================
print("Đang tiến hành dung hợp các Não (Stacking Ensemble)...\n")

# Tập hợp các chuyên gia
estimators = [
    ('Linear_Poly', linear_pipeline),  # Chuyên bắt tín hiệu tuyến tính & tương tác đôi
    ('Linear_PCA', pca_ridge_pipeline),# Chuyên bắt cấu trúc nền móng của dữ liệu
    ('KNN_Local', knn_pipeline),       # Chuyên bắt lân cận, các điểm giống nhau
    ('Tree_HGB', hgb_model),           # Học phân phối bằng Binning cực tốt
    ('Tree_ET', et_model),             # Lọc nhiễu, cực kỳ ổn định (ổn định test set)
    ('Tree_XGB', best_xgb)             # Thuật toán chủ lực chuyên đấm các sai số nhỏ
]

# Sử dụng BayesianRidge: Tự động đánh giá sự tự tin của mỗi mô hình con (Thay vì RidgeCV cứng nhắc)
ensemble_model = StackingRegressor(
    estimators=estimators,
    final_estimator=BayesianRidge(), 
    cv=KFold(n_splits=5, shuffle=True, random_state=42),
    n_jobs=-1,
    passthrough=False 
)

# Đào tạo toàn bộ Cỗ máy
ensemble_model.fit(X_train, y_train)

# =====================================================================
# 6. ĐÁNH GIÁ KẾT QUẢ
# =====================================================================
y_train_pred = ensemble_model.predict(X_train)
y_test_pred = ensemble_model.predict(X_test)

print("\n" + "="*50)
print("🏆 KẾT QUẢ CỦA SIÊU MÔ HÌNH (SUPER-ENSEMBLE)")
print("="*50)
evaluate_model(y_train, y_train_pred, "MÔ HÌNH MULTI-BRAIN", "TẬP TRAIN")
evaluate_model(y_test, y_test_pred, "MÔ HÌNH MULTI-BRAIN", "TẬP TEST")

# (Tùy chọn) Xem trọng số mà BayesianRidge đã gán cho từng "Não"
final_weights = ensemble_model.final_estimator_.coef_
print("\n[Trọng số tín nhiệm (Weights) của từng Não do Meta-Model quyết định]:")
for name, weight in zip([e[0] for e in estimators], final_weights):
    print(f" - {name:<15}: {weight:.4f}")