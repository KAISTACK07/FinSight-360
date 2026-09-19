"""
Customer Finance 360° Intelligence Platform
SHAP Feature Importance Exporter

Exports the global feature importance scores from the trained
Random Forest churn model to a CSV file for Power BI consumption.

Why a separate script:
  - Keeps the dashboard data pipeline fully reproducible
  - Avoids manual data entry in Power BI (interview-defensible)
  - CSV is automatically loaded into Power BI data model

Usage:
    python -m src.ml.export_shap_importance
"""

import pandas as pd
import joblib
import os
import logging
from src.etl.config import PROJECT_ROOT

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(name)-14s │ %(levelname)-8s │ %(message)s'
)
logger = logging.getLogger("customer360.shap_export")

# Human-readable display names for ML features
FEATURE_DISPLAY_NAMES = {
    "total_trans_ct_12m": "Transaction Count (12M)",
    "total_trans_amt_12m": "Transaction Amount (12M)",
    "ct_change_q4_q1": "Txn Count Change (Q4 vs Q1)",
    "amt_change_q4_q1": "Spending Change (Q4 vs Q1)",
    "months_inactive_12m": "Months Inactive (12M)",
    "contacts_count_12m": "Service Contact Frequency",
    "credit_utilization_ratio": "Credit Utilization Ratio",
    "customer_tenure_months": "Customer Tenure (Months)",
    "total_products_held": "Products Held",
    "age": "Customer Age",
}

# The feature order used during model training (must match churn_model.py)
FEATURE_COLUMNS = [
    "age",
    "customer_tenure_months",
    "total_products_held",
    "credit_utilization_ratio",
    "months_inactive_12m",
    "contacts_count_12m",
    "total_trans_amt_12m",
    "total_trans_ct_12m",
    "amt_change_q4_q1",
    "ct_change_q4_q1",
]


def export_shap_importance():
    """Load the trained churn model and export feature importance to CSV."""
    logger.info("=" * 60)
    logger.info("Exporting SHAP Feature Importance for Power BI")
    logger.info("=" * 60)

    # 1. Load trained model
    models_dir = os.path.join(PROJECT_ROOT, "models")
    model_path = os.path.join(models_dir, "churn_rf_model.pkl")

    if not os.path.exists(model_path):
        logger.error(f"Model not found at {model_path}. Run churn_model.py first.")
        return

    logger.info(f"Loading model from {model_path}...")
    rf_model = joblib.load(model_path)

    # 2. Extract feature importances (Gini importance from Random Forest)
    importances = rf_model.feature_importances_

    if len(importances) != len(FEATURE_COLUMNS):
        logger.error(
            f"Feature count mismatch: model has {len(importances)} features, "
            f"expected {len(FEATURE_COLUMNS)}"
        )
        return

    # 3. Build the export DataFrame
    importance_df = pd.DataFrame({
        "feature_name": FEATURE_COLUMNS,
        "display_name": [FEATURE_DISPLAY_NAMES.get(f, f) for f in FEATURE_COLUMNS],
        "importance_score": importances,
    })

    # Sort by importance descending
    importance_df = importance_df.sort_values(
        "importance_score", ascending=False
    ).reset_index(drop=True)

    # Add rank column
    importance_df.insert(0, "importance_rank", range(1, len(importance_df) + 1))

    # 4. Save to CSV
    output_dir = os.path.join(PROJECT_ROOT, "data", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "shap_feature_importance.csv")
    importance_df.to_csv(output_path, index=False)

    logger.info(f"Saved {len(importance_df)} feature importances to {output_path}")
    logger.info("\nGlobal Churn Risk Drivers (Ranked):")
    for _, row in importance_df.iterrows():
        logger.info(
            f"  #{int(row['importance_rank']):2d}  "
            f"{row['display_name']:<30s}  {row['importance_score']:.4f}"
        )

    logger.info("=" * 60)
    logger.info("✅ SHAP Export Complete")
    logger.info("=" * 60)

    return importance_df


if __name__ == "__main__":
    export_shap_importance()
