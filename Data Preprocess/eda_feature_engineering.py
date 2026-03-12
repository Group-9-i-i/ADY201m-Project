"""EDA + feature engineering pipeline cho dữ liệu Agri_Data_Cleaned.

Cách chạy:
    python 'Data Preprocess/eda_feature_engineering.py' \
        --input 'Data Preprocess/Agri_Data_Cleaned.csv' \
        --output-dir 'Data Preprocess/outputs'
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EDA + Feature Engineering cho Agri Cleaned data")
    parser.add_argument("--input", required=True, help="CSV input path")
    parser.add_argument("--output-dir", required=True, help="Folder lưu file output")
    parser.add_argument("--target", default="Yield", help="Tên cột target (default: Yield)")
    parser.add_argument(
        "--low-cardinality-threshold",
        type=int,
        default=12,
        help="Ngưỡng unique values để one-hot encoding",
    )
    return parser.parse_args()


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / (denominator.replace(0, np.nan))


def generate_eda_report(df: pd.DataFrame, target: str) -> str:
    missing = (df.isna().mean() * 100).sort_values(ascending=False)
    duplicated_rows = int(df.duplicated().sum())

    lines = []
    lines.append("=== EDA REPORT ===")
    lines.append(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    lines.append(f"Duplicate rows: {duplicated_rows}")
    lines.append("\nTop 15 cột thiếu dữ liệu (%):")

    for col, pct in missing.head(15).items():
        lines.append(f"- {col}: {pct:.2f}%")

    if target in df.columns:
        target_desc = df[target].describe()
        lines.append(f"\nTarget: {target}")
        lines.append(target_desc.to_string())

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    if target in numeric_cols:
        corr = df[numeric_cols].corr(numeric_only=True)[target].drop(target).sort_values(ascending=False)
        lines.append(f"\nTop 10 tương quan dương với {target}:")
        for col, val in corr.head(10).items():
            lines.append(f"+ {col}: {val:.4f}")

        lines.append(f"\nTop 10 tương quan âm với {target}:")
        for col, val in corr.tail(10).items():
            lines.append(f"- {col}: {val:.4f}")

    return "\n".join(lines)


def feature_engineering(df: pd.DataFrame, target: str, low_cardinality_threshold: int) -> pd.DataFrame:
    data = df.copy()

    # 1) Impute missing
    numeric_cols = data.select_dtypes(include=np.number).columns.tolist()
    cat_cols = data.select_dtypes(exclude=np.number).columns.tolist()

    for col in numeric_cols:
        data[col] = data[col].fillna(data[col].median())

    for col in cat_cols:
        mode_value = data[col].mode(dropna=True)
        fill_value = mode_value.iloc[0] if not mode_value.empty else "Unknown"
        data[col] = data[col].fillna(fill_value)

    # 2) Date-like categorical season mapping
    if "Season" in data.columns:
        season_map = {"Kharif": 0, "Rabi": 1, "Summer": 2}
        data["Season_Ordinal"] = data["Season"].map(season_map).fillna(-1).astype(int)

    # 3) Interaction features (domain driven)
    if {"Max Temp", "Min Temp"}.issubset(data.columns):
        data["Temp_Range"] = data["Max Temp"] - data["Min Temp"]

    if {"Max Relative Humidity", "Min Relative Humidity"}.issubset(data.columns):
        data["Humidity_Range"] = data["Max Relative Humidity"] - data["Min Relative Humidity"]

    if {"Rainfall", "Heat_Stress_Days"}.issubset(data.columns):
        data["Rainfall_per_HeatStressDay"] = safe_divide(data["Rainfall"], data["Heat_Stress_Days"] + 1)

    if {"Nitrogen", "Organic_Carbon"}.issubset(data.columns):
        data["Nitrogen_to_OrganicCarbon"] = safe_divide(data["Nitrogen"], data["Organic_Carbon"])

    if {"Clay", "Sand", "Silt"}.issubset(data.columns):
        data["Texture_Balance"] = (data["Clay"] + data["Silt"]) - data["Sand"]

    if {"EVI", "LAI", "FPAR"}.issubset(data.columns):
        data["Veg_Composite_Index"] = (data["EVI"] + data["LAI"] + data["FPAR"]) / 3

    # 4) Skew handling with log1p
    numeric_cols = data.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if col == target:
            continue
        if (data[col] >= 0).all() and abs(float(data[col].skew())) > 1:
            data[f"{col}_log1p"] = np.log1p(data[col])

    # 5) Encode categorical variables
    cat_cols = data.select_dtypes(exclude=np.number).columns.tolist()
    low_card_cols = [c for c in cat_cols if data[c].nunique(dropna=False) <= low_cardinality_threshold]
    high_card_cols = [c for c in cat_cols if c not in low_card_cols]

    # one-hot for low cardinality
    if low_card_cols:
        data = pd.get_dummies(data, columns=low_card_cols, drop_first=True)

    # frequency encoding for high cardinality
    for col in high_card_cols:
        freq_map = data[col].value_counts(normalize=True)
        data[f"{col}_freq"] = data[col].map(freq_map)
    if high_card_cols:
        data = data.drop(columns=high_card_cols)

    # final cleanup
    data = data.replace([np.inf, -np.inf], np.nan)
    for col in data.columns:
        if data[col].isna().any():
            if pd.api.types.is_numeric_dtype(data[col]):
                data[col] = data[col].fillna(data[col].median())
            else:
                data[col] = data[col].fillna("Unknown")

    return data


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, encoding="utf-8-sig")

    report = generate_eda_report(df, args.target)
    report_path = output_dir / "eda_report.txt"
    report_path.write_text(report, encoding="utf-8")

    transformed = feature_engineering(
        df,
        target=args.target,
        low_cardinality_threshold=args.low_cardinality_threshold,
    )

    fe_path = output_dir / "agri_feature_engineered.csv"
    transformed.to_csv(fe_path, index=False)

    print(f"Đã tạo báo cáo EDA: {report_path}")
    print(f"Đã tạo dữ liệu feature-engineered: {fe_path}")
    print(f"Shape trước FE: {df.shape} | Shape sau FE: {transformed.shape}")


if __name__ == "__main__":
    main()
