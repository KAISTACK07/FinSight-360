"""
FinSight 360 AI Analytics Assistant
Schema Metadata Layer

Provides the complete schema context that the LLM uses to generate SQL.
Every table, column, relationship, and business definition is described here.
The LLM never sees the raw database ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â only this curated metadata.

Source: Actual PostgreSQL customer360 schema discovered during Phase 1 inspection.
"""

# ============================================================
# FEATURE DISPLAY NAMES
# Reused from src/ml/export_shap_importance.py to ensure
# consistency between SHAP explanations and AI responses.
# ============================================================
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

# ============================================================
# SCHEMA DEFINITION
# Authoritative source for all table/column metadata.
# ============================================================
SCHEMA_NAME = "customer360"

# Tables the AI is allowed to query
ALLOWED_TABLES = {
    "dim_customer",
    "dim_product",
    "dim_campaign",
    "dim_date",
    "fact_transactions",
    "fact_service_logs",
    "fact_campaign_responses",
    "ml_churn_predictions",
    "ml_customer_segments",
    "clv_predictions",
    "v_customer_clv_predictions",
    "ml_campaign_propensity",
    "campaign_experiments",
    "campaign_experiment_outcomes",
    "campaign_experiment_metrics",
    "v_campaign_targeting",
    "v_campaign_audience_summary",
    "v_campaign_experiment_metrics",
}

