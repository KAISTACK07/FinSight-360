import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import joblib
import os
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
from src.etl.config import get_connection_url, PROJECT_ROOT
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s │ %(name)-14s │ %(levelname)-8s │ %(message)s')
logger = logging.getLogger("customer360.churn")

def train_churn_model():
    """Trains a Random Forest churn prediction model and generates SHAP explanations."""
    logger.info("=" * 60)
    logger.info("Starting Churn Prediction Modeling")
    logger.info("=" * 60)
    
    # 1. Fetch Data
    engine = create_engine(get_connection_url())
    query = """
    SELECT 
        dc.customer_id,
        dc.age,
        dc.customer_tenure_months,
        dc.total_products_held,
        dc.credit_utilization_ratio,
        dc.months_inactive_12m,
        dc.contacts_count_12m,
        dc.total_trans_amt_12m,
        dc.total_trans_ct_12m,
        dc.amt_change_q4_q1,
        dc.ct_change_q4_q1,
        CASE WHEN dc.customer_status = 'Churned' THEN 1 ELSE 0 END AS target_churn
    FROM customer360.dim_customer dc
    """
    logger.info("Fetching features from PostgreSQL...")
    df = pd.read_sql(query, engine)
    logger.info(f"Fetched {len(df)} rows.")

    # 2. Preprocessing
    X = df.drop(columns=['customer_id', 'target_churn'])
    y = df['target_churn']
    
    # Scaling
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)
    
    # Train-test split (80-20)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    
    # 3. Model Training
    logger.info("Training RandomForestClassifier...")
    rf_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight='balanced')
    rf_model.fit(X_train, y_train)
    
    # 4. Evaluation
    y_pred = rf_model.predict(X_test)
    y_prob = rf_model.predict_proba(X_test)[:, 1]
    
    auc = roc_auc_score(y_test, y_prob)
    logger.info(f"Model AUC-ROC: {auc:.4f}")
    logger.info("\nClassification Report:\n" + classification_report(y_test, y_pred))
    
    # 5. Full Dataset Predictions
    logger.info("Generating predictions for all customers...")
    df['churn_probability'] = rf_model.predict_proba(X_scaled)[:, 1]
    df['churn_risk_tier'] = pd.cut(df['churn_probability'], 
                                   bins=[0, 0.3, 0.7, 1.0], 
                                   labels=['Low Risk', 'Medium Risk', 'High Risk'])

    # 6. SHAP Value Explanations (Global & Local)
    logger.info("Calculating SHAP values for explainability...")
    # Use a sample for SHAP if dataset is huge, but 10k is small enough for TreeExplainer
    explainer = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_scaled)
    
    # SHAP values for class 1 (Churn)
    shap_class1 = shap_values[:, :, 1] if len(shap_values.shape) == 3 else shap_values[1] if isinstance(shap_values, list) else shap_values
    
    # Extract top 3 risk factors for each customer
    logger.info("Extracting top risk drivers per customer...")
    feature_names = X.columns
    
    top_factor_1 = []
    top_factor_2 = []
    top_factor_3 = []
    
    for i in range(len(df)):
        # Get absolute SHAP values for this customer to find the most impactful features
        customer_shap = np.abs(shap_class1[i])
        # Get indices of top 3 features
        top_indices = np.argsort(customer_shap)[-3:][::-1]
        
        top_factor_1.append(feature_names[top_indices[0]])
        top_factor_2.append(feature_names[top_indices[1]])
        top_factor_3.append(feature_names[top_indices[2]])
        
    df['top_risk_driver_1'] = top_factor_1
    df['top_risk_driver_2'] = top_factor_2
    df['top_risk_driver_3'] = top_factor_3

    # 7. Save Artifacts
    output_dir = os.path.join(PROJECT_ROOT, "data", "output")
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    
    # Save Model & Scaler
    joblib.dump(rf_model, os.path.join(models_dir, "churn_rf_model.pkl"))
    joblib.dump(scaler, os.path.join(models_dir, "churn_scaler.pkl"))
    logger.info(f"Saved model artifacts to {models_dir}")
    
    # Save Output for Power BI
    output_cols = ['customer_id', 'churn_probability', 'churn_risk_tier', 
                   'top_risk_driver_1', 'top_risk_driver_2', 'top_risk_driver_3']
    output_path = os.path.join(output_dir, "churn_predictions.csv")
    df[output_cols].to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} predictions to {output_path}")
    
    # Log global feature importance
    importance_df = pd.DataFrame({
        'Feature': feature_names,
        'Importance': rf_model.feature_importances_
    }).sort_values('Importance', ascending=False)
    
    logger.info("\nTop 5 Global Churn Drivers:")
    for _, row in importance_df.head(5).iterrows():
        logger.info(f"  - {row['Feature']}: {row['Importance']:.4f}")
        
    logger.info("=" * 60)
    logger.info("✅ Churn Modeling Complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    train_churn_model()
