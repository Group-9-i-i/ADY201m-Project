import pandas as pd
import numpy as np
import time
from tqdm import tqdm
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RandomizedSearchCV
from sklearn.ensemble import StackingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, LinearRegression

# Import các mô hình cơ sở
from xgboost import XGBRegressor
from catboost import CatBoostRegressor

def evaluate_model(name, model, X_train, y_train, X_test, y_test):
    """Hàm đánh giá chi tiết cả trên Train và Test"""
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    
    train_r2 = r2_score(y_train, y_train_pred)
    train_mse = mean_squared_error(y_train, y_train_pred)
    
    test_r2 = r2_score(y_test, y_test_pred)
    test_mse = mean_squared_error(y_test, y_test_pred)
    _, p_val = pearsonr(y_test, y_test_pred)
    
    print(f"\n[{name.upper()}]")
    print(f"  + TRAIN | R²: {train_r2:7.4f} | MSE: {train_mse:8.4f}")
    print(f"  + TEST  | R²: {test_r2:7.4f} | MSE: {test_mse:8.4f}")
    print(f"  + P-value (Test): {p_val:.5e}")
    return test_r2

def main():
    # =========================================================================
    # 1. TẢI DỮ LIỆU
    # =========================================================================
    print("1. Đang tải dữ liệu...")
    try:
        X_train = pd.read_csv('X_train.csv')
        y_train = pd.read_csv('y_train.csv').values.ravel()
        X_test = pd.read_csv('X_test.csv')
        y_test = pd.read_csv('y_test.csv').values.ravel()
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file dữ liệu. {e}")
        return

    # =========================================================================
    # 2. TARGET ENCODING
    # =========================================================================
    print("2. Đang áp dụng Target Encoding...")
    ohe_prefixes = ['District_'] 
    
    for prefix in ohe_prefixes:
        cols = [c for c in X_train.columns if c.startswith(prefix)]
        if len(cols) > 0:
            global_mean = y_train.mean()
            target_means = {}
            
            for col in cols:
                idx = X_train[X_train[col] == 1].index
                if len(idx) > 0:
                    target_means[col] = y_train[idx].mean()
                else:
                    target_means[col] = global_mean
                    
            new_col_name = f"{prefix}Target_Encoded"
            X_train[new_col_name] = global_mean
            X_test[new_col_name] = global_mean
            
            for col in cols:
                X_train.loc[X_train[col] == 1, new_col_name] = target_means[col]
                X_test.loc[X_test[col] == 1, new_col_name] = target_means.get(col, global_mean)
                
            X_train = X_train.drop(columns=cols)
            X_test = X_test.drop(columns=cols)

    # =========================================================================
    # 3. CHUẨN HÓA DỮ LIỆU
    # =========================================================================
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # =========================================================================
    # 4. TÌM KIẾM THAM SỐ (KỶ LUẬT SẮT - EXTREME REGULARIZATION)
    # =========================================================================
    model_grids = {
        "Lasso": {
            "model": Lasso(random_state=42),
            "params": {'alpha': [1.0, 5.0, 10.0]} # Lọc biến nhiễu cực mạnh
        },
        "RandomForest": {
            "model": RandomForestRegressor(random_state=42, max_features='sqrt'),
            "params": {
                'n_estimators': [100, 150],
                'max_depth': [2, 3, 4],            # Rất lùn
                'min_samples_leaf': [15, 20, 30]   # Lá khổng lồ
            }
        },
        "XGBoost": {
            "model": XGBRegressor(objective='reg:squarederror', random_state=42),
            "params": {
                'n_estimators': [100, 150],
                'max_depth': [1, 2, 3],            # Cây chỉ 1-2 tầng
                'learning_rate': [0.01, 0.03],
                'subsample': [0.5, 0.7],           # Chỉ dùng 50-70% dữ liệu
                'colsample_bytree': [0.5, 0.7],
                'reg_lambda': [50, 100, 200]       # Phạt L2 khổng lồ
            }
        },
        "CatBoost": {
            "model": CatBoostRegressor(verbose=0, random_state=42),
            "params": {
                'iterations': [100, 200],
                'depth': [2, 3, 4],                # Rất lùn
                'learning_rate': [0.01, 0.03],
                'subsample': [0.5, 0.7],
                'l2_leaf_reg': [50, 100, 200]      # Phạt L2 khổng lồ
            }
        }
    }

    print("\n3. Bắt đầu tìm kiếm tham số (Không gian tham số Kỷ Luật Sắt)...")
    best_estimators = []
    
    for name in tqdm(model_grids.keys(), desc="Đang chạy"):
        search = RandomizedSearchCV(
            estimator=model_grids[name]["model"],
            param_distributions=model_grids[name]["params"],
            n_iter=10,       
            scoring='neg_mean_squared_error',
            cv=5,            
            n_jobs=-1,
            random_state=42
        )
        
        search.fit(X_train_scaled, y_train)
        best_model = search.best_estimator_
        best_estimators.append((name, best_model))
        
        evaluate_model(name, best_model, X_train_scaled, y_train, X_test_scaled, y_test)

    # =========================================================================
    # 5. STACKING ENSEMBLE
    # =========================================================================
    print("\n4. Đang kết hợp Ensemble bằng Stacking...")
    stacking_model = StackingRegressor(
        estimators=best_estimators,
        # Lasso(positive=True) ở tầng Meta giúp chặn bớt mô hình thừa và giữ tỷ lệ dương
        final_estimator=Lasso(alpha=0.01, positive=True, random_state=42), 
        cv=5,
        n_jobs=-1
    )
    stacking_model.fit(X_train_scaled, y_train)

    # =========================================================================
    # 6. ĐÁNH GIÁ TỔNG THỂ
    # =========================================================================
    print("\n" + "="*70)
    print("KẾT QUẢ CUỐI CÙNG CỦA MÔ HÌNH ENSEMBLE (STACKING)".center(70))
    print("="*70)
    
    evaluate_model("STACKING ENSEMBLE", stacking_model, X_train_scaled, y_train, X_test_scaled, y_test)
    
    weights = stacking_model.final_estimator_.coef_
    print("\n[PHÂN TÍCH TRỌNG SỐ] Mức độ tin tưởng của 'Sếp' vào các mô hình:")
    for name, weight in zip([name for name, _ in best_estimators], weights):
        print(f" - {name:15}: {weight:.4f} ({weight*100:.1f}%)")
    print("="*70)

if __name__ == "__main__":
    main()