# Complete table metadata with business context
TABLE_METADATA = {
    "dim_customer": {
        "description": "Master customer dimension table. Contains demographics, credit profile, activity metrics, and status for all 10,127 retail banking customers.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Unique integer customer identifier (e.g., 818770008)",
            "first_name": "Customer first name",
            "last_name": "Customer last name",
            "age": "Customer age in years (18ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“100)",
            "gender": "Customer gender: 'Male' or 'Female'",
            "dependents": "Number of dependents",
            "education_level": "Education level: 'Graduate', 'Post-Graduate', 'Uneducated', 'High School', 'College', 'Doctorate', or NULL",
            "marital_status": "Marital status: 'Married', 'Single', 'Divorced', or NULL",
            "income_bracket": "Indian INR income bracket: 'Below ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹3L', 'ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹3L - ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹5L', 'ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹5L - ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹8L', 'ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹8L - ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹15L', 'Above ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹15L', 'Unknown'",
            "city": "Customer city (Indian cities)",
            "state": "Customer state (Indian states)",
            "customer_since": "Date when the customer opened their account",
            "customer_tenure_months": "Number of months as a customer",
            "customer_status": "Current status: 'Active' or 'Churned'",
            "credit_limit": "Credit limit in INR",
            "total_revolving_bal": "Total revolving balance in INR",
            "avg_open_to_buy": "Average open-to-buy credit in INR",
            "credit_utilization_ratio": "Credit utilization ratio (0.0000 to 1.0000)",
            "card_category": "Card tier: 'Blue', 'Silver', 'Gold', or 'Platinum'",
            "total_products_held": "Number of banking products held by the customer",
            "months_inactive_12m": "Number of months inactive in the last 12 months",
            "contacts_count_12m": "Number of service contacts in the last 12 months",
            "total_trans_amt_12m": "Total transaction amount in INR over last 12 months",
            "total_trans_ct_12m": "Total transaction count over last 12 months",
            "amt_change_q4_q1": "Spending change ratio (Q4 vs Q1)",
            "ct_change_q4_q1": "Transaction count change ratio (Q4 vs Q1)",
            "risk_category": "Risk category: 'Low', 'Medium', or 'High'",
            "preferred_channel": "Preferred banking channel (e.g., 'Mobile Banking', 'UPI')",
            "created_at": "Record creation timestamp",
        },
    },
    "dim_product": {
        "description": "Banking product catalog with 12 Indian retail banking products covering deposits, cards, loans, insurance, and investments.",
        "primary_key": "product_id",
        "columns": {
            "product_id": "Unique product identifier (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“12)",
            "product_name": "Product name (e.g., 'Credit Card - Gold', 'Savings Account')",
            "product_category": "Category: 'Deposits', 'Cards', 'Loans', 'Insurance', 'Investments'",
            "product_type": "Sub-category type",
            "annual_fee": "Annual fee in INR",
            "interest_rate": "Annual interest rate percentage",
            "min_balance": "Minimum balance or sum insured in INR",
            "launch_date": "Product launch date",
            "is_active": "Whether the product is currently active (boolean)",
        },
    },
    "dim_campaign": {
        "description": "Marketing campaign definitions with 5 bank campaigns covering cross-sell, upsell, retention, and engagement.",
        "primary_key": "campaign_id",
        "columns": {
            "campaign_id": "Unique campaign identifier (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“5)",
            "campaign_name": "Campaign name (e.g., 'Credit Limit Upgrade', 'Re-engagement Offer')",
            "campaign_type": "Type: 'Email', 'SMS', 'Push Notification', 'Outbound Call', 'Branch'",
            "campaign_channel": "Channel: 'Digital' or 'Direct'",
            "target_segment": "Target segment name",
            "start_date": "Campaign start date",
            "end_date": "Campaign end date",
            "budget": "Campaign budget in INR",
            "objective": "Objective: 'Acquisition', 'Cross-sell', 'Retention', 'Engagement', 'Upsell'",
            "status": "Status: 'Active', 'Completed', 'Cancelled'",
        },
    },
    "dim_date": {
        "description": "Calendar dimension from 2020-01-01 to 2025-12-31 with Indian fiscal year support (AprilÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“March).",
        "primary_key": "date_key",
        "columns": {
            "date_key": "Date key in YYYYMMDD integer format",
            "full_date": "Full date (DATE type)",
            "day_of_week": "Day of week (0=Monday, 6=Sunday)",
            "day_name": "Day name (e.g., 'Monday')",
            "day_of_month": "Day of month (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“31)",
            "week_of_year": "ISO week of year",
            "month_number": "Month number (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“12)",
            "month_name": "Month name (e.g., 'January')",
            "quarter": "Calendar quarter (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“4)",
            "quarter_name": "Quarter name (e.g., 'Q1')",
            "year": "Calendar year",
            "is_weekend": "Whether the date is a weekend (boolean)",
            "is_holiday": "Whether the date is a bank holiday (boolean)",
            "holiday_name": "Holiday name if applicable",
            "fiscal_year": "Indian fiscal year (FY2025 = Apr 2024 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ Mar 2025)",
            "fiscal_quarter": "Fiscal quarter (FQ1 = AprÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Jun, FQ4 = JanÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“Mar)",
            "fiscal_quarter_name": "Fiscal quarter name",
            "is_month_start": "Whether it is the first day of the month",
            "is_month_end": "Whether it is the last day of the month",
            "is_salary_week": "Whether it falls in 1st or last week of month (salary peaks)",
        },
    },
    "fact_transactions": {
        "description": "Individual transaction records. 1,311,818 rows derived from BankChurners aggregates using Sparkov distribution patterns. All amounts in INR.",
        "primary_key": "transaction_id",
        "foreign_keys": {
            "customer_id": "dim_customer.customer_id",
            "product_id": "dim_product.product_id",
            "date_key": "dim_date.date_key",
        },
        "columns": {
            "transaction_id": "Unique transaction identifier (auto-increment)",
            "customer_id": "Foreign key to dim_customer",
            "product_id": "Foreign key to dim_product",
            "date_key": "Foreign key to dim_date (YYYYMMDD format)",
            "transaction_date": "Full transaction timestamp",
            "transaction_type": "Type: 'Purchase', 'Payment', 'Refund', 'Transfer', 'EMI'",
            "transaction_channel": "Channel: 'UPI', 'NEFT', 'RTGS', 'IMPS', 'Debit Card', 'Credit Card', 'Mobile Banking', 'Net Banking', 'Branch', 'ATM', 'POS'",
            "merchant_category": "Merchant category (e.g., 'Groceries', 'Online Shopping', 'Food & Dining', 'Travel')",
            "merchant_name": "Merchant name (Indian merchants like 'Flipkart', 'Swiggy', 'DMart')",
            "amount": "Transaction amount in INR (always positive)",
            "balance_after": "Account balance after transaction in INR",
            "is_high_value": "Whether the transaction exceeds the 75th percentile for its segment (boolean)",
        },
    },
    "fact_service_logs": {
        "description": "Customer service interactions. 25,208 records derived from BankChurners contact signals.",
        "primary_key": "service_id",
        "foreign_keys": {
            "customer_id": "dim_customer.customer_id",
            "date_key": "dim_date.date_key",
        },
        "columns": {
            "service_id": "Unique service interaction identifier",
            "customer_id": "Foreign key to dim_customer",
            "date_key": "Foreign key to dim_date",
            "complaint_date": "Complaint timestamp",
            "complaint_category": "Category (varies by card tier: 'Fee Dispute', 'Reward Points', 'Concierge Service', etc.)",
            "complaint_subcategory": "Sub-category detail",
            "priority": "Priority: 'Low', 'Medium', 'High', 'Critical'",
            "channel": "Service channel: 'Branch', 'Call Center', 'Email', 'App', 'Social Media'",
            "resolution_date": "Resolution timestamp (NULL if unresolved)",
            "resolution_time_hours": "Hours to resolution (NULL if unresolved)",
            "status": "Status: 'Open', 'In Progress', 'Resolved', 'Escalated'",
            "escalation_flag": "Whether the complaint was escalated (boolean)",
            "csat_score": "Customer satisfaction score (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“5 scale)",
            "agent_id": "Service agent identifier",
        },
    },
    "fact_campaign_responses": {
        "description": "Campaign response funnel. 13,478 records tracking the sequential funnel: contacted ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ opened ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ clicked ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ accepted.",
        "primary_key": "response_id",
        "foreign_keys": {
            "campaign_id": "dim_campaign.campaign_id",
            "customer_id": "dim_customer.customer_id",
            "date_key": "dim_date.date_key",
        },
        "columns": {
            "response_id": "Unique response identifier",
            "campaign_id": "Foreign key to dim_campaign",
            "customer_id": "Foreign key to dim_customer",
            "date_key": "Foreign key to dim_date",
            "response_date": "Response timestamp",
            "was_contacted": "Whether the customer was contacted (boolean)",
            "was_opened": "Whether the customer opened the message (boolean)",
            "was_clicked": "Whether the customer clicked (boolean)",
            "was_accepted": "Whether the customer accepted the offer (boolean)",
            "response_channel": "Channel through which the response was received",
            "conversion_value": "Revenue from conversion in INR",
            "days_to_response": "Number of days from contact to response",
        },
    },
    "ml_churn_predictions": {
        "description": "Machine learning churn predictions for all 10,127 customers. Generated by Random Forest classifier with SHAP explanations. Contains per-customer churn probability, risk tier, and top 3 SHAP risk drivers.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Foreign key to dim_customer (bigint)",
            "churn_probability": "Model-predicted probability of churn (0.0 to 1.0). Higher = more likely to churn.",
            "churn_risk_tier": "Risk tier based on probability: 'Low Risk' (0ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“0.3), 'Medium Risk' (0.3ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“0.7), 'High Risk' (0.7ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“1.0)",
            "top_risk_driver_1": "Primary SHAP contributor toward churn (feature name, e.g., 'months_inactive_12m', 'total_trans_ct_12m')",
            "top_risk_driver_2": "Secondary SHAP contributor toward churn",
            "top_risk_driver_3": "Tertiary SHAP contributor toward churn",
        },
    },
    "ml_customer_segments": {
        "description": "Behavioral customer segments from K-Means clustering (k=4). Each customer is assigned to one of: Premium Customers, Loyal Customers, Growth Customers, Value Seekers.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Foreign key to dim_customer (bigint)",
            "cluster_id": "Internal cluster ID (0ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“3)",
            "behavioral_segment": "Business segment name: 'Premium Customers', 'Loyal Customers', 'Growth Customers', 'Value Seekers'",
            "pca_x": "PCA component 1 (for visualization)",
            "pca_y": "PCA component 2 (for visualization)",
        },
    },
    "clv_predictions": {
        "description": "Predicted 12-month Customer Lifetime Value (CLV) from Random Forest Regressor. Each customer is assigned a predicted future revenue and value tier.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Foreign key to dim_customer",
            "predicted_clv_12m": "Predicted 12-month future customer value in INR",
            "clv_tier": "Value tier: 'Platinum' (top 5%), 'Gold' (top 5ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“20%), 'Silver' (top 20ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“50%), 'Bronze' (bottom 50%)",
            "prediction_date": "Date when the prediction was generated",
        },
    },
    "v_customer_clv_predictions": {
        "description": "View joining dim_customer with clv_predictions. Provides customer name, status, card category, historical revenue, predicted CLV, and predicted revenue growth.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Customer identifier",
            "customer_name": "Full customer name (first + last)",
            "customer_status": "Active or Churned",
            "card_category": "Card tier",
            "risk_category": "Risk category from dim_customer",
            "historical_12m_revenue": "Historical 12-month revenue from dim_customer.total_trans_amt_12m",
            "predicted_clv_12m": "Predicted 12-month CLV",
            "clv_tier": "CLV tier",
            "predicted_revenue_growth": "predicted_clv_12m - historical_12m_revenue",
            "prediction_date": "Prediction date",
        },
    },
    "ml_campaign_propensity": {
        "description": "Machine learning outputs for campaign response propensity and targeting priority. Includes probability of response and a target priority score combining Propensity, CLV, and Churn Risk.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Foreign key to dim_customer",
            "propensity_score": "Model-predicted probability of responding to a campaign (0.0 to 1.0).",
            "propensity_tier": "Propensity tier: 'Low', 'Medium', 'High'",
            "target_priority_score": "Composite business score combining propensity, CLV, and churn probability (0.0 to 1.0).",
            "priority_tier": "Targeting priority tier: 'Low', 'Medium', 'High'",
            "prediction_date": "Prediction generation date",
        },
    },
    "campaign_experiments": {
        "description": "A/B testing assignments for campaign effectiveness evaluation. Customers are assigned to Control or Treatment groups.",
        "primary_key": "experiment_id, customer_id",
        "columns": {
            "experiment_id": "Unique experiment assignment identifier",
            "campaign_id": "Foreign key to dim_campaign",
            "customer_id": "Foreign key to dim_customer",
            "assignment_group": "Group assignment: 'Control' or 'Treatment'",
            "assignment_date": "Date of experiment assignment",
            "random_seed": "Random seed used for assignment reproducibility",
            "eligibility_rule": "Rule used to define the eligible audience",
            "is_synthetic": "Whether the assignment row is synthetic",
        },
    },
    "campaign_experiment_outcomes": {
        "description": "Observed Control/Treatment outcomes for campaign experiments at the customer-experiment grain.",
        "primary_key": "experiment_id, customer_id",
        "foreign_keys": {
            "experiment_id, customer_id": "campaign_experiments.experiment_id, campaign_experiments.customer_id",
            "campaign_id": "dim_campaign.campaign_id",
            "customer_id": "dim_customer.customer_id",
        },
        "columns": {
            "experiment_id": "Unique experiment assignment identifier",
            "campaign_id": "Foreign key to dim_campaign",
            "customer_id": "Foreign key to dim_customer",
            "assignment_group": "Group assignment: 'Control' or 'Treatment'",
            "was_exposed": "Whether the customer was exposed to the campaign",
            "converted": "Whether the customer converted or accepted the offer",
            "conversion_value": "Observed conversion value in INR",
            "outcome_date": "Date the observed outcome was recorded",
            "is_synthetic": "Whether the outcome row is synthetic",
        },
    },
    "campaign_experiment_metrics": {
        "description": "Experiment-level summary metrics for Control vs Treatment measurement, including lift and significance statistics.",
        "primary_key": "experiment_id, campaign_id",
        "foreign_keys": {
            "campaign_id": "dim_campaign.campaign_id",
        },
        "columns": {
            "experiment_id": "Unique experiment assignment identifier",
            "campaign_id": "Foreign key to dim_campaign",
            "campaign_name": "Campaign name",
            "objective": "Campaign objective",
            "control_customers": "Control group size",
            "treatment_customers": "Treatment group size",
            "control_responses": "Observed control conversions",
            "treatment_responses": "Observed treatment conversions",
            "control_conversion_rate": "Observed control conversion rate",
            "treatment_conversion_rate": "Observed treatment conversion rate",
            "absolute_lift": "Treatment minus control conversion rate",
            "relative_lift": "Absolute lift divided by control conversion rate",
            "z_statistic": "Two-proportion z-statistic",
            "p_value": "Two-proportion p-value",
            "confidence_interval_low": "Lower confidence interval bound for lift",
            "confidence_interval_high": "Upper confidence interval bound for lift",
            "includes_synthetic_data": "Whether the metrics include synthetic rows",
            "calculated_at": "Metric calculation timestamp",
        },
    },
    "v_campaign_audience_summary": {
        "description": "Aggregated audience summary for campaign targeting by segment and tier.",
        "primary_key": "behavioral_segment, priority_tier, propensity_tier",
        "columns": {
            "behavioral_segment": "Behavioral customer segment",
            "priority_tier": "Target priority tier",
            "propensity_tier": "Propensity tier",
            "eligible_customers": "Number of eligible customers",
            "avg_clv": "Average predicted CLV",
            "avg_churn_probability": "Average churn probability",
            "avg_propensity": "Average campaign propensity",
            "avg_target_priority": "Average target priority score",
        },
    },
    "v_campaign_experiment_metrics": {
        "description": "Experiment summary view for Control vs Treatment conversion, lift, and significance metrics.",
        "primary_key": "experiment_id, campaign_id",
        "columns": {
            "experiment_id": "Unique experiment assignment identifier",
            "campaign_id": "Foreign key to dim_campaign",
            "campaign_name": "Campaign name",
            "objective": "Campaign objective",
            "control_customers": "Control group size",
            "treatment_customers": "Treatment group size",
            "control_responses": "Observed control conversions",
            "treatment_responses": "Observed treatment conversions",
            "control_conversion_rate": "Observed control conversion rate",
            "treatment_conversion_rate": "Observed treatment conversion rate",
            "absolute_lift": "Treatment minus control conversion rate",
            "relative_lift": "Absolute lift divided by control conversion rate",
            "z_statistic": "Two-proportion z-statistic",
            "p_value": "Two-proportion p-value",
            "confidence_interval_low": "Lower confidence interval bound for lift",
            "confidence_interval_high": "Upper confidence interval bound for lift",
            "includes_synthetic_data": "Whether the metrics include synthetic rows",
            "calculated_at": "Metric calculation timestamp",
        },
    },
    "v_campaign_targeting": {
        "description": "Denormalized view joining customer demographics, ML predictions, and campaign targeting scores for audience building.",
        "primary_key": "customer_id",
        "columns": {
            "customer_id": "Customer identifier",
            "customer_name": "Full customer name",
            "customer_status": "Active or Churned",
            "income_bracket": "Indian INR income bracket",
            "card_category": "Card tier",
            "behavioral_segment": "Behavioral segment from K-Means clustering",
            "predicted_clv_12m": "Predicted 12-month Customer Lifetime Value",
            "churn_probability": "Predicted churn probability",
            "propensity_score": "Model-predicted probability of responding to a campaign",
            "propensity_tier": "Propensity tier",
            "target_priority_score": "Targeting priority score",
            "priority_tier": "Targeting priority tier",
        },
    },
}

