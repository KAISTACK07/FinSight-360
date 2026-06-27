-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Churn & Retention KPIs
-- ============================================================
-- Business Questions Answered:
--   • What is the overall churn rate?
--   • What factors are most highly correlated with churn?
--   • How does utilization impact churn?
--   • Are high-value customers churning?
--
-- SQL Techniques Demonstrated:
--   • Common Table Expressions (CTEs) for feature binning
--   • Aggregation with FILTER
--   • Cross-tabulation logic
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Overall Churn Metrics
-- -----------------------------------------------------------

SELECT
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned_customers,
    ROUND(COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 / COUNT(*), 2) AS churn_rate_pct,
    ROUND(SUM(total_trans_amt_12m) FILTER (WHERE customer_status = 'Churned'), 0) AS revenue_lost_12m
FROM dim_customer;


-- -----------------------------------------------------------
-- KPI 2: Churn by Credit Utilization Ratio
-- -----------------------------------------------------------
-- What: Does high utilization lead to churn?
-- Why: Customers maxing out their cards may default or switch to lower rates.

WITH utilization_bins AS (
    SELECT
        customer_id,
        customer_status,
        CASE
            WHEN credit_utilization_ratio < 0.1 THEN 'Low (< 10%)'
            WHEN credit_utilization_ratio < 0.4 THEN 'Medium (10-40%)'
            WHEN credit_utilization_ratio < 0.7 THEN 'High (40-70%)'
            ELSE 'Very High (70%+)'
        END AS utilization_band
    FROM dim_customer
)
SELECT
    utilization_band,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned_customers,
    ROUND(COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 / COUNT(*), 2) AS churn_rate_pct
FROM utilization_bins
GROUP BY utilization_band
ORDER BY churn_rate_pct DESC;


-- -----------------------------------------------------------
-- KPI 3: Churn by Inactivity Duration
-- -----------------------------------------------------------
-- What: How strongly does inactivity predict churn?

SELECT
    months_inactive_12m AS months_inactive,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned_customers,
    ROUND(COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 / COUNT(*), 2) AS churn_rate_pct
FROM dim_customer
GROUP BY months_inactive_12m
ORDER BY months_inactive_12m;


-- -----------------------------------------------------------
-- KPI 4: Churn by Change in Spending (Q4 vs Q1)
-- -----------------------------------------------------------
-- What: Do customers who decrease their spending churn more?

WITH spending_trend AS (
    SELECT
        customer_id,
        customer_status,
        CASE
            WHEN amt_change_q4_q1 < 0.5 THEN 'Significant Decrease (<50%)'
            WHEN amt_change_q4_q1 < 0.9 THEN 'Moderate Decrease (50-90%)'
            WHEN amt_change_q4_q1 < 1.1 THEN 'Stable (90-110%)'
            ELSE 'Increase (>110%)'
        END AS spending_trend_band
    FROM dim_customer
)
SELECT
    spending_trend_band,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned_customers,
    ROUND(COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 / COUNT(*), 2) AS churn_rate_pct
FROM spending_trend
GROUP BY spending_trend_band
ORDER BY churn_rate_pct DESC;
