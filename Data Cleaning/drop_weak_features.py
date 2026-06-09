import pandas as pd
import os

def main():
    # File paths
    input_file = r"C:\Users\hachimi\Documents\GitHub\ADY201m-Project\Data Cleaning\Bangladesh_database_Final_Merged.csv"
    output_file = r"C:\Users\hachimi\Documents\GitHub\ADY201m-Project\Data Cleaning\Bangladesh_database_Final_Merged_30features.csv"
    
    print(f"Reading dataset from: {input_file}")
    df = pd.read_csv(input_file)
    
    print(f"Original shape: {df.shape}")
    
    # Features to Keep (removed Latitude and Longitude)
    features_to_keep = [
        'FPAR', 'Avg_Salinity_Index', 'EVI', 'Rain_Temp_Ratio', 'Rainfall', 
        'Wind_Mean', 'Temp_Min', 'Wind_Max', 'Temp_Max', 
        'District', 'Clay', 'LAI', 'Nitrogen', 
        'Soil_Moisture_mm', 'pH', 'LST_Kelvin', 'Dominant_Soil_Texture', 'AP Ratio', 
        'Temp_Mean', 'Avg Humidity', 'Heat_Stress_Days', 'Silt', 'Growth', 
        'CN_Ratio', 'Crop Name', 'Organic_Carbon', 'Transplant', 'Season'
    ]
    
    # Target columns (Keeping only NDVI_Season_Mean as requested)
    targets_to_keep = [
        'NDVI_Season_Mean'
    ]
    
    # Select columns
    final_columns = features_to_keep + targets_to_keep
    
    # Identify which columns are being dropped just for logging
    dropped_columns = [col for col in df.columns if col not in final_columns]
    print(f"\nDropping {len(dropped_columns)} columns: {dropped_columns}")
    
    # Create final dataframe
    df_final = df[final_columns]
    
    # Save to new CSV
    df_final.to_csv(output_file, index=False)
    print(f"\nSaved new dataset with shape {df_final.shape} to: {output_file}")
    print(f"- Number of features: {len(features_to_keep)}")
    print(f"- Number of targets: {len(targets_to_keep)}")

if __name__ == "__main__":
    main()
