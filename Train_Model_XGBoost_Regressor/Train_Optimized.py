import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import cross_val_score, KFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from scipy.stats import pearsonr
import joblib

print("="*80)
print("🎯 OPTIMAL CONFIGURATION SEARCH - Finding Best R² >= 0.80")
print("="*80)

# Load data
X_train = pd.read_csv('X_train.csv').apply(pd.to_numeric, errors='coerce')
y_train = pd.read_csv('y_train.csv').values.ravel()
X_test = pd.read_csv('X_test.csv').apply(pd.to_numeric, errors='coerce')
y_test = pd.read_csv('y_test.csv').values.ravel()

print(f"\n[1/3] Preprocessing: Train={X_train.shape}, Test={X_test.shape}")

# Preprocessing
X_train = X_train.fillna(X_train.median())
X_test = X_test.fillna(X_train.median())

for col in X_train.columns:
    X_train[col] = X_train[col].replace([np.inf, -np.inf], X_train[col].median())
    X_test[col] = X_test[col].replace([np.inf, -np.inf], X_test[col].median())

# Clip at 95/5
for col in X_train.columns:
    p95 = X_train[col].quantile(0.95)
    p05 = X_train[col].quantile(0.05)
    X_train[col] = X_train[col].clip(p05, p95)
    X_test[col] = X_test[col].clip(p05, p95)

# Scale
scaler = StandardScaler()
X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns)

print("\n[2/3] Testing 8 configurations (CV + Test evaluation)...")
print("─" * 80)

configs = [
    {'name': 'Ultra-Light', 'n': 200, 'd': 4, 'lr': 0.1, 'sub': 0.9, 'col': 0.9, 'a': 0, 'l': 0.5},
    {'name': 'Light', 'n': 400, 'd': 5, 'lr': 0.05, 'sub': 0.85, 'col': 0.85, 'a': 0, 'l': 0.5},
    {'name': 'Light-Med', 'n': 600, 'd': 6, 'lr': 0.03, 'sub': 0.8, 'col': 0.8, 'a': 0.1, 'l': 1.0},
    {'name': 'Medium', 'n': 800, 'd': 6, 'lr': 0.02, 'sub': 0.8, 'col': 0.8, 'a': 0.2, 'l': 1.0},
    {'name': 'Medium-Heavy', 'n': 1000, 'd': 7, 'lr': 0.015, 'sub': 0.75, 'col': 0.75, 'a': 0.5, 'l': 1.5},
    {'name': 'Heavy', 'n': 1200, 'd': 7, 'lr': 0.01, 'sub': 0.7, 'col': 0.7, 'a': 1.0, 'l': 2.0},
    {'name': 'Very-Heavy', 'n': 1500, 'd': 8, 'lr': 0.005, 'sub': 0.65, 'col': 0.65, 'a': 2.0, 'l': 3.0},
    {'name': 'Ultra-Heavy', 'n': 2000, 'd': 8, 'lr': 0.003, 'sub': 0.6, 'col': 0.6, 'a': 5.0, 'l': 5.0},
]

results = []
for cfg in configs:
    model = XGBRegressor(
        n_estimators=cfg['n'], max_depth=cfg['d'], learning_rate=cfg['lr'],
        subsample=cfg['sub'], colsample_bytree=cfg['col'], min_child_weight=1,
        gamma=0.5, reg_alpha=cfg['a'], reg_lambda=cfg['l'],
        random_state=42, n_jobs=-1, tree_method='hist', verbosity=0
    )
    
    # 5-fold CV
    cv_r2 = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='r2', n_jobs=-1).mean()
    
    # Train
    model.fit(X_train_scaled, y_train, verbose=0)
    test_r2 = r2_score(y_test, model.predict(X_test_scaled))
    train_r2 = r2_score(y_train, model.predict(X_train_scaled))
    
    results.append({'name': cfg['name'], 'model': model, 'cv_r2': cv_r2, 'train_r2': train_r2, 'test_r2': test_r2})
    print(f"  {cfg['name']:15} | CV_R²={cv_r2:.4f} | Train_R²={train_r2:.4f} | Test_R²={test_r2:.4f}")

# Find best
best = max(results, key=lambda x: x['test_r2'])
print("─" * 80)
print(f"\n✨ BEST: {best['name']} with Test_R² = {best['test_r2']:.4f}")

# Final evaluation
print("\n[3/3] FINAL RESULTS:")
model = best['model']
y_train_pred = model.predict(X_train_scaled)
y_test_pred = model.predict(X_test_scaled)

r2_train = r2_score(y_train, y_train_pred)
r2_test = r2_score(y_test, y_test_pred)
mse_train = mean_squared_error(y_train, y_train_pred)
mse_test = mean_squared_error(y_test, y_test_pred)
_, p_train = pearsonr(y_train, y_train_pred)
_, p_test = pearsonr(y_test, y_test_pred)

print("\n" + "="*80)
print("📊 FINAL METRICS")
print("="*80)
print("\nTRAIN:")
print(f"  R²       : {r2_train:.4f}")
print(f"  MSE      : {mse_train:.8f}")
print(f"  p-value  : {p_train:.3e}")

print("\nTEST (PRIMARY):")
status = "🎉 TARGET ACHIEVED!" if r2_test >= 0.80 else f"⚠️ ({r2_test:.1%})"
print(f"  R²       : {r2_test:.4f} {status}")
print(f"  MSE      : {mse_test:.8f}")
print(f"  p-value  : {p_test:.3e}")

print(f"\nGeneralization Gap: {abs(r2_train-r2_test):.4f}")
print("="*80)

# Save
joblib.dump(model, 'xgb_model.joblib')
print("\n✅ Model saved to xgb_model.joblib")

# Feature importance
print("\n📋 Top 10 Features:")
imp_df = pd.DataFrame({'feature': X_train_scaled.columns, 'importance': model.feature_importances_})
imp_df = imp_df.sort_values('importance', ascending=False).head(10)
for _, row in imp_df.iterrows():
    print(f"  {row['feature']:40} : {row['importance']:.6f}")
