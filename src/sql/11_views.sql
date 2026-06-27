-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Dashboard Views
-- ============================================================
-- These views flatten the star schema and pre-calculate 
-- complex aggregations to simplify Power BI ingestion and 
-- accelerate dashboard rendering.
-- ============================================================

SET search_path TO customer360;

-- -----------------------------------------------------------
-- 1. Executive KPIs View
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_executive_kpis AS
WITH monthly_revenue AS (
    SELECT 
        d.year,
        d.month_number,
        d.month_name,
        SUM(t.amount) as total_revenue,
        COUNT(t.transaction_id) as total_transactions
    FROM fact_transactions t
    JOIN dim_date d ON t.date_key = d.date_key
    GROUP BY d.year, d.month_number, d.month_name
),
monthly_csat AS (
    SELECT 
        d.year,
        d.month_number,
        AVG(s.csat_score) as avg_csat
    FROM fact_service_logs s
    JOIN dim_date d ON s.date_key = d.date_key
    GROUP BY d.year, d.month_number
)
SELECT 
    r.year,
    r.month_number,
    r.month_name,
    r.total_revenue,
    r.total_transactions,
    c.avg_csat
FROM monthly_revenue r
LEFT JOIN monthly_csat c 
    ON r.year = c.year AND r.month_number = c.month_number;


-- -----------------------------------------------------------
-- 2. Customer 360 Flattened View
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_customer_360 AS
SELECT 
    c.customer_id,
    c.age,
    c.gender,
    c.dependent_count,
    c.education_level,
    c.marital_status,
    c.income_bracket,
    c.card_category,
    c.customer_tenure_months,
    c.customer_status,
    c.credit_limit,
    c.total_revolving_bal,
    c.avg_open_to_buy,
    c.total_trans_amt_12m,
    c.total_trans_ct_12m,
    c.credit_utilization_ratio,
    COALESCE(s.complaint_count, 0) AS total_complaints,
    s.avg_csat,
    COALESCE(cr.campaigns_accepted, 0) AS total_campaigns_accepted
FROM dim_customer c
LEFT JOIN (
    SELECT customer_id, COUNT(service_id) as complaint_count, AVG(csat_score) as avg_csat
    FROM fact_service_logs 
    GROUP BY customer_id
) s ON c.customer_id = s.customer_id
LEFT JOIN (
    SELECT customer_id, SUM(CASE WHEN was_accepted THEN 1 ELSE 0 END) as campaigns_accepted
    FROM fact_campaign_responses
    GROUP BY customer_id
) cr ON c.customer_id = cr.customer_id;


-- -----------------------------------------------------------
-- 3. Campaign Funnel View
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_campaign_funnel AS
SELECT 
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.target_segment,
    COUNT(r.response_id) AS total_targeted,
    SUM(CASE WHEN r.was_contacted THEN 1 ELSE 0 END) AS total_contacted,
    SUM(CASE WHEN r.was_opened THEN 1 ELSE 0 END) AS total_opened,
    SUM(CASE WHEN r.was_clicked THEN 1 ELSE 0 END) AS total_clicked,
    SUM(CASE WHEN r.was_accepted THEN 1 ELSE 0 END) AS total_accepted,
    SUM(r.conversion_value) AS total_conversion_value
FROM dim_campaign c
LEFT JOIN fact_campaign_responses r ON c.campaign_id = r.campaign_id
GROUP BY 
    c.campaign_id, c.campaign_name, c.campaign_type, c.target_segment;


-- -----------------------------------------------------------
-- 4. Transaction Heatmap View
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_transaction_heatmap AS
SELECT 
    d.day_name,
    d.day_of_week,
    EXTRACT(HOUR FROM t.transaction_date) AS hour_of_day,
    t.merchant_category,
    COUNT(t.transaction_id) as transaction_count,
    SUM(t.amount) as total_volume
FROM fact_transactions t
JOIN dim_date d ON t.date_key = d.date_key
GROUP BY 
    d.day_name, d.day_of_week, EXTRACT(HOUR FROM t.transaction_date), t.merchant_category;
