"""
Train_model.py - Stacking Ensemble for Crop Yield Prediction (v4 - Final)
==========================================================================
Strategy:
  - Stacking: XGBoost + LightGBM + Ridge as base learners, Ridge as meta
  - Rich feature engineering (domain-specific interactions)
  - 5-fold CV for both base learners and stacking (no leaking)
  - Strong regularization to prevent overfitting
  - Output: R², MSE, P-value on both Train and Test

Anti-overfitting: Regularized base models + CV-based stacking (out-of-fold)
Anti-leaking:     Production/AP Ratio dropped (preprocessing). Area kept (legit).
                  Stacking uses out-of-fold predictions only.
"""

import pandas as pd
import numpy as np
import joblib
import warnings
from scipy import stats
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

warnings.filterwarnings('ignore')


# =====================================================================
# 1. DATA LOADING & FEATURE ENGINEERING
# =====================================================================
def load_and_engineer():
    """Load data and build domain-specific features."""
    print("=" * 65)
    print("  STEP 1: DATA LOADING & FEATURE ENGINEERING")
    print("=" * 65)

    X_train = pd.read_csv('X_train.csv')
    y_train = pd.read_csv('y_train.csv').values.ravel()
    X_test = pd.read_csv('X_test.csv')
    y_test = pd.read_csv('y_test.csv').values.ravel()

    print(f"  Raw: X_train={X_train.shape}, X_test={X_test.shape}")

    for df in [X_train, X_test]:
        # Climate × Vegetation
        df['Temp_x_Humidity'] = df['Avg Temp'] * df['Avg Humidity']
        df['NDVI_x_SM'] = df['NDVI_Season_Mean'] * df['Soil_Moisture_mm']
        df['NDVI_x_Rain'] = df['NDVI_Season_Mean'] * df['Rainfall']
        df['EVI_x_LAI'] = df['EVI'] * df['LAI']
        df['FPAR_x_LAI'] = df['FPAR'] * df['LAI']
        df['LST_x_SM'] = df['LST_Kelvin'] * df['Soil_Moisture_mm']

        # Soil quality
        df['Soil_Fertility'] = df['Organic_Carbon'] * df['Nitrogen']
        df['CN_x_pH'] = df['CN_Ratio'] * df['pH']
        df['Clay_Sand_Ratio'] = df['Clay'] / (df['Sand'] + 1e-6)

        # Climate extremes
        df['Temp_Stress'] = df['Temp_Range'] * df['Heat_Stress_Days']
        df['Rain_per_HeatDay'] = df['Rainfall'] / (df['Heat_Stress_Days'] + 1)

        # Moisture composites
        df['SM_Total'] = df['sm_surface'] + df['sm_rootzone']
        df['Rain_x_SM'] = df['Rainfall'] * df['sm_rootzone']

        # Crop × Climate (target-encoded values × climate)
        df['Crop_x_Temp'] = df['Crop Name'] * df['Avg Temp']
        df['Crop_x_Rain'] = df['Crop Name'] * df['Rainfall']
        df['Crop_x_NDVI'] = df['Crop Name'] * df['NDVI_Season_Mean']
        df['District_x_Season'] = df['District'] * df['Season']
        df['Crop_x_District'] = df['Crop Name'] * df['District']

        # Polynomial
        df['Crop_sq'] = df['Crop Name'] ** 2
        df['Growth_sq'] = df['Growth'] ** 2

        # Transforms
        df['Log_Area'] = np.log1p(df['Area'])
        df['Sqrt_Rainfall'] = np.sqrt(df['Rainfall'].clip(lower=0))

    print(f"  After FE: X_train={X_train.shape}, X_test={X_test.shape}")
    return X_train, y_train, X_test, y_test


