# Datasets Directory

This folder contains the evaluation and training datasets used to train the machine learning models for SmartStock AI:

1. **`food_waste_dataset.csv`**: Food waste tracking dataset used to train the Waste Classification (`waste_classifier.joblib`) and Excess Quantity Regression (`waste_regressor.joblib`) models.
2. **`eval.parquet`**: Perishable retail demand records from the FreshRetailNet dataset used for Demand Forecasting (`demand_forecaster.joblib`).

> **Note:** The pre-trained production model weights are stored in `ml/models/` and are loaded directly at runtime by `ml/predictor.py`.

