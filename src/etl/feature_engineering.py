"""
FinSight 360: Feature Engineering Pipeline
Extracts RFM, Tenure, and Behavioral features from PostgreSQL for Machine Learning pipelines.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import logging
from src.etl.config import get_connection_url

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s │ %(name)-14s │ %(levelname)-8s │ %(message)s')
logger = logging.getLogger("customer360.features")


def load_raw_features() -> pd.DataFrame:
    """Loads raw customer and transaction data from PostgreSQL."""
    logger.info("Connecting to PostgreSQL to load raw features...")
    engine = create_engine(get_connection_url())
    
    # Load basic customer demographics and tenure
    customer_query = """
    SELECT 
        customer_id,
        age,
        gender,
        income_bracket,
        customer_tenure_months,
        credit_utilization_ratio,
        total_products_held,
        card_category,
        customer_status
    FROM customer360.dim_customer
    """
    df_customers = pd.read_sql(customer_query, engine)
    
    # Load transactional aggregates for RFM
    # In a real environment, this might calculate dynamic recency.
    # Here we aggregate transactions to get Recency, Frequency, and Monetary value.
    # Split into historical (Jan-Sep) and future target window (Oct-Dec)
    txn_query = """
    SELECT 
        customer_id,
        MAX(CASE WHEN transaction_date < '2024-10-01' THEN transaction_date END) as last_transaction_date,
        COUNT(CASE WHEN transaction_date < '2024-10-01' THEN transaction_id END) as hist_frequency,
        SUM(CASE WHEN transaction_date < '2024-10-01' THEN amount END) as hist_monetary,
        COUNT(CASE WHEN transaction_date >= '2024-10-01' THEN transaction_id END) as future_frequency,
        SUM(CASE WHEN transaction_date >= '2024-10-01' THEN amount END) as future_monetary,
        MODE() WITHIN GROUP (ORDER BY transaction_channel) as preferred_channel
    FROM customer360.fact_transactions
    GROUP BY customer_id
    """
    df_txns = pd.read_sql(txn_query, engine)
    
    logger.info(f"Loaded {len(df_customers)} customers and {len(df_txns)} transactional summaries.")
    
    # Merge datasets
    df_features = pd.merge(df_customers, df_txns, on="customer_id", how="left")
    
    # Handle customers with no transactions
    df_features['hist_frequency'] = df_features['hist_frequency'].fillna(0)
    df_features['hist_monetary'] = df_features['hist_monetary'].fillna(0)
    df_features['future_frequency'] = df_features['future_frequency'].fillna(0)
    df_features['future_monetary'] = df_features['future_monetary'].fillna(0)
    df_features['preferred_channel'] = df_features['preferred_channel'].fillna('Unknown')
    
    return df_features


def engineer_clv_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers specific features required for the Customer Lifetime Value (CLV) predictive model.
    """
    logger.info("Engineering CLV-specific features...")
    df = df.copy()
    
    # 1. Recency in days (Assuming 'today' is the max date in the dataset to simulate point-in-time)
    if df['last_transaction_date'].notna().any():
        split_date = pd.to_datetime('2024-10-01')
        df['last_transaction_date'] = pd.to_datetime(df['last_transaction_date'])
        df['recency_days'] = (split_date - df['last_transaction_date']).dt.days
    else:
        df['recency_days'] = 365 # Default for no transactions
        
    df['recency_days'] = df['recency_days'].fillna(365)
    
    # 2. Average Transaction Value
    df['avg_transaction_value'] = np.where(
        df['hist_frequency'] > 0, 
        df['hist_monetary'] / df['hist_frequency'], 
        0
    )
    
    # 3. Product intensity (Transactions per product)
    df['txn_per_product'] = np.where(
        df['total_products_held'] > 0,
        df['hist_frequency'] / df['total_products_held'],
        0
    )
    
    # 4. Categorical Encoding (One-Hot for model readiness)
    categorical_cols = ['gender', 'income_bracket', 'card_category', 'preferred_channel']
    df_encoded = pd.get_dummies(df, columns=categorical_cols, drop_first=True)
    
    # We drop columns that are not predictive features or are targets themselves
    drop_cols = ['last_transaction_date', 'customer_status', 'future_monetary', 'future_frequency'] 
    
    # Keep customer_id for tracking, but exclude from training array later
    features_df = df_encoded.drop(columns=[col for col in drop_cols if col in df_encoded.columns])
    
    logger.info(f"Feature engineering complete. Output shape: {features_df.shape}")
    return features_df

if __name__ == "__main__":
    df_raw = load_raw_features()
    df_features = engineer_clv_features(df_raw)
    print(df_features.head())
