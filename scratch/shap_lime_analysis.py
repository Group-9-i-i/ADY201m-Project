import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
import shap
import lime
import lime.lime_tabular
import json
import warnings
warnings.filterwarnings('ignore')

def main():
    # Load Data
    df = pd.read_csv(r"C:\Users\hachimi\Documents\GitHub\ADY201m-Project\Data Cleaning\Bangladesh_database_Final_Merged.csv")
    
    # Target and Data Leakage
    target_col = 'NDVI_Season_Mean'
    # Drop other NDVI columns to prevent trivial prediction
    leakage_cols = ['NDVI_Season_Max', 'NDVI_Season_Min', 'NDVI_Season_Std', 'NDVI_Season_Range', 'NDVI_Season_CV']
    if 'Production' in df.columns:
        # Based on previous conversation, 'Production' might be data leakage for other tasks, but for NDVI it's okay, maybe keep it.
        pass
        
    df = df.drop(columns=[col for col in leakage_cols if col in df.columns])
    
    # Separate categorical and numerical
    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    # Label encode categorical columns
    le_dict = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        le_dict[col] = le
        
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    # Train Model
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    
    # 1. SHAP Analysis
    explainer = shap.TreeExplainer(rf)
    # Using a sample to speed up SHAP
    X_sample = shap.sample(X_train, 100)
    shap_values = explainer.shap_values(X_sample)
    
    # Calculate global SHAP importance (mean absolute SHAP value)
    shap_importance = np.abs(shap_values).mean(axis=0)
    shap_df = pd.DataFrame({'Feature': X.columns, 'SHAP_Importance': shap_importance})
    shap_df = shap_df.sort_values(by='SHAP_Importance', ascending=False)
    
    # 2. LIME Analysis
    # LIME is local, so we'll average over a sample to get "global" proxy
    lime_explainer = lime.lime_tabular.LimeTabularExplainer(
        X_train.values, 
        feature_names=X_train.columns, 
        class_names=[target_col], 
        verbose=False, 
        mode='regression',
        categorical_features=[X.columns.get_loc(c) for c in cat_cols]
    )
    
    lime_importances = np.zeros(X_train.shape[1])
    # Average LIME absolute weights over 100 instances
    for i in range(100):
        exp = lime_explainer.explain_instance(X_test.iloc[i].values, rf.predict, num_features=len(X.columns))
        for feature_idx, weight in exp.local_exp[1]:
            lime_importances[feature_idx] += abs(weight)
            
    lime_importances /= 100
    lime_df = pd.DataFrame({'Feature': X.columns, 'LIME_Importance': lime_importances})
    lime_df = lime_df.sort_values(by='LIME_Importance', ascending=False)
    
    # Merge SHAP and LIME
    merged_imp = pd.merge(shap_df, lime_df, on='Feature')
    
    # Rank by sum of normalized ranks
    merged_imp['SHAP_Rank'] = merged_imp['SHAP_Importance'].rank(ascending=False)
    merged_imp['LIME_Rank'] = merged_imp['LIME_Importance'].rank(ascending=False)
    merged_imp['Avg_Rank'] = (merged_imp['SHAP_Rank'] + merged_imp['LIME_Rank']) / 2
    merged_imp = merged_imp.sort_values(by='Avg_Rank')
    
    # Output top and bottom features
    result = {
        'all_features': merged_imp['Feature'].tolist(),
        'feature_stats': merged_imp.to_dict(orient='records')
    }
    
    with open(r"C:\Users\hachimi\Documents\GitHub\ADY201m-Project\scratch\shap_lime_results.json", 'w') as f:
        json.dump(result, f, indent=4)
        
    print("Analysis complete. Saved to scratch/shap_lime_results.json")

if __name__ == "__main__":
    main()
