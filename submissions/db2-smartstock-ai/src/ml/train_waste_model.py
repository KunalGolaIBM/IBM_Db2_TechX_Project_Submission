"""
Training pipeline for Food Waste Prediction Models:
- Random Forest Classifier & Regressor
- XGBoost Classifier & Regressor
- LightGBM Classifier & Regressor
Evaluates and compares performance, extracts feature importances,
and saves the best model artifacts.
"""

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report,
    mean_absolute_error, mean_squared_error, r2_score
)
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import LGBMClassifier, LGBMRegressor

from config import WASTE_DATASET_PATH, MODELS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_waste_models():
    logger.info(f"Loading dataset from: {WASTE_DATASET_PATH}")
    df = pd.read_csv(WASTE_DATASET_PATH)

    # Impute missing values with median / mode
    df['Shelf_Life_Days'] = df['Shelf_Life_Days'].fillna(df['Shelf_Life_Days'].median())
    df['Storage_Temperature'] = df['Storage_Temperature'].fillna(df['Storage_Temperature'].median())
    df['Daily_Demand'] = df['Daily_Demand'].fillna(df['Daily_Demand'].median())
    df['Weather'] = df['Weather'].fillna(df['Weather'].mode()[0])

    # Feature set (avoiding target leakage like Waste_Reason, Donation_Made)
    feature_cols = [
        'Food_Category', 'Purchase_Quantity', 'Daily_Demand',
        'Remaining_Stock', 'Shelf_Life_Days', 'Storage_Temperature',
        'Promotion', 'Weather'
    ]

    # Preprocessing
    encoders = {}
    for col in ['Food_Category', 'Promotion', 'Weather']:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = {label: int(idx) for idx, label in enumerate(le.classes_)}

    X = df[feature_cols].copy()
    y_class = df['Waste_Level'].astype(str)
    y_reg = df['Waste_Quantity'].astype(float)

    # Label encode target for classification
    target_le = LabelEncoder()
    y_class_encoded = target_le.fit_transform(y_class)
    class_names = list(target_le.classes_)

    # Train / Test split
    X_train, X_test, y_train_c, y_test_c = train_test_split(
        X, y_class_encoded, test_size=0.2, random_state=42, stratify=y_class_encoded
    )
    _, _, y_train_r, y_test_r = train_test_split(
        X, y_reg, test_size=0.2, random_state=42
    )

    # -----------------------------
    # 1. Classification Comparison
    # -----------------------------
    logger.info("Training Waste Level Classification Models...")
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

    classifiers = {
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42, max_depth=8),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=5),
        "LightGBM": LGBMClassifier(n_estimators=100, random_state=42, max_depth=6, verbose=-1)
    }

    class_metrics = {}
    best_clf_name = None
    best_f1 = -1.0
    trained_clfs = {}

    for name, clf in classifiers.items():
        try:
            clf.fit(X_train, y_train_c)
            preds = clf.predict(X_test)
            acc = float(accuracy_score(y_test_c, preds))
            f1 = float(f1_score(y_test_c, preds, average='weighted'))
            class_metrics[name] = {"accuracy": round(acc, 4), "f1_score": round(f1, 4)}
            trained_clfs[name] = clf
            logger.info(f"{name} Classifier -> Accuracy: {acc:.4f}, F1: {f1:.4f}")
            if f1 > best_f1:
                best_f1 = f1
                best_clf_name = name
        except Exception as e:
            logger.warning(f"Model {name} failed: {e}")

    # -----------------------------
    # 2. Regression Comparison (Quantity)
    # -----------------------------
    logger.info("Training Waste Quantity Regression Models...")
    regressors = {
        "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42, max_depth=8),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=5),
        "LightGBM": LGBMRegressor(n_estimators=100, random_state=42, max_depth=6, verbose=-1)
    }

    reg_metrics = {}
    best_reg_name = None
    best_r2 = -999.0
    trained_regs = {}

    for name, reg in regressors.items():
        try:
            reg.fit(X_train, y_train_r)
            preds = reg.predict(X_test)
            mae = float(mean_absolute_error(y_test_r, preds))
            rmse = float(np.sqrt(mean_squared_error(y_test_r, preds)))
            r2 = float(r2_score(y_test_r, preds))
            reg_metrics[name] = {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}
            trained_regs[name] = reg
            logger.info(f"{name} Regressor -> MAE: {mae:.4f}, RMSE: {rmse:.4f}, R2: {r2:.4f}")
            if r2 > best_r2:
                best_r2 = r2
                best_reg_name = name
        except Exception as e:
            logger.warning(f"Model {name} failed: {e}")

    # -----------------------------
    # Feature Importances
    # -----------------------------
    best_clf = trained_clfs[best_clf_name]
    if hasattr(best_clf, 'feature_importances_'):
        feature_importance = {
            col: round(float(imp), 4)
            for col, imp in zip(feature_cols, best_clf.feature_importances_)
        }
        # Sort descending
        feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))
    else:
        feature_importance = {}

    # Save artifacts
    joblib.dump(best_clf, MODELS_DIR / "waste_classifier.joblib")
    joblib.dump(trained_regs[best_reg_name], MODELS_DIR / "waste_regressor.joblib")

    metadata = {
        "feature_cols": feature_cols,
        "categorical_encoders": encoders,
        "class_names": class_names,
        "classification_comparison": class_metrics,
        "regression_comparison": reg_metrics,
        "best_classifier": best_clf_name,
        "best_regressor": best_reg_name,
        "feature_importance": feature_importance
    }

    with open(MODELS_DIR / "waste_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Successfully trained and saved Food Waste Models & Metadata!")
    return metadata

if __name__ == "__main__":
    train_waste_models()
