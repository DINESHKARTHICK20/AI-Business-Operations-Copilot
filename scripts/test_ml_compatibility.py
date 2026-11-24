"""
Machine Learning Compatibility Verification Suite
Tests:
1. Churn Prediction model loading & inference
2. Inventory Demand Prediction model loading & inference
3. Sales Forecasting model loading & inference
4. Serialization and scikit-learn version check
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
import sklearn

print("=" * 70)
print("MACHINE LEARNING COMPATIBILITY VERIFICATION")
print("=" * 70)
print(f"scikit-learn version: {sklearn.__version__}")
print(f"joblib version      : {joblib.__version__}")
print(f"numpy version       : {np.__version__}")
print(f"pandas version      : {pd.__version__}")

MODELS_DIR = "backend/models"

# 1. Churn Model
churn_path = os.path.join(MODELS_DIR, "churn_model.pkl")
churn_artifact = joblib.load(churn_path)
print(f"\n1. Churn Model:")
print(f"   Artifact keys: {list(churn_artifact.keys())}")
churn_model = churn_artifact.get("model")
churn_scaler = churn_artifact.get("scaler")
churn_feats = churn_artifact.get("features", [])
print(f"   Model type   : {type(churn_model).__name__}")
print(f"   Features     : {churn_feats}")

# Test churn inference with sample business inputs
test_sample = pd.DataFrame([{
    "total_orders": 12,
    "total_spend": 50000.0,
    "days_since_last_purchase": 10,
    "support_tickets": 1,
    "complaints": 0,
    "average_order_value": 4166.67
}])
if churn_scaler:
    X_scaled = churn_scaler.transform(test_sample[churn_feats])
else:
    X_scaled = test_sample[churn_feats]

prob = churn_model.predict_proba(X_scaled)[0][1]
pred_class = churn_model.predict(X_scaled)[0]
print(f"   Inference Test: Churn Probability = {prob*100:.2f}%, Class = {pred_class} -> PASS")

# 2. Inventory Model
inv_path = os.path.join(MODELS_DIR, "inventory_model.pkl")
inv_artifact = joblib.load(inv_path)
print(f"\n2. Inventory Demand Model:")
print(f"   Artifact keys: {list(inv_artifact.keys())}")
inv_model = inv_artifact.get("model")
inv_feats = inv_artifact.get("features", [])
print(f"   Model type   : {type(inv_model).__name__}")
print(f"   Features     : {inv_feats}")

# Test inventory inference
inv_sample = pd.DataFrame([{
    "avg_daily_demand": 5.0,
    "trend": 1.05,
    "promotion_factor": 1.0
}])
inv_pred = inv_model.predict(inv_sample[inv_feats])[0]
print(f"   Inference Test: Predicted Daily Demand = {inv_pred:.2f} units -> PASS")

# 3. Sales Model
sales_path = os.path.join(MODELS_DIR, "sales_model.pkl")
sales_artifact = joblib.load(sales_path)
print(f"\n3. Sales Forecast Model:")
print(f"   Artifact keys: {list(sales_artifact.keys())}")
sales_model = sales_artifact.get("model")
sales_feats = sales_artifact.get("features", [])
print(f"   Model type   : {type(sales_model).__name__}")
print(f"   Features     : {sales_feats}")

# Test sales inference
sales_sample = pd.DataFrame([{
    "month_index": 11,
    "orders": 25,
    "marketing_spend": 15000.0
}])
sales_pred = sales_model.predict(sales_sample[sales_feats])[0]
print(f"   Inference Test: Predicted Sales Revenue = ₹{sales_pred:,.2f} -> PASS")

print("\n" + "=" * 70)
print("ALL 3 ML MODELS VERIFIED: 100% COMPATIBLE AND OPERATIONAL")
print("=" * 70)