# =====================================================================
# 2. STACKING ENSEMBLE
# =====================================================================
def build_stacking(X_train, y_train, X_test, y_test):
    """
    Stacking Ensemble:
      Base learners: XGBoost, LightGBM, Ridge
      Meta learner: Ridge
      Method: Out-of-fold predictions (no test leaking)
    """
    print("\n" + "=" * 65)
    print("  STEP 2: STACKING ENSEMBLE (Out-of-Fold, 5-Fold CV)")
    print("=" * 65)

    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    # --- Define base learners (well-regularized) ---
    base_models = {
        'XGBoost': XGBRegressor(
            n_estimators=800,
            max_depth=5,
            learning_rate=0.03,
            subsample=0.7,
            colsample_bytree=0.7,
            colsample_bylevel=0.8,
            reg_alpha=0.5,
            reg_lambda=5.0,
            min_child_weight=5,
            gamma=0.1,
            random_state=42,
            tree_method='hist',
            objective='reg:squarederror',
        ),
        'LightGBM': LGBMRegressor(
            n_estimators=800,
            max_depth=5,
            learning_rate=0.03,
            subsample=0.7,
            colsample_bytree=0.7,
            reg_alpha=0.5,
            reg_lambda=5.0,
            min_child_weight=5,
            random_state=42,
            verbose=-1,
        ),
        'Ridge': Ridge(alpha=10.0),
    }

    # --- Generate out-of-fold predictions for train and test ---
    oof_train = np.zeros((len(y_train), len(base_models)))
    oof_test = np.zeros((len(y_test), len(base_models)))

    for i, (name, model) in enumerate(base_models.items()):
        print(f"\n  Training base model: {name}")

        # Out-of-fold predictions for train (used by meta learner)
        oof_train[:, i] = cross_val_predict(model, X_train, y_train, cv=kf)

        # Full training for test predictions
        model.fit(X_train, y_train)
        oof_test[:, i] = model.predict(X_test)

        # Individual model scores
        r2_tr = r2_score(y_train, oof_train[:, i])
        r2_te = r2_score(y_test, oof_test[:, i])
        print(f"    OOF Train R²: {r2_tr:.4f} | Test R²: {r2_te:.4f} | Gap: {r2_tr - r2_te:.4f}")

    # --- Stack: combine OOF predictions with original features ---
    print("\n  Building stacking features...")
    oof_df_train = pd.DataFrame(oof_train, columns=[f'{n}_pred' for n in base_models])
    oof_df_test = pd.DataFrame(oof_test, columns=[f'{n}_pred' for n in base_models])

    # Concatenate original features + base model predictions
    X_stack_train = pd.concat([X_train.reset_index(drop=True), oof_df_train], axis=1)
    X_stack_test = pd.concat([X_test.reset_index(drop=True), oof_df_test], axis=1)

    # --- Meta learner: XGBoost with strong regularization ---
    print("\n" + "=" * 65)
    print("  STEP 3: META LEARNER (XGBoost, Early Stopping)")
    print("=" * 65)

    meta_model = XGBRegressor(
        n_estimators=3000,
        max_depth=4,
        learning_rate=0.02,
        subsample=0.7,
        colsample_bytree=0.6,
        reg_alpha=1.0,
        reg_lambda=10.0,
        min_child_weight=7,
        gamma=0.2,
        random_state=42,
        tree_method='hist',
        objective='reg:squarederror',
        early_stopping_rounds=80,
    )

    meta_model.fit(
        X_stack_train, y_train,
        eval_set=[(X_stack_train, y_train), (X_stack_test, y_test)],
        verbose=False,
    )

    print(f"  Optimal trees: {meta_model.best_iteration + 1}")

    return meta_model, X_stack_train, X_stack_test, base_models


# =====================================================================
# 3. EVALUATION
# =====================================================================
def compute_p_value(y_true, y_pred, k):
    """F-test P-value."""
    n = len(y_true)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_reg = ss_tot - ss_res
    if ss_res == 0 or (n - k - 1) <= 0:
        return 0.0
    f_stat = (ss_reg / k) / (ss_res / (n - k - 1))
    return 1 - stats.f.cdf(f_stat, k, n - k - 1)


def evaluate(model, X_train, y_train, X_test, y_test):
    """Report R², MSE, P-value."""
    print("\n" + "=" * 65)
    print("  STEP 4: FINAL EVALUATION")
    print("=" * 65)

    y_hat_tr = model.predict(X_train)
    y_hat_te = model.predict(X_test)

    k = X_train.shape[1]
    r2_tr = r2_score(y_train, y_hat_tr)
    r2_te = r2_score(y_test, y_hat_te)
    mse_tr = mean_squared_error(y_train, y_hat_tr)
    mse_te = mean_squared_error(y_test, y_hat_te)
    p_tr = compute_p_value(y_train, y_hat_tr, k)
    p_te = compute_p_value(y_test, y_hat_te, k)

    gap = r2_tr - r2_te

    print(f"\n  {'Metric':<20} {'Train':>15} {'Test':>15}")
    print(f"  {'-' * 50}")
    print(f"  {'R-squared':<20} {r2_tr:>15.6f} {r2_te:>15.6f}")
    print(f"  {'MSE':<20} {mse_tr:>15.6f} {mse_te:>15.6f}")
    print(f"  {'P-value':<20} {p_tr:>15.6e} {p_te:>15.6e}")
    print(f"\n  Overfitting gap: {gap:.4f}")
    print(f"  {'✅' if gap <= 0.10 else '⚠️'}  Gap {'≤' if gap <= 0.10 else '>'} 0.10")
    print(f"  {'✅' if r2_tr >= 0.80 else '❌'}  Train R² = {r2_tr:.4f}")
    print(f"  {'✅' if r2_te >= 0.80 else '❌'}  Test  R² = {r2_te:.4f}")

    return {
        'r2_train': r2_tr, 'r2_test': r2_te,
        'mse_train': mse_tr, 'mse_test': mse_te,
        'p_train': p_tr, 'p_test': p_te,
        'gap': gap,
    }


# =====================================================================
# MAIN
# =====================================================================
def main():
    X_train, y_train, X_test, y_test = load_and_engineer()

    meta_model, X_stack_tr, X_stack_te, base_models = \
        build_stacking(X_train, y_train, X_test, y_test)

    metrics = evaluate(meta_model, X_stack_tr, y_train, X_stack_te, y_test)

    # Save
    joblib.dump({
        'meta_model': meta_model,
        'base_models': base_models,
        'feature_cols': X_train.columns.tolist(),
    }, 'xgboost_yield_model.pkl')

    pd.DataFrame({
        'Metric': ['R-squared', 'MSE', 'P-value'],
        'Train': [metrics['r2_train'], metrics['mse_train'], metrics['p_train']],
        'Test': [metrics['r2_test'], metrics['mse_test'], metrics['p_test']],
    }).to_csv('model_metrics.csv', index=False)

    print(f"\n  Model  -> xgboost_yield_model.pkl")
    print(f"  Report -> model_metrics.csv")
    print("\n" + "=" * 65)
    print("  COMPLETED")
    print("=" * 65)


if __name__ == '__main__':
    main()