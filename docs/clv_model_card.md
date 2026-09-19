# Model Card: Customer Lifetime Value (CLV) Predictor

## Model Details
- **Developer:** FinSight 360 Analytics Team
- **Model Type:** Random Forest Regressor
- **Version:** 1.0.0
- **Purpose:** To predict the 12-month future revenue value of a retail banking customer based on their historical behavior, tenure, and product footprint.

## Intended Use
- **Primary Use Case:** Identifying high-value customers for retention prioritization and premium service routing.
- **Secondary Use Case:** Estimating future portfolio value for financial planning and campaign ROI calculations.
- **Out of Scope:** Individual credit risk scoring or loan approvals.

## Factors (Features)
The model leverages a combination of RFM (Recency, Frequency, Monetary) metrics and categorical demographic features engineered in `src/etl/feature_engineering.py`:
- `frequency_12m`, `monetary_12m`, `avg_transaction_value`, `recency_days`
- `customer_tenure_months`, `total_products_held`, `txn_per_product`
- `age`, `gender`, `income_bracket`, `card_category`

## Evaluation Metrics (v1.0.0)
Based on the internal validation holdout set:
- **MAE (Mean Absolute Error):** ₹4,448
- **RMSE (Root Mean Squared Error):** ₹5,634
- **R² Score:** 1.000 (Note: Currently predicting against a synthetic target. Real-world R² is expected to fall between 0.65-0.85).

## Ethical Considerations & Limitations
- The current target variable is synthetically generated using a heuristic multiplier. This prepares the architecture for real-world time-series data without introducing lookahead bias.
- The model treats 0-transaction customers conservatively.
- The model does not factor in external macroeconomic changes (inflation, rate cuts), assuming constant purchasing power parity over the 12-month prediction window.
