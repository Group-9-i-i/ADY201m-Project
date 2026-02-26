import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import KFold, ParameterSampler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# 1. Đọc dữ liệu (Giữ nguyên gốc, KHÔNG DÙNG LOGARIT NỮA)
X_train = pd.read_csv('X_train.csv')
X_test = pd.read_csv('X_test.csv')
y_train = pd.read_csv('y_train.csv').values.ravel()
y_test = pd.read_csv('y_test.csv').values.ravel()

# 2. Không gian siêu tham số Tối thượng (Dành cho reg:tweedie)
param_grid = {
    'n_estimators': [3000],                     # Vẫn để trần cao, Early Stopping sẽ tự cắt
    'learning_rate': [0.01, 0.02, 0.05, 0.1],   # Học chậm lại để mô hình "ngấm" dữ liệu sâu hơn
    'max_depth': [5, 7, 9, 11],                 # Mở rộng độ sâu cho phép
    'min_child_weight': [1, 3, 5, 7],
    'subsample': [0.7, 0.8, 0.9, 1.0],
    'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
    'colsample_bynode': [0.6, 0.8, 1.0],        # ÉP MÔ HÌNH HỌC CÁC BIẾN MÔI TRƯỜNG, phá vỡ sự thống trị của One-Hot
    'gamma': [0, 0.1, 0.3, 0.5],
    'reg_alpha': [0, 0.5, 1, 5],                # L1
    'reg_lambda': [1, 5, 10, 20],               # L2
    'tweedie_variance_power': [1.2, 1.5, 1.8]   # [ĐẶC BIỆT] Hệ số điều chỉnh độ cong của phân phối Năng suất
}

# Tăng số vòng thử nghiệm lên 100 để xác suất quét trúng bộ tham số vàng cao hơn
n_iter = 100
param_list = list(ParameterSampler(param_grid, n_iter=n_iter, random_state=42))
kf = KFold(n_splits=5, shuffle=True, random_state=42)

best_score = -np.inf
best_params = None
best_trees = 0

print("Đang huấn luyện (Objective: Tweedie Regression + Tối ưu hóa GPU RTX 4050)...")

# 3. Tìm kiếm mô hình tối ưu
for params in tqdm(param_list, desc="Tiến trình (100 Cấu hình)", unit=" Mô Hình"):
    fold_scores = []
    fold_best_iters = [] 
    
    for train_idx, val_idx in kf.split(X_train):
        X_tr, X_va = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_tr, y_va = y_train[train_idx], y_train[val_idx]
        
        # SỬ DỤNG TWEEDIE REGRESSION TRÊN GPU
        model = XGBRegressor(
            **params, 
            random_state=42, 
            n_jobs=-1,  
            objective='reg:tweedie',  # ĐỔI TỪ SQUARED ERROR SANG TWEEDIE
            tree_method='hist',
            device='cuda',
            max_bin=256,
            early_stopping_rounds=50
        )
        
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_va, y_va)],
            verbose=False
        )
        
        preds = model.predict(X_va)
        score = r2_score(y_va, preds)
        
        fold_scores.append(score)
        fold_best_iters.append(model.best_iteration)
        
    avg_score = np.mean(fold_scores)
    avg_best_iter = int(np.mean(fold_best_iters)) 
    
    if avg_score > best_score:
        best_score = avg_score
        best_params = params
        best_trees = avg_best_iter 

best_params['n_estimators'] = best_trees

# 4. Huấn luyện lại mô hình cuối cùng trên toàn bộ tập dữ liệu
print(f"\n[Hoàn tất] Cấu hình tốt nhất được chọn. Số cây (Trees) tối ưu: {best_trees}")
print("Bắt đầu đào tạo siêu mô hình cuối cùng trên GPU...")

final_model = XGBRegressor(
    **best_params, 
    random_state=42, 
    n_jobs=-1, 
    objective='reg:tweedie',
    tree_method='hist',
    device='cuda',
    max_bin=256
)

final_model.fit(X_train, y_train, verbose=False)

# 5. DỰ ĐOÁN TRỰC TIẾP (Không cần giải mã exmp1 nữa)
y_pred_train = final_model.predict(X_train)
y_pred_test = final_model.predict(X_test)

def evaluate(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_true, y_pred)
    return mae, mse, rmse, r2

train_mae, train_mse, train_rmse, train_r2 = evaluate(y_train, y_pred_train)
test_mae, test_mse, test_rmse, test_r2 = evaluate(y_test, y_pred_test)

print("\n" + "="*60)
print("KẾT QUẢ TÌM KIẾM SIÊU THAM SỐ (Tweedie Regression trên GPU)")
print("="*60)
for param, value in best_params.items():
    print(f" ► {param}: {value}")

print("\n" + "="*60)
print("ĐÁNH GIÁ MÔ HÌNH TRÊN TẬP HUẤN LUYỆN (Train Set)")
print("="*60)
print(f" ► Mean Absolute Error (MAE) : {train_mae:.4f}")
print(f" ► Root Mean Squared (RMSE)  : {train_rmse:.4f}")
print(f" ► R-squared (R2 Score)      : {train_r2:.4f}")

print("\n" + "="*60)
print("ĐÁNH GIÁ MÔ HÌNH TRÊN TẬP KIỂM TRA (Test Set)")
print("="*60)
print(f" ► Mean Absolute Error (MAE) : {test_mae:.4f}")
print(f" ► Root Mean Squared (RMSE)  : {test_rmse:.4f}")
print(f" ► R-squared (R2 Score)      : {test_r2:.4f}")

print("\n" + "="*60)
print("TOP 15 MỐI LIÊN HỆ ĐẶC TRƯNG QUAN TRỌNG NHẤT")
print("="*60)
feature_importances = final_model.feature_importances_
importance_df = pd.DataFrame({'Feature': X_train.columns, 'Importance_Score': feature_importances})
importance_df = importance_df.sort_values(by='Importance_Score', ascending=False)

for index, row in importance_df.head(15).iterrows():
    print(f"{row['Feature']:<35} : {row['Importance_Score']:.5f}")