# Interview Defense Guide

This document is designed to help you confidently explain the technical and business decisions made throughout the Customer Finance 360° project during an interview.

## 1. Why a Star Schema in PostgreSQL?
**Question:** Why did you use a Star Schema instead of keeping the data in flat tables or using a Snowflake schema?
**Defense:** Flat tables are extremely inefficient for analytical queries as they duplicate string data (like demographics and product names) millions of times, leading to slow `GROUP BY` operations. A Star Schema centralizes events into narrow, integer-based Fact tables (`fact_transactions`, `fact_service_logs`) and links them to wide Dimension tables (`dim_customer`, `dim_date`). We avoided a Snowflake schema because keeping dimensions denormalized (like having `product_category` inside `dim_product` directly) requires fewer `JOIN`s, which optimizes Power BI's data model performance.

## 2. Handling the Datasets (BankChurners vs. Sparkov)
**Question:** How did you handle the fact that you combined two completely different Kaggle datasets? Is this realistic?
**Defense:** I did *not* blindly merge them. I treated BankChurners as the authoritative source for customer profiles and aggregate metrics (e.g., total spend in 12 months). I treated Sparkov purely as a *statistical template* to extract temporal patterns (like what time of day people shop) and category proportions. The Python ETL pipeline procedurally generated transaction records that respected the Sparkov patterns but mathematically reconciled to the exact penny with the BankChurners aggregates. This demonstrates an understanding of data simulation for analytics rather than just doing a naive SQL `JOIN`.

## 3. Why Random Forest for Churn?
**Question:** Why did you use Random Forest instead of XGBoost or a Neural Network for Churn Prediction?
**Defense:** In banking and finance, *explainability* is often more important than a fractional increase in accuracy. Random Forest provides a highly stable, non-linear classification that easily outputs feature importances. More importantly, it pairs flawlessly with SHAP (SHapley Additive exPlanations) to explain exactly why a specific customer is predicted to churn. Neural networks are black boxes, which makes it very hard to give a marketing team actionable advice on *how* to retain the customer.

## 4. Dual-Layer Validation
**Question:** Why do you have two separate validation scripts (`data_quality.py` and `business_validation.py`)?
**Defense:** Data Quality ensures the database isn't broken (e.g., no NULL primary keys, no negative transactions, valid foreign keys). But a database can be technically perfect and still be completely wrong from a business perspective. The Business Validation script ensures statistical realism—it asserts that Premium Card holders are generally high-income, that churned customers have declining transaction frequency, and that the calculated CLV correlates strongly with historical revenue. Separating them ensures technical robustness *and* business logic accuracy.

## 5. Machine Learning vs. SQL
**Question:** When do you use SQL versus Python/ML in this project?
**Defense:** SQL is used for deterministic, historical reporting. Calculating total revenue per quarter, active customer counts, or funnel conversion rates is done natively in the PostgreSQL Analytics Engine using Window Functions and CTEs. Python/ML is used for predictive and unsupervised tasks where SQL struggles—such as predicting a future probability (Churn), finding hidden multi-dimensional groupings (PCA/K-Means), or estimating unobserved future value (CLV).
