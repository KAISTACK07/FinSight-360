import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import joblib
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from src.etl.config import get_connection_url, PROJECT_ROOT
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s │ %(name)-14s │ %(levelname)-8s │ %(message)s')
logger = logging.getLogger("customer360.segmentation")

def run_segmentation():
    """Runs K-Means clustering to create behavioral customer segments."""
    logger.info("=" * 60)
    logger.info("Starting Customer Segmentation Clustering")
    logger.info("=" * 60)
    
    # 1. Fetch Data
    engine = create_engine(get_connection_url())
    query = """
    WITH customer_behavior AS (
        SELECT 
            dc.customer_id,
            dc.total_trans_amt_12m,
            dc.total_trans_ct_12m,
            dc.customer_tenure_months,
            dc.credit_utilization_ratio,
            dc.total_products_held,
            COALESCE(AVG(fsl.csat_score), 3) AS avg_csat,
            COUNT(fcr.response_id) AS campaign_engagements
        FROM customer360.dim_customer dc
        LEFT JOIN customer360.fact_service_logs fsl ON dc.customer_id = fsl.customer_id
        LEFT JOIN customer360.fact_campaign_responses fcr ON dc.customer_id = fcr.customer_id AND fcr.was_accepted = TRUE
        GROUP BY 
            dc.customer_id, dc.total_trans_amt_12m, dc.total_trans_ct_12m, 
            dc.customer_tenure_months, dc.credit_utilization_ratio, dc.total_products_held
    )
    SELECT * FROM customer_behavior
    """
    logger.info("Fetching behavioral features from PostgreSQL...")
    df = pd.read_sql(query, engine)
    logger.info(f"Fetched {len(df)} rows.")

    # 2. Preprocessing
    X = df.drop(columns=['customer_id'])
    
    # Handle any nulls (though SQL COALESCE handles most)
    X = X.fillna(X.mean())
    
    # Scaling is critical for K-Means
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Optional: PCA for dimensionality reduction and visualization
    pca = PCA(n_components=2)
    pca_features = pca.fit_transform(X_scaled)
    df['pca_x'] = pca_features[:, 0]
    df['pca_y'] = pca_features[:, 1]
    logger.info(f"PCA explained variance ratio: {pca.explained_variance_ratio_.sum():.4f}")

    # 3. Clustering (K-Means)
    # Using k=4 based on standard banking archetypes (High Value, Active, Credit Hungry, Dormant)
    n_clusters = 4
    logger.info(f"Running K-Means with k={n_clusters}...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(X_scaled)
    
    # 4. Cluster Profiling and Naming
    logger.info("Profiling clusters to assign business names...")
    cluster_profiles = df.groupby('cluster_id').mean()
    
    # Logic to name clusters based on their relative feature means
    cluster_names = {}
    for i in range(n_clusters):
        profile = cluster_profiles.loc[i]
        
        if profile['total_trans_amt_12m'] > cluster_profiles['total_trans_amt_12m'].mean() * 1.5:
            name = "1. Elite High-Spenders"
        elif profile['credit_utilization_ratio'] > cluster_profiles['credit_utilization_ratio'].mean() * 1.5:
            name = "2. Credit Dependent"
        elif profile['campaign_engagements'] > cluster_profiles['campaign_engagements'].mean() * 1.2:
            name = "3. Engaged Opportunists"
        elif profile['total_trans_ct_12m'] < cluster_profiles['total_trans_ct_12m'].mean() * 0.5:
            name = "4. Passive / Low Activity"
        else:
            name = f"Cluster {i} (General)"
            
        cluster_names[i] = name
        
    # Ensure unique names if logic overlaps
    unique_names = list(set(cluster_names.values()))
    if len(unique_names) < n_clusters:
        # Fallback naming if logic isn't distinct enough
        cluster_names = {
            0: "Elite Spenders",
            1: "Digital Engagers",
            2: "Credit Dependent",
            3: "Passive Customers"
        }
        
    df['behavioral_segment'] = df['cluster_id'].map(cluster_names)
    
    # Log the sizes
    sizes = df['behavioral_segment'].value_counts()
    for name, size in sizes.items():
        logger.info(f"  - {name}: {size} customers ({size/len(df)*100:.1f}%)")

    # 5. Save Artifacts
    output_dir = os.path.join(PROJECT_ROOT, "data", "output")
    models_dir = os.path.join(PROJECT_ROOT, "models")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    
    # Save Model & Scaler
    joblib.dump(kmeans, os.path.join(models_dir, "segmentation_kmeans_model.pkl"))
    joblib.dump(scaler, os.path.join(models_dir, "segmentation_scaler.pkl"))
    joblib.dump(pca, os.path.join(models_dir, "segmentation_pca.pkl"))
    logger.info(f"Saved clustering artifacts to {models_dir}")
    
    # Save Output for Power BI
    output_cols = ['customer_id', 'cluster_id', 'behavioral_segment', 'pca_x', 'pca_y']
    output_path = os.path.join(output_dir, "customer_segments.csv")
    df[output_cols].to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} segment assignments to {output_path}")
        
    logger.info("=" * 60)
    logger.info("✅ Segmentation Modeling Complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_segmentation()