# ============================================================
# RELATIONSHIPS (for JOIN generation)
# ============================================================
TABLE_RELATIONSHIPS = [
    {"from_table": "fact_transactions", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "fact_transactions", "from_column": "product_id", "to_table": "dim_product", "to_column": "product_id"},
    {"from_table": "fact_transactions", "from_column": "date_key", "to_table": "dim_date", "to_column": "date_key"},
    {"from_table": "fact_service_logs", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "fact_service_logs", "from_column": "date_key", "to_table": "dim_date", "to_column": "date_key"},
    {"from_table": "fact_campaign_responses", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "fact_campaign_responses", "from_column": "campaign_id", "to_table": "dim_campaign", "to_column": "campaign_id"},
    {"from_table": "fact_campaign_responses", "from_column": "date_key", "to_table": "dim_date", "to_column": "date_key"},
    {"from_table": "ml_churn_predictions", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "ml_customer_segments", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "clv_predictions", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "ml_campaign_propensity", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "campaign_experiments", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "campaign_experiments", "from_column": "campaign_id", "to_table": "dim_campaign", "to_column": "campaign_id"},
    {"from_table": "campaign_experiment_outcomes", "from_column": "customer_id", "to_table": "dim_customer", "to_column": "customer_id"},
    {"from_table": "campaign_experiment_outcomes", "from_column": "campaign_id", "to_table": "dim_campaign", "to_column": "campaign_id"},
    {"from_table": "campaign_experiment_outcomes", "from_column": "experiment_id", "to_table": "campaign_experiments", "to_column": "experiment_id"},
    {"from_table": "campaign_experiment_metrics", "from_column": "campaign_id", "to_table": "dim_campaign", "to_column": "campaign_id"},
]

