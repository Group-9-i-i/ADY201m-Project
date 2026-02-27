import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import cross_val_predict, KFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from scipy.stats import pearsonr
import joblib

print("="*80)
print("🏆 STACKING ENSEMBLE - Combining Multiple Strong Learners")
print("="*80)

# Load
X_train = pd.read_csv('X_train.csv').apply(pd.to_numeric, errors='coerce')
y_train = pd.read_csv('y_train.csv').values.ravel()
X_test = pd.read_csv('X_test.csv').apply(pd.to_numeric, errors='coerce')
y_test = pd.read_csv('y_test.csv').values.ravel()

print(f"\n[1/3] Preprocessing...")
X_train = X_train.fillna(X_train.median())
X_test = X_test.fillna(X_train.median())

for col in X_train.columns:
    X_train[col] = X_train[col].replace([np.inf, -np.inf], X_train[col].median())
    X_test[col] = X_test[col].replace([np.inf, -np.inf], X_test[col].median())

for col in X_train.columns:
    p95, p05 = X_train[col].quantile(0.95), X_train[col].quantile(0.05)
    X_train[col] = X_train[col].clip(p05, p95)
    X_test[col] = X_test[col].clip(p05, p95)

scaler = StandardScaler()
X_train = pd.DataFrame(scaler.fit_transform(X_train), columns=X_train.columns)
X_test = pd.DataFrame(scaler.transform(X_test), columns=X_test.columns)

print(f"[2/3] Training base learners with stacking...")
kf = KFold(n_splits=5, shuffle=True, random_state=42)

# Base learners
base_learners = [
    ('xgb1', XGBRegressor(n_estimators=1200, max_depth=7, learning_rate=0.01, subsample=0.7, colsample_bytree=0.7, reg_lambda=2, reg_alpha=1, random_state=42, n_jobs=-1)),
    ('xgb2', XGBRegressor(n_estimators=1000, max_depth=6, learning_rate=0.02, subsample=0.8, colsample_bytree=0.8, reg_lambda=1, reg_alpha=0.5, random_state=43, n_jobs=-1)),
    ('xgb3', XGBRegressor(n_estimators=800, max_depth=8, learning_rate=0.015, subsample=0.75, colsample_bytree=0.75, reg_lambda=1.5, reg_alpha=0.5, random_state=44, n_jobs=-1)),
    ('gbm', GradientBoostingRegressor(n_estimators=500, max_depth=7, learning_rate=0.1, subsample=0.8, random_state=42)),
    ('rf', RandomForestRegressor(n_estimators=300, max_depth=15, max_features='sqrt', random_state=42, n_jobs=-1)),
]

# Generate meta-features
X_meta_train = np.zeros((X_train.shape[0], len(base_learners)))
X_meta_test = np.zeros((X_test.shape[0], len(base_learners)))

for i, (name, model) in enumerate(base_learners):
    print(f"  Training {name}...", end=" ")
    X_meta_train[:, i] = cross_val_predict(model, X_train, y_train, cv=kf, n_jobs=-1)
    model.fit(X_train, y_train)
    X_meta_test[:, i] = model.predict(X_test)
    print("✓")

# Meta-learner
print(f"  Training meta-learner (Ridge)...")
meta_model = Ridge(alpha=1.0)
meta_model.fit(X_meta_train, y_train)

# Predictions
y_train_pred = meta_model.predict(X_meta_train)
y_test_pred = meta_model.predict(X_meta_test)

# Metrics
r2_train = r2_score(y_train, y_train_pred)
r2_test = r2_score(y_test, y_test_pred)
mse_train = mean_squared_error(y_train, y_train_pred)
mse_test = mean_squared_error(y_test, y_test_pred)
_, p_train = pearsonr(y_train, y_train_pred)
_, p_test = pearsonr(y_test, y_test_pred)

print("\n[3/3] FINAL STACKING RESULTS:")
print("="*80)
print("\nTRAIN:")
print(f"  R²       : {r2_train:.4f}")
print(f"  MSE      : {mse_train:.8f}")
print(f"  p-value  : {p_train:.3e}")

print("\nTEST (PRIMARY):")
status = "🎉 TARGET ACHIEVED!" if r2_test >= 0.80 else f"📈 {r2_test:.1%}"
print(f"  R²       : {r2_test:.4f} {status}")
print(f"  MSE      : {mse_test:.8f}")
print(f"  p-value  : {p_test:.3e}")

print(f"\nGeneralization Gap: {abs(r2_train-r2_test):.4f}")
print("="*80)

# Save
joblib.dump({
    'meta_model': meta_model,
    'base_learners': base_learners,
    'scaler': scaler
}, 'xgb_model_ensemble.joblib')

print("\n✅ Stacking ensemble saved to xgb_model_ensemble.joblib")
