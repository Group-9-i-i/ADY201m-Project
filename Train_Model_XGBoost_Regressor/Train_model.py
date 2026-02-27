import pandas as pd
import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

# IMPORT TRỰC TIẾP TỪ LIGHTGBM
from lightgbm import LGBMRegressor, early_stopping, log_evaluation 

def evaluate_model(name, model, X_train, y_train, X_test, y_test):
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

def main():
    # 1. TẢI DỮ LIỆU
    print("1. Đang tải dữ liệu...")
    try:
        X_train = pd.read_csv('X_train.csv')
        y_train = pd.read_csv('y_train.csv').values.ravel()
        X_test = pd.read_csv('X_test.csv')
        y_test = pd.read_csv('y_test.csv').values.ravel()
    except FileNotFoundError as e:
        print(f"Lỗi: Không tìm thấy file dữ liệu. {e}")
        return

    # 2. TARGET ENCODING
    print("2. Đang áp dụng Target Encoding...")
    ohe_prefixes = ['District_'] 
    for prefix in ohe_prefixes:
        cols = [c for c in X_train.columns if c.startswith(prefix)]
        if len(cols) > 0:
            global_mean = y_train.mean()
            target_means = {}
            for col in cols:
                idx = X_train[X_train[col] == 1].index
                target_means[col] = y_train[idx].mean() if len(idx) > 0 else global_mean
                    
            new_col_name = f"{prefix}Target_Encoded"
            X_train[new_col_name], X_test[new_col_name] = global_mean, global_mean
            for col in cols:
                X_train.loc[X_train[col] == 1, new_col_name] = target_means[col]
                X_test.loc[X_test[col] == 1, new_col_name] = target_means.get(col, global_mean)
            X_train, X_test = X_train.drop(columns=cols), X_test.drop(columns=cols)

    # 3. CHUẨN HÓA
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. LIGHTGBM VỚI EARLY STOPPING 
    print("\n3. Bắt đầu huấn luyện LightGBM với Early Stopping...")
    
    lgbm_model = LGBMRegressor(
        n_estimators=1000,           
        learning_rate=0.02,          
        max_depth=6,                 
        num_leaves=31,               
        subsample=0.8,               
        colsample_bytree=0.8,        
        reg_alpha=0.1,               
        reg_lambda=5.0,              
        random_state=42,
        verbose=-1                   
    )
    
    # SỬ DỤNG CÁCH GỌI CALLBACK MỚI CHUẨN CỦA LIGHTGBM
    lgbm_model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)], 
        eval_metric='rmse',
        callbacks=[
            early_stopping(stopping_rounds=50), # Dừng nếu sau 50 cây không cải thiện
            log_evaluation(period=50)           # In tiến trình mỗi 50 cây
        ]
    )
    
    print(f"\n[INFO] Mô hình đã tự động dừng ở cây thứ: {lgbm_model.best_iteration_}")

    # 5. ĐÁNH GIÁ CUỐI CÙNG
    print("\n" + "="*70)
    print("KẾT QUẢ CUỐI CÙNG CỦA LIGHTGBM (EARLY STOPPING)".center(70))
    print("="*70)
    evaluate_model("LightGBM", lgbm_model, X_train_scaled, y_train, X_test_scaled, y_test)
    print("="*70)

if __name__ == "__main__":
    main()