import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns

# Load data
X_train = pd.read_csv('X_train.csv').apply(pd.to_numeric, errors='coerce')
y_train = pd.read_csv('y_train.csv').values.ravel()
X_test = pd.read_csv('X_test.csv').apply(pd.to_numeric, errors='coerce')
y_test = pd.read_csv('y_test.csv').values.ravel()

print("=" * 80)
print("PHÂN TÍCH NGUYÊN NHÂN TEST R2 THẤP")
print("=" * 80)

# 1. Check data distribution
print("\n1. PHÂN BỐ BIẾN MỤC TIÊU (Y)")
print("-" * 50)
print(f"Train Y - Mean: {y_train.mean():.3f}, Std: {y_train.std():.3f}, Min: {y_train.min():.3f}, Max: {y_train.max():.3f}")
print(f"Test Y  - Mean: {y_test.mean():.3f}, Std: {y_test.std():.3f}, Min: {y_test.min():.3f}, Max: {y_test.max():.3f}")

if abs(y_train.mean() - y_test.mean()) / y_train.std() > 0.1:
    print("⚠️ WARNING: Trung bình Y khác đáng kể giữa train và test!")

# 2. Check for data drift in features
print("\n2. DATA DRIFT - So sánh phân bố giữa Train & Test")
print("-" * 50)
drift_cols = []
for col in X_train.select_dtypes(include=np.number).columns:
    train_mean = X_train[col].mean()
    test_mean = X_test[col].mean()
    train_std = X_train[col].std()
    
    if train_std > 0:
        normalized_diff = abs(train_mean - test_mean) / train_std
        if normalized_diff > 0.3:  # > 0.3 std differences
            drift_cols.append((col, normalized_diff))

if drift_cols:
    print(f"✗ {len(drift_cols)} columns có data drift đáng kể (>0.3 std):")
    for col, diff in sorted(drift_cols, key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {col}: {diff:.3f} std")
else:
    print("✓ Phân bố features khá nhất quán giữa train và test")

# 3. Feature importance analysis
print("\n3. PHÂN TÍCH FEATURES")
print("-" * 50)
print(f"Train: {X_train.shape[1]} features, {X_train.shape[0]} mẫu")
print(f"Test:  {X_test.shape[1]} features, {X_test.shape[0]} mẫu")
print(f"Tỷ lệ Train:Test = {X_train.shape[0] / X_test.shape[0]:.2f}:1")

# Check correlation between features and target
print("\nTop 10 features tương quan mạnh nhất với Y (train):")
train_full = X_train.copy()
train_full['Y'] = y_train
corr = train_full.corr()['Y'].abs().drop('Y').sort_values(ascending=False).head(10)
for feat, val in corr.items():
    print(f"  - {feat}: {val:.4f}")

# 4. Check for outliers
print("\n4. PHÁT HIỆN OUTLIERS")
print("-" * 50)
y_train_q1, y_train_q3 = np.percentile(y_train, [25, 75])
y_train_iqr = y_train_q3 - y_train_q1
train_outliers = np.sum((y_train < y_train_q1 - 1.5 * y_train_iqr) | (y_train > y_train_q3 + 1.5 * y_train_iqr))

y_test_q1, y_test_q3 = np.percentile(y_test, [25, 75])
y_test_iqr = y_test_q3 - y_test_q1
test_outliers = np.sum((y_test < y_test_q1 - 1.5 * y_test_iqr) | (y_test > y_test_q3 + 1.5 * y_test_iqr))

print(f"Train outliers: {train_outliers} ({100*train_outliers/len(y_train):.1f}%)")
print(f"Test outliers:  {test_outliers} ({100*test_outliers/len(y_test):.1f}%)")

# 5. Class distribution (for regression, check yield ranges)
print("\n5. PHÂN BỐ YIELD")
print("-" * 50)
print("Train yield distribution:")
for i, (q, val) in enumerate([(0, y_train.min()), (0.25, np.percentile(y_train, 25)), 
                              (0.5, np.percentile(y_train, 50)), (0.75, np.percentile(y_train, 75)),
                              (1.0, y_train.max())]):
    print(f"  {q:.0%}: {val:.3f}")

print("\nTest yield distribution:")
for i, (q, val) in enumerate([(0, y_test.min()), (0.25, np.percentile(y_test, 25)), 
                              (0.5, np.percentile(y_test, 50)), (0.75, np.percentile(y_test, 75)),
                              (1.0, y_test.max())]):
    print(f"  {q:.0%}: {val:.3f}")

print("\n" + "=" * 80)
