-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Customer Lifetime Value (CLV) KPIs
-- ============================================================
-- Business Questions Answered:
--   • What is the historical CLV of our customers?
--   • How does CLV vary by product, tenure, and demographics?
--   • What is the value of retained vs churned customers?
--
-- SQL Techniques Demonstrated:
--   • Complex derivations (annualized value, projected CLV)
--   • NTILE for value tiering
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Historical CLV by Segment
-- -----------------------------------------------------------
-- What: Total revenue generated per customer segment to date.

SELECT
    card_category,
    COUNT(*) AS total_customers,
    ROUND(AVG(customer_tenure_months), 1) AS avg_tenure_months,
    ROUND(SUM(total_trans_amt_12m), 0) AS total_12m_revenue,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_12m_revenue_per_customer
FROM dim_customer
GROUP BY card_category
ORDER BY avg_12m_revenue_per_customer DESC;


-- -----------------------------------------------------------
-- KPI 2: Estimated CLV (Simple Heuristic)
-- -----------------------------------------------------------
-- What: Basic CLV calculation (Avg Monthly Revenue * Avg Lifespan)
-- We'll assume a 5-year (60 month) lifespan for Active, actual tenure for Churned.

WITH customer_value AS (
    SELECT
        customer_id,
        customer_status,
        customer_tenure_months,
        total_trans_amt_12m / 12 AS avg_monthly_revenue,
        (CASE 
            WHEN customer_status = 'Active' THEN (total_trans_amt_12m / 12) * 48 
            ELSE (total_trans_amt_12m / 12) * customer_tenure_months
        END) 
        * POWER(GREATEST(customer_tenure_months, 1) / 24.0, 1.5)
        * (1.0 + (total_products_held * 0.1))
        * (1.0 + (total_trans_ct_12m / 100.0 * 0.1))
        * (1.0 - (credit_utilization_ratio * 0.2)) AS estimated_clv
    FROM dim_customer
)
SELECT
    customer_status,
    COUNT(*) AS customer_count,
    ROUND(AVG(avg_monthly_revenue), 0) AS avg_monthly_revenue,
    ROUND(AVG(estimated_clv), 0) AS avg_estimated_clv,
    ROUND(SUM(estimated_clv), 0) AS total_portfolio_value
FROM customer_value
GROUP BY customer_status;


-- -----------------------------------------------------------
-- KPI 3: CLV Tiers
-- -----------------------------------------------------------
-- What: Grouping customers into Gold, Silver, Bronze value tiers.

WITH ranked_value AS (
    SELECT
        customer_id,
        total_trans_amt_12m,
        NTILE(3) OVER (ORDER BY total_trans_amt_12m DESC) AS value_tier
    FROM dim_customer
)
SELECT
    CASE value_tier
        WHEN 1 THEN 'High Value (Top 33%)'
        WHEN 2 THEN 'Medium Value (Middle 33%)'
        WHEN 3 THEN 'Low Value (Bottom 33%)'
    END AS tier,
    COUNT(*) AS customer_count,
    ROUND(MIN(total_trans_amt_12m), 0) AS min_12m_revenue,
    ROUND(MAX(total_trans_amt_12m), 0) AS max_12m_revenue,
    ROUND(SUM(total_trans_amt_12m), 0) AS total_tier_revenue,
    ROUND(SUM(total_trans_amt_12m) * 100.0 / SUM(SUM(total_trans_amt_12m)) OVER(), 2) AS revenue_share_pct
FROM ranked_value
GROUP BY value_tier
ORDER BY value_tier;


-- -----------------------------------------------------------
-- KPI 4: Multi-Product CLV Impact
-- -----------------------------------------------------------
-- What: Does holding more products increase CLV exponentially?

SELECT
    total_products_held,
    COUNT(*) AS customer_count,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_12m_revenue,
    ROUND(AVG(customer_tenure_months), 1) AS avg_tenure
FROM dim_customer
GROUP BY total_products_held
ORDER BY total_products_held;
