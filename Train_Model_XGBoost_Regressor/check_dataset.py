import pandas as pd
import numpy as np

def analyze_data():
    print("="*60)
    print(" BÁO CÁO KIỂM TRA SỨC KHỎE DỮ LIỆU (DATA AUDIT)".center(60))
    print("="*60)

    try:
        X_train = pd.read_csv('X_train.csv')
        y_train = pd.read_csv('y_train.csv')
        X_test = pd.read_csv('X_test.csv')
        y_test = pd.read_csv('y_test.csv')
    except FileNotFoundError as e:
        print(f"Lỗi tải file: {e}")
        return

    # 1. KIỂM TRA BIẾN MỤC TIÊU (YIELD)
    print("\n1. PHÂN BỐ CỦA BIẾN MỤC TIÊU (YIELD):")
    print("-" * 50)
    
    y_train_stats = y_train.describe().T
    y_test_stats = y_test.describe().T
    
    comp_df = pd.DataFrame({
        'Train (Yield)': y_train_stats.iloc[0],
        'Test (Yield)': y_test_stats.iloc[0]
    })
    print(comp_df.round(3).to_string())

    train_outliers = (y_train > y_train.quantile(0.99)).sum().values[0]
    test_outliers = (y_test > y_test.quantile(0.99)).sum().values[0]
    print(f"\n -> Số lượng điểm đột biến (Outliers > 99th percentile):")
    print(f"    - Tập Train: {train_outliers} điểm")
    print(f"    - Tập Test:  {test_outliers} điểm")
    
    if y_train.std().values[0] > y_test.std().values[0] * 1.5:
        print("\n [CẢNH BÁO ĐỎ] Độ lệch chuẩn của Train lớn hơn Test RẤT NHIỀU.")
        print(" -> Giải thích tại sao Train R² thấp: Tập Train quá nhiễu, Test lại quá 'sạch'.")

    # 2. KIỂM TRA SỰ LỆCH PHA CỦA DỮ LIỆU ĐẦU VÀO (X)
    print("\n2. KIỂM TRA SỰ KHÁC BIỆT (DATA SHIFT) GIỮA TRAIN VÀ TEST:")
    print("-" * 50)
    
    shift_cols = []
    for col in X_train.select_dtypes(include=np.number).columns:
        train_mean = X_train[col].mean()
        test_mean = X_test[col].mean()
        
        # Nếu trung bình của Test lệch quá 20% so với Train
        if train_mean != 0 and abs(train_mean - test_mean) / abs(train_mean) > 0.2:
            shift_cols.append((col, train_mean, test_mean))
    
    if len(shift_cols) > 0:
        print(f" Phát hiện {len(shift_cols)} biến có độ phân bố lệch nhau > 20%:")
        for col, t_m, te_m in shift_cols[:10]: # Chỉ in 10 cột lệch nhất
            print(f"   - {col}: Train_Mean = {t_m:.2f} | Test_Mean = {te_m:.2f}")
        if len(shift_cols) > 10:
             print("     ... (và nhiều biến khác)")
    else:
        print(" Các biến đầu vào có phân bố khá đồng đều giữa Train và Test.")

    # 3. TÌM BIẾN TƯƠNG QUAN MẠNH NHẤT VỚI YIELD
    print("\n3. TƯƠNG QUAN CỦA CÁC ĐẶC TRƯNG VỚI YIELD (Tập Train):")
    print("-" * 50)
    # Gộp tạm để tính tương quan
    train_full = X_train.copy()
    train_full['Yield_Target'] = y_train.values
    
    correlations = train_full.corr()['Yield_Target'].drop('Yield_Target').dropna()
    top_corr = correlations.abs().sort_values(ascending=False).head(5)
    
    print(" 5 biến có sức mạnh dự báo TỐT NHẤT:")
    for col, val in top_corr.items():
        print(f"   - {col:30}: {val:.4f} (Dấu {'+' if correlations[col] > 0 else '-'})")
        
    print("\n" + "="*60)

if __name__ == "__main__":
    analyze_data()