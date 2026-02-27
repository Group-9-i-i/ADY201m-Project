import pandas as pd
import numpy as np
import time
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

# Import các mô hình
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor

def main():
    # 1. Tải dữ liệu
    print("Đang tải dữ liệu...")
    try:
        X_train = pd.read_csv('X_train.csv')
        y_train = pd.read_csv('y_train.csv')
        X_test = pd.read_csv('X_test.csv')
        y_test = pd.read_csv('y_test.csv')
    except FileNotFoundError as e:
        print(f"Lỗi: {e}")
        return

    # Chuyển đổi y thành mảng 1D
    y_train = y_train.values.ravel()
    y_test = y_test.values.ravel()

    # 2. ĐỘT PHÁ: ÁP DỤNG TARGET ENCODING CHO BIẾN PHÂN LOẠI
    # Khai báo các tiền tố (prefix) của các cột đã bị One-hot. 
    # Nếu bạn có One-hot cho Mùa vụ hay Loại cây thì có thể thêm vào: ['District_', 'Season_', 'Crop_']
    ohe_prefixes = ['District_'] 
    
    for prefix in ohe_prefixes:
        # Tìm tất cả các cột thuộc nhóm này
        cols = [c for c in X_train.columns if c.startswith(prefix)]
        
        if len(cols) > 0:
            print(f"Đang thực hiện Target Encoding gộp các cột: {prefix}...")
            global_mean = y_train.mean()
            target_means = {}
            
            # Tính Target Mean (Năng suất trung bình) trên tập Train cho từng Huyện
            for col in cols:
                # Lấy index các dòng mà huyện này có giá trị = 1
                idx = X_train[X_train[col] == 1].index
                if len(idx) > 0:
                    target_means[col] = y_train[idx].mean()
                else:
                    target_means[col] = global_mean
                    
            # Tạo 1 cột duy nhất mới thay thế cho hàng chục cột cũ
            new_col_name = f"{prefix}Target_Encoded"
            X_train[new_col_name] = global_mean
            X_test[new_col_name] = global_mean
            
            # Áp xạ (map) giá trị Target Mean vào cột mới
            for col in cols:
                X_train.loc[X_train[col] == 1, new_col_name] = target_means[col]
                X_test.loc[X_test[col] == 1, new_col_name] = target_means.get(col, global_mean)
                
            # XÓA toàn bộ các cột One-hot cũ để giảm chiều dữ liệu
            X_train = X_train.drop(columns=cols)
            X_test = X_test.drop(columns=cols)
            print(f"-> Đã giảm từ {len(cols)} cột One-hot xuống còn 1 cột {new_col_name}")

    # 3. CHUẨN HÓA DỮ LIỆU
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. THIẾT LẬP MÔ HÌNH (THAM SỐ CÂN BẰNG)
    models = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression": Ridge(alpha=1.0),
        "Lasso Regression": Lasso(alpha=0.01),
        "Decision Tree": DecisionTreeRegressor(max_depth=8, min_samples_leaf=4, random_state=42),
        "Random Forest": RandomForestRegressor(n_estimators=200, max_depth=10, min_samples_leaf=2, max_features='sqrt', random_state=42),
        "XGBoost": XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, colsample_bytree=0.7, random_state=42, objective='reg:squarederror'),
        "LightGBM": LGBMRegressor(n_estimators=200, max_depth=8, learning_rate=0.05, colsample_bytree=0.7, random_state=42, verbose=-1),
        "CatBoost": CatBoostRegressor(iterations=300, learning_rate=0.05, depth=6, verbose=0, random_state=42),
        "SVR": SVR(kernel='rbf', C=1.0, epsilon=0.1),
        "ANN (MLPRegressor)": MLPRegressor(hidden_layer_sizes=(128, 64), activation='relu', max_iter=1000, early_stopping=True, random_state=42)
    }

    # 5. HUẤN LUYỆN VÀ ĐÁNH GIÁ
    results = []
    print("\nBắt đầu huấn luyện và đánh giá...")
    for name, model in models.items():
        start_time = time.time()
        try:
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)
            
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            end_time = time.time()
            results.append({
                "Mô hình": name,
                "MAE": round(mae, 4),
                "MSE": round(mse, 4),
                "RMSE": round(rmse, 4),
                "R²": round(r2, 4),
                "Thời gian chạy (s)": round(end_time - start_time, 2)
            })
            print(f"[OK] Đã hoàn thành: {name}")
        except Exception as e:
            print(f"[LỖI] Cố gắng chạy {name} thất bại. Lỗi: {e}")

    # 6. TỔNG HỢP VÀ IN KẾT QUẢ
    if results:
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by="R²", ascending=False).reset_index(drop=True)

        print("\n" + "="*85)
        print(f"{'BẢNG TỔNG HỢP KẾT QUẢ (ÁP DỤNG TARGET ENCODING)':^85}")
        print("="*85)
        print(results_df.to_string(index=False))
        print("="*85)
        
        results_df.to_csv('model_comparison_TE_results.csv', index=False)
        print("\n-> Kết quả đã được lưu vào file 'model_comparison_TE_results.csv'")

if __name__ == "__main__":
    main()