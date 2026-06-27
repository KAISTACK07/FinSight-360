-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Dashboard Materialization Views
-- ============================================================
-- Business Questions Answered:
--   • How do we efficiently feed Power BI / Tableau?
--
-- SQL Techniques Demonstrated:
--   • Materialized Views (or wide views) for BI performance
--   • Pre-calculated dimensions
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- VIEW: BI_Customer_Overview
-- -----------------------------------------------------------
-- One wide row per customer with pre-calculated metrics for fast dashboard slicing.

DROP VIEW IF EXISTS vw_bi_customer_overview;
CREATE VIEW vw_bi_customer_overview AS
SELECT
    dc.customer_id,
    dc.age,
    CASE
        WHEN dc.age < 30 THEN '18-29'
        WHEN dc.age < 40 THEN '30-39'
        WHEN dc.age < 50 THEN '40-49'
        WHEN dc.age < 60 THEN '50-59'
        ELSE '60+'
    END AS age_band,
    dc.gender,
    dc.income_bracket,
    dc.state,
    dc.city,
    dc.card_category,
    dc.customer_status,
    dc.customer_tenure_months,
    dc.total_products_held,
    dc.credit_limit,
    dc.total_trans_amt_12m AS annual_revenue,
    dc.total_trans_ct_12m AS annual_transactions,
    dc.risk_category,
    COALESCE(SUM(fs.csat_score), 0) / NULLIF(COUNT(fs.service_id), 0) AS avg_csat,
    COUNT(fs.service_id) AS total_complaints,
    SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) AS accepted_campaigns
FROM dim_customer dc
LEFT JOIN fact_service_logs fs ON dc.customer_id = fs.customer_id
LEFT JOIN fact_campaign_responses fcr ON dc.customer_id = fcr.customer_id
GROUP BY dc.customer_id;


-- -----------------------------------------------------------
-- VIEW: BI_Transaction_Timeline
-- -----------------------------------------------------------
-- Aggregated daily transactions for fast time-series charting.

DROP VIEW IF EXISTS vw_bi_transaction_timeline;
CREATE VIEW vw_bi_transaction_timeline AS
SELECT
    dd.full_date,
    dd.year,
    dd.month_name,
    dd.day_name,
    dd.is_weekend,
    dd.is_holiday,
    dd.holiday_name,
    ft.merchant_category,
    ft.transaction_channel,
    COUNT(*) AS total_transactions,
    SUM(ft.amount) AS total_revenue,
    COUNT(DISTINCT ft.customer_id) AS unique_customers
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY dd.full_date, dd.year, dd.month_name, dd.day_name, 
         dd.is_weekend, dd.is_holiday, dd.holiday_name,
         ft.merchant_category, ft.transaction_channel;
