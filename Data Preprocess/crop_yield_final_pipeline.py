"""
╔══════════════════════════════════════════════════════════════════╗
║          CROP YIELD REGRESSION — FINAL PIPELINE                 ║
║          Validated qua 8 vòng thực nghiệm + phản biện           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold
import warnings
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════
MONTH_MAP = {
    'January':1,  'February':2,  'March':3,    'April':4,
    'May':5,      'June':6,      'July':7,      'August':8,
    'September':9,'October':10,  'November':11, 'December':12
}

DROP_COLS = ['Area', 'Production', 'Yield', 'Growth', 'Harvest', 'Transplant']

CAT_COLS = [
    'District', 'Season', 'Crop Name',
    'Dominant_Soil_Texture', 'Water_Availability_Cat',
    'Extreme_Heat_Risk', 'pH_Suitability'
]


# ══════════════════════════════════════════════════════════════════
# 1. LOAD & VALIDATE
# ══════════════════════════════════════════════════════════════════
def load_and_validate(train_path, test_path):
    train = pd.read_csv(train_path)
    test  = pd.read_csv(test_path)

    print("=" * 65)
    print("CROP YIELD REGRESSION — FINAL PIPELINE")
    print("=" * 65)
    print(f"\nTrain: {train.shape} | Test: {test.shape}")
    
    # Check leakage
    leak_check = (train['Production'] / train['Area'] - train['Yield']).abs()
    pct_exact = (leak_check < 0.01).mean()
    print(f"✓ Leakage check: Production/Area ≈ Yield in {pct_exact:.1%} of rows")

    return train, test


# ══════════════════════════════════════════════════════════════════
# 2. FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════
def engineer_features(df):
    d = df.copy()

    def first_month(s):
        return MONTH_MAP.get(str(s).split()[0], np.nan)

    d['Transplant_Month']   = d['Transplant'].apply(first_month)
    d['Harvest_StartMonth'] = d['Harvest'].apply(first_month)
    d['Cycle_Length'] = (d['Harvest_StartMonth'] - d['Transplant_Month']) % 12
    
    # Interactions
    d['NDVI_x_LAI']      = d['NDVI_Season_Mean'] * d['LAI']
    d['Temp_x_Humidity'] = d['Avg Temp'] * d['Max Relative Humidity']

    return d


# ══════════════════════════════════════════════════════════════════
# 3. PREPROCESSING
# ══════════════════════════════════════════════════════════════════
def preprocess(train_df, test_df):
    tr = train_df.drop(DROP_COLS, axis=1).copy()
    te = test_df.drop(DROP_COLS, axis=1).copy()

    encoders = {}
    for c in CAT_COLS:
        if c not in tr.columns:
            continue
        le = LabelEncoder().fit(pd.concat([tr[c], te[c]]).astype(str))
        tr[c] = le.transform(tr[c].astype(str))
        te[c] = le.transform(te[c].astype(str))
        encoders[c] = le

    imp = SimpleImputer(strategy='median')
    Xtr = imp.fit_transform(tr)
    Xte = imp.transform(te)

    return Xtr, Xte, tr.columns.tolist(), encoders, imp


# ══════════════════════════════════════════════════════════════════
# 4. MODELS
# ══════════════════════════════════════════════════════════════════
def build_models():
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=16,
        min_samples_leaf=3,
        max_features='sqrt',
        n_jobs=-1,
        random_state=42
    )
    hgb = HistGradientBoostingRegressor(
        max_iter=200,
        max_depth=7,
        learning_rate=0.05,
        min_samples_leaf=20,
        random_state=42
    )
    return rf, hgb


# ══════════════════════════════════════════════════════════════════
# 5. CROSS VALIDATION
# ══════════════════════════════════════════════════════════════════
def run_cv(model, X, y, model_name="Model", n_splits=5):
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = []
    for fi, fv in kf.split(X):
        m = model.__class__(**model.get_params())
        m.fit(X[fi], y[fi])
        pred = m.predict(X[fv])
        r2 = 1 - np.sum((y[fv]-pred)**2) / np.sum((y[fv]-y[fv].mean())**2)
        scores.append(r2)
    scores = np.array(scores)
    print(f"  {model_name} CV R²: {scores.mean():.4f} ± {scores.std():.4f}")
    return scores


# ══════════════════════════════════════════════════════════════════
# 6. EVALUATION (UPDATED)
# ══════════════════════════════════════════════════════════════════
def evaluate(y_true, y_pred, label="", indent="  "):
    # Calculate Metrics
    mse  = np.mean((y_true - y_pred)**2)       # Mean Squared Error
    mae  = np.mean(np.abs(y_true - y_pred))    # Mean Absolute Error
    r2   = 1 - np.sum((y_true-y_pred)**2) / np.sum((y_true-y_true.mean())**2)
    
    # Print formatted
    print(f"{indent}{label:25s} | R²={r2:.4f} | MSE={mse:.4f} | MAE={mae:.4f}")
    return r2, mse, mae


# ══════════════════════════════════════════════════════════════════
# 7. MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════
def run_pipeline(train_path, test_path):

    # ── Load & validate ──────────────────────────────────────────
    train, test = load_and_validate(train_path, test_path)
    y_train = train['Yield'].values
    y_test  = test['Yield'].values

    # ── Feature engineering ──────────────────────────────────────
    print("\n[1] Feature Engineering")
    train_fe = engineer_features(train)
    test_fe  = engineer_features(test)

    # ── Preprocessing ────────────────────────────────────────────
    print("\n[2] Preprocessing")
    X_train, X_test, feat_names, encoders, imp = preprocess(train_fe, test_fe)

    # ── Cross validation ─────────────────────────────────────────
    print("\n[3] Cross Validation (KFold-5)")
    rf, hgb = build_models()
    cv_rf  = run_cv(rf,  X_train, y_train, "RandomForest")
    cv_hgb = run_cv(hgb, X_train, y_train, "HGB")

    # ── Train final models ───────────────────────────────────────
    print("\n[4] Training Final Models")
    rf.fit(X_train, y_train)
    hgb.fit(X_train, y_train)
    
    # ── Predict (Train & Test) ───────────────────────────────────
    # Predict on Train (to see fitting score)
    p_rf_train  = rf.predict(X_train)
    p_hgb_train = hgb.predict(X_train)
    p_avg_train = (p_rf_train + p_hgb_train) / 2
    
    # Predict on Test
    p_rf_test  = rf.predict(X_test)
    p_hgb_test = hgb.predict(X_test)
    p_avg_test = (p_rf_test + p_hgb_test) / 2

    # ── Evaluate (CLEAR OUTPUT SECTION) ──────────────────────────
    print("\n" + "═"*65)
    print(" FINAL EVALUATION RESULTS (TRAIN vs TEST)")
    print("═"*65)
    
    print("\n>>> TRAINING SET METRICS (Self-Check):")
    evaluate(y_train, p_rf_train,  "RF Train")
    evaluate(y_train, p_hgb_train, "HGB Train")
    evaluate(y_train, p_avg_train, "Ensemble Train")
    
    print("\n>>> TEST SET METRICS (Generalization):")
    evaluate(y_test, p_rf_test,  "RF Test")
    evaluate(y_test, p_hgb_test, "HGB Test")
    evaluate(y_test, p_avg_test, "Ensemble Test")

    # ── OOD analysis (Optional but kept for context) ─────────────
    train_max = y_train.max()
    in_dist   = y_test <= train_max
    
    print("\n>>> TEST SET (Excluding OOD / Outliers):")
    evaluate(y_test[in_dist], p_avg_test[in_dist], "Ensemble (No OOD)")

    print("-" * 65)
    return {
        'rf': rf, 'hgb': hgb,
        'cv_score': cv_rf.mean(),
        'train_score': 1 - np.sum((y_train-p_avg_train)**2)/np.sum((y_train-y_train.mean())**2),
        'test_score': 1 - np.sum((y_test-p_avg_test)**2)/np.sum((y_test-y_test.mean())**2)
    }


# ══════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Thay đổi đường dẫn file nếu cần thiết
    results = run_pipeline(
        train_path='Agri_Train_Combined_16k.csv', 
        test_path='Agri_Test_Original_4k.csv'
    )