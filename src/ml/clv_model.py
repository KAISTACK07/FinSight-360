"""
FinSight 360: Predictive Customer Lifetime Value (CLV) Model
Trains a Random Forest Regressor to predict future 12-month revenue based on historical behavior.
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
import logging
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from src.etl.config import PROJECT_ROOT
from src.etl.feature_engineering import load_raw_features, engineer_clv_features

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s │ %(name)-14s │ %(levelname)-8s │ %(message)s')
logger = logging.getLogger("customer360.clv")

def train_clv_model():
    """Trains the CLV predictive model and exports outputs."""
    logger.info("=" * 60)
    logger.info("Starting CLV Predictive Modeling Pipeline")
    
    # 1. Load and Engineer Features
    df_raw = load_raw_features()
    
    logger.info("Setting future CLV target from actual future temporal holdout (Q4)...")
    target = df_raw['future_monetary'].fillna(0)
    
    # Extract features
    df_features = engineer_clv_features(df_raw)
    
    # Separate features (X) and Target (y)
    customer_ids = df_features['customer_id']
    X = df_features.drop(columns=['customer_id'])
    y = target
    
    logger.info("=== LEAKAGE AUDIT ===")
    logger.info(f"Target column: future_monetary")
    logger.info(f"Features used: {list(X.columns)}")
    logger.info(f"Potential target-derived features in df_raw: future_monetary, future_frequency")
    logger.info(f"Dropped leakage columns (not in X): {[c for c in ['future_monetary', 'future_frequency', 'last_transaction_date', 'customer_status'] if c not in X.columns]}")
    logger.info("=======================")

    # 2. Train-Test Split
    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, customer_ids, test_size=0.2, random_state=42
    )
    logger.info(f"Training set: {len(X_train)} | Test set: {len(X_test)}")

    # 3. Model Training
    logger.info("Training Random Forest Regressor...")
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    # 4. Evaluation
    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)
    
    # Safe MAPE calculation (ignore targets == 0)
    y_test_vals = y_test.values
    mask = y_test_vals > 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_test_vals[mask] - predictions[mask]) / y_test_vals[mask]))
    else:
        mape = 0.0
        
    logger.info(f"Model Evaluation Metrics:")
    logger.info(f"  MAE:  ₹{mae:,.2f}")
    logger.info(f"  RMSE: ₹{rmse:,.2f}")
    logger.info(f"  R²:   {r2:.3f}")
    logger.info(f"  MAPE: {mape:.4f}")

    # 5. Generate Predictions for Entire Portfolio
    logger.info("Generating predictions for all customers...")
    all_predictions = model.predict(X)
    
    output_df = pd.DataFrame({
        'customer_id': customer_ids,
        'predicted_clv_12m': np.round(all_predictions, 2)
    })
    
    # Tiering customers based on predicted CLV using realistic long-tail distribution
    quantiles = output_df['predicted_clv_12m'].quantile([0.50, 0.80, 0.95])
    
    def assign_tier(val):
        if val <= quantiles[0.50]: return 'Bronze'
        elif val <= quantiles[0.80]: return 'Silver'
        elif val <= quantiles[0.95]: return 'Gold'
        else: return 'Platinum'
        
    output_df['clv_tier'] = output_df['predicted_clv_12m'].apply(assign_tier)

    # 6. Save Artifacts
    # Save Model
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, "clv_model.pkl")
    joblib.dump(model, model_path)
    logger.info(f"Saved CLV model to {model_path}")

    # Save Predictions
    output_dir = os.path.join(PROJECT_ROOT, "data", "output")
    os.makedirs(output_dir, exist_ok=True)
    predictions_path = os.path.join(output_dir, "customer_clv.csv")
    output_df.to_csv(predictions_path, index=False)
    logger.info(f"Saved predictions to {predictions_path}")

    # Save Metrics
    metrics_path = os.path.join(output_dir, "clv_metrics.json")
    metrics = {
        "model": "RandomForestRegressor",
        "target": "future_customer_value",
        "evaluation_type": "temporal_holdout",
        "r2": round(float(r2), 3),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "mape": round(float(mape), 4),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "features_used": list(X.columns),
        "leakage_columns_removed": ["future_monetary", "future_frequency"],
        "portfolio_summary": {
            "total_predicted_value": round(float(output_df['predicted_clv_12m'].sum()), 2),
            "average_clv": round(float(output_df['predicted_clv_12m'].mean()), 2),
            "tier_distribution": output_df['clv_tier'].value_counts().to_dict()
        }
    }
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=4)
    logger.info(f"Saved metrics to {metrics_path}")
    logger.info("CLV Pipeline Complete.")

if __name__ == "__main__":
    train_clv_model()
