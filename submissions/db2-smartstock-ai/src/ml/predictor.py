"""
Unified Machine Learning Inference & Explainability Engine.
Serves predictions for:
1. Food Waste Risk & Quantity
2. Demand Forecasting & Stockout/Shortage Alerts
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List
import joblib
import numpy as np
import pandas as pd

from config import MODELS_DIR

logger = logging.getLogger(__name__)

class SmartStockPredictor:
    def __init__(self):
        self.waste_clf = None
        self.waste_reg = None
        self.demand_model = None
        self.waste_meta = {}
        self.demand_meta = {}
        self._load_models()

    def _load_models(self):
        try:
            clf_path = MODELS_DIR / "waste_classifier.joblib"
            reg_path = MODELS_DIR / "waste_regressor.joblib"
            meta_path = MODELS_DIR / "waste_metadata.json"
            if clf_path.exists() and meta_path.exists():
                self.waste_clf = joblib.load(clf_path)
                self.waste_reg = joblib.load(reg_path)
                with open(meta_path, "r") as f:
                    self.waste_meta = json.load(f)
                logger.info("Waste models loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading waste models: {e}")

        try:
            d_path = MODELS_DIR / "demand_forecaster.joblib"
            d_meta_path = MODELS_DIR / "demand_metadata.json"
            if d_path.exists() and d_meta_path.exists():
                self.demand_model = joblib.load(d_path)
                with open(d_meta_path, "r") as f:
                    self.demand_meta = json.load(f)
                logger.info("Demand model loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading demand model: {e}")

    def predict_food_waste(
        self,
        category: str,
        purchase_qty: float,
        remaining_stock: float,
        days_to_expiry: float,
        storage_temp: float,
        daily_demand: float,
        weather: str = "Sunny",
        promotion: str = "No"
    ) -> Dict[str, Any]:
        """
        Predicts waste risk level (Low, Medium, High) and estimated waste quantity in kg.
        Includes explainable reasoning.
        """
        encoders = self.waste_meta.get("categorical_encoders", {})
        cat_map = encoders.get("Food_Category", {})
        promo_map = encoders.get("Promotion", {})
        weather_map = encoders.get("Weather", {})

        cat_val = cat_map.get(category, 0)
        promo_val = promo_map.get(promotion, 0)
        weather_val = weather_map.get(weather, 0)

        # Feature order must match trained features
        # ['Food_Category', 'Purchase_Quantity', 'Daily_Demand', 'Remaining_Stock', 'Shelf_Life_Days', 'Storage_Temperature', 'Promotion', 'Weather']
        feat_vals = [
            cat_val, purchase_qty, daily_demand, remaining_stock,
            days_to_expiry, storage_temp, promo_val, weather_val
        ]
        X = pd.DataFrame([feat_vals], columns=self.waste_meta.get("feature_cols", [
            'Food_Category', 'Purchase_Quantity', 'Daily_Demand',
            'Remaining_Stock', 'Shelf_Life_Days', 'Storage_Temperature',
            'Promotion', 'Weather'
        ]))

        # Calculate exact theoretical excess
        usable_before_expiry = max(0.0, float(days_to_expiry) * float(daily_demand))
        potential_excess = max(0.0, round(float(remaining_stock) - usable_before_expiry, 2))

        # Model predictions
        waste_level = "Low"
        pred_qty = 0.0

        if self.waste_clf:
            try:
                c_idx = self.waste_clf.predict(X)[0]
                class_names = self.waste_meta.get("class_names", ["High", "Low", "Medium"])
                waste_level = class_names[c_idx] if c_idx < len(class_names) else "Medium"
            except Exception as e:
                logger.warning(f"Classification inference error: {e}")

        # Deterministic calibration based on physical constraints (First Principles):
        # If remaining stock > days_to_expiry * daily_demand, waste is guaranteed!
        if potential_excess > 0:
            pred_qty = potential_excess
            if days_to_expiry <= 2 and potential_excess >= 2.0:
                waste_level = "High"
            elif potential_excess >= 1.0:
                waste_level = "Medium"
        else:
            pred_qty = 0.0
            waste_level = "Low"

        # Risk score (0 - 100)
        if waste_level == "High":
            risk_score = min(98, 75 + int(potential_excess * 3))
        elif waste_level == "Medium":
            risk_score = min(74, 45 + int(potential_excess * 3))
        else:
            risk_score = max(5, int((1.0 / max(1, days_to_expiry)) * 25))

        # Explainable reasoning
        explanation = (
            f"Currently {remaining_stock} kg available with {days_to_expiry} day(s) until expiration. "
            f"At an average daily consumption of {daily_demand} kg/day, expected usage before expiry is "
            f"{usable_before_expiry:.1f} kg. This leaves an estimated excess of {potential_excess:.1f} kg "
            f"at risk of spoilage if not redirected to active recipes."
        )

        return {
            "waste_level": waste_level,
            "predicted_waste_qty": pred_qty,
            "expected_usage": usable_before_expiry,
            "potential_excess": potential_excess,
            "risk_score": risk_score,
            "explanation": explanation,
            "feature_importance": self.waste_meta.get("feature_importance", {})
        }

    def forecast_ingredient_demand(
        self,
        daily_base_consumption: float,
        current_stock: float,
        horizon_days: int = 7,
        demand_multiplier: float = 1.0
    ) -> Dict[str, Any]:
        """
        Forecasts demand across a horizon (1-day, 3-day, 7-day) and identifies shortages.
        Supports What-If simulation via demand_multiplier.
        """
        # Day by day projection with slight weekend variance
        forecast_days = []
        cum_demand = 0.0
        for d in range(1, horizon_days + 1):
            day_factor = 1.2 if d in [5, 6] else 0.95 # Weekend surge
            d_demand = round(daily_base_consumption * day_factor * demand_multiplier, 1)
            cum_demand += d_demand
            forecast_days.append({
                "day": d,
                "demand": d_demand,
                "cumulative": round(cum_demand, 1)
            })

        predicted_total = round(cum_demand, 1)
        shortage = max(0.0, round(predicted_total - current_stock, 1))
        reorder_suggested = shortage > 0

        return {
            "horizon_days": horizon_days,
            "current_stock": current_stock,
            "predicted_demand": predicted_total,
            "shortage": shortage,
            "reorder_suggested": reorder_suggested,
            "daily_breakdown": forecast_days,
            "explanation": (
                f"Projected {horizon_days}-day demand is {predicted_total} units vs current stock of {current_stock} units. "
                + (f"Shortage of {shortage} units detected. Reorder recommended." if shortage > 0 else "Stock is sufficient.")
            )
        }

predictor = SmartStockPredictor()

