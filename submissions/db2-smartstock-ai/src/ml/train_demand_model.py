"""
Training pipeline for Demand Forecasting:
- Baseline (Linear Regression)
- Random Forest Regressor
- Gradient Boosting Regressor
- LightGBM Regressor
Trained on FreshRetailNet-50K perishable food product dataset.
Saves comparison metrics, feature importance, and best model artifact.
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import DEMAND_DATASET_PATH, MODELS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_demand_models():
    logger.info(f"Loading perishable demand dataset: {DEMAND_DATASET_PATH}")
    # Sample 50,000 rows for fast, robust training
    df = pd.read_parquet(DEMAND_DATASET_PATH)
    if len(df) > 50000:
        df = df.sample(n=50000, random_state=42)

    # Clean & fill nulls
    features = [
        'discount', 'holiday_flag', 'activity_flag',
        'avg_temperature', 'avg_humidity', 'avg_wind_level'
    ]
    if 'precpt' in df.columns:
        features.append('precpt')

    X = df[features].copy()
    for col in features:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(X[col].median() if not pd.isna(X[col].median()) else 0.0)

    y = pd.to_numeric(df['sale_amount'], errors='coerce').fillna(0.0).astype(float)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    models = {
        "Linear Regression (Baseline)": LinearRegression(),
        "Random Forest Regressor": RandomForestRegressor(n_estimators=80, max_depth=8, random_state=42, n_jobs=-1),
        "Gradient Boosting Regressor": GradientBoostingRegressor(n_estimators=80, max_depth=5, random_state=42),
        "LightGBM Regressor": LGBMRegressor(n_estimators=100, max_depth=6, random_state=42, verbose=-1)
    }

    comparison = {}
    trained_models = {}
    best_name = None
    best_mae = float("inf")

    for name, model in models.items():
        logger.info(f"Training {name}...")
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        # Avoid negative demand predictions
        preds = np.clip(preds, 0, None)

        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        r2 = float(r2_score(y_test, preds))
        # WAPE (Weighted Absolute Percentage Error)
        wape = float(np.sum(np.abs(y_test - preds)) / np.sum(y_test)) if np.sum(y_test) > 0 else 0.0

        comparison[name] = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2": round(r2, 4),
            "wape": round(wape, 4)
        }
        trained_models[name] = model
        logger.info(f"{name} -> MAE: {mae:.4f}, RMSE: {rmse:.4f}, R2: {r2:.4f}, WAPE: {wape:.4f}")

        if mae < best_mae:
            best_mae = mae
            best_name = name

    # Feature Importance for best tree-based model
    best_model = trained_models[best_name]
    feature_importance = {}
    if hasattr(best_model, 'feature_importances_'):
        feature_importance = {
            feat: round(float(imp), 4)
            for feat, imp in zip(features, best_model.feature_importances_)
        }
        feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    # Save best model
    joblib.dump(best_model, MODELS_DIR / "demand_forecaster.joblib")

    metadata = {
        "features": features,
        "best_model": best_name,
        "comparison": comparison,
        "feature_importance": feature_importance
    }

    with open(MODELS_DIR / "demand_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Successfully trained and saved Demand Forecasting Models & Metadata!")
    return metadata

if __name__ == "__main__":
    train_demand_models()