# ============================================================
# ALLOWED COLUMNS (complete whitelist for SQL validation)
# ============================================================
def get_all_allowed_columns() -> set:
    """Return a flat set of all allowed column names across all tables."""
    columns = set()
    for table_info in TABLE_METADATA.values():
        columns.update(table_info["columns"].keys())
    return columns


def get_schema_context_for_llm() -> str:
    """
    Generate a compact schema description string for LLM prompts.
    This is injected into the system prompt so the LLM knows what tables
    and columns are available for SQL generation.
    """
    lines = [
        f"Database Schema: {SCHEMA_NAME} (PostgreSQL)",
        f"All tables are in the '{SCHEMA_NAME}' schema. Always prefix table names with '{SCHEMA_NAME}.'",
        "",
    ]

    for table_name, meta in TABLE_METADATA.items():
        lines.append(f"TABLE: {SCHEMA_NAME}.{table_name}")
        lines.append(f"  Description: {meta['description']}")
        lines.append(f"  Primary Key: {meta.get('primary_key', 'N/A')}")

        if "foreign_keys" in meta:
            fk_str = ", ".join(f"{k} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {v}" for k, v in meta["foreign_keys"].items())
            lines.append(f"  Foreign Keys: {fk_str}")

        lines.append("  Columns:")
        for col_name, col_desc in meta["columns"].items():
            lines.append(f"    - {col_name}: {col_desc}")
        lines.append("")

    lines.append("RELATIONSHIPS (for JOINs):")
    for rel in TABLE_RELATIONSHIPS:
        lines.append(
            f"  {rel['from_table']}.{rel['from_column']} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ "
            f"{rel['to_table']}.{rel['to_column']}"
        )

    return "\n".join(lines)


def get_feature_display_name(feature_name: str) -> str:
    """Convert a raw SHAP feature name to a human-readable display name."""
    return FEATURE_DISPLAY_NAMES.get(feature_name, feature_name.replace("_", " ").title())
