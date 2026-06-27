-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Revenue KPIs
-- ============================================================
-- Business Questions Answered:
--   • How much revenue do we generate?
--   • Is revenue growing or declining?
--   • Which segments contribute most revenue?
--   • Which products generate the most revenue?
--   • Which channels drive revenue?
--
-- SQL Techniques Demonstrated:
--   • Running totals with SUM() OVER()
--   • LAG() for growth calculations
--   • RANK() for top segments
--   • Indian Fiscal Year (April–March) logic
--   • Multi-level aggregation
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Monthly Revenue Trend
-- -----------------------------------------------------------
-- What: Total revenue per month with growth metrics
-- Why: Core financial tracking. Identifies trends and seasonality.
-- SQL Technique: LAG() for MoM growth, SUM() OVER for cumulative

WITH monthly_revenue AS (
    SELECT
        dd.year,
        dd.month_number,
        dd.month_name,
        dd.fiscal_year,
        dd.fiscal_quarter,
        SUM(ft.amount)          AS monthly_revenue,
        COUNT(*)                AS transaction_count,
        COUNT(DISTINCT ft.customer_id) AS active_customers
    FROM fact_transactions ft
    JOIN dim_date dd ON ft.date_key = dd.date_key
    GROUP BY dd.year, dd.month_number, dd.month_name, dd.fiscal_year, dd.fiscal_quarter
)
SELECT
    year,
    month_number,
    month_name,
    fiscal_year,
    fiscal_quarter,
    ROUND(monthly_revenue, 0)           AS revenue,
    transaction_count,
    active_customers,
    ROUND(monthly_revenue / NULLIF(active_customers, 0), 0) AS revenue_per_customer,
    LAG(monthly_revenue) OVER (ORDER BY year, month_number) AS prev_month_revenue,
    CASE
        WHEN LAG(monthly_revenue) OVER (ORDER BY year, month_number) > 0
        THEN ROUND(
            (monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY year, month_number)) * 100.0
            / LAG(monthly_revenue) OVER (ORDER BY year, month_number), 2
        )
    END AS mom_growth_pct,
    SUM(monthly_revenue) OVER (
        PARTITION BY year ORDER BY month_number
    ) AS ytd_revenue
FROM monthly_revenue
ORDER BY year, month_number;


-- -----------------------------------------------------------
-- KPI 2: Quarterly Revenue Summary
-- -----------------------------------------------------------
-- What: Revenue by Indian fiscal quarter
-- Why: Banks report on fiscal quarters (FQ1 = Apr–Jun)

SELECT
    fiscal_year,
    fiscal_quarter,
    ROUND(SUM(ft.amount), 0)            AS quarterly_revenue,
    COUNT(*)                            AS transaction_count,
    COUNT(DISTINCT ft.customer_id)      AS active_customers,
    ROUND(
        SUM(ft.amount) / NULLIF(COUNT(DISTINCT ft.customer_id), 0), 0
    ) AS revenue_per_customer,
    LAG(SUM(ft.amount)) OVER (ORDER BY fiscal_year, fiscal_quarter) AS prev_qtr_revenue,
    CASE
        WHEN LAG(SUM(ft.amount)) OVER (ORDER BY fiscal_year, fiscal_quarter) > 0
        THEN ROUND(
            (SUM(ft.amount) - LAG(SUM(ft.amount)) OVER (ORDER BY fiscal_year, fiscal_quarter)) * 100.0
            / LAG(SUM(ft.amount)) OVER (ORDER BY fiscal_year, fiscal_quarter), 2
        )
    END AS qoq_growth_pct
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY fiscal_year, fiscal_quarter
ORDER BY fiscal_year, fiscal_quarter;


-- -----------------------------------------------------------
-- KPI 3: Revenue by Customer Segment (Income Bracket)
-- -----------------------------------------------------------
-- What: Which income segments generate the most revenue?
-- Why: Identifies where to invest for growth vs. retention.
-- SQL Technique: RANK() for segment ranking

SELECT
    dc.income_bracket,
    COUNT(DISTINCT dc.customer_id) AS customers,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(
        SUM(ft.amount) / NULLIF(COUNT(DISTINCT dc.customer_id), 0), 0
    ) AS revenue_per_customer,
    ROUND(AVG(ft.amount), 0) AS avg_transaction_value,
    RANK() OVER (ORDER BY SUM(ft.amount) DESC) AS revenue_rank
FROM fact_transactions ft
JOIN dim_customer dc ON ft.customer_id = dc.customer_id
GROUP BY dc.income_bracket
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------
-- KPI 4: Revenue by Product (Card Category)
-- -----------------------------------------------------------
-- What: Which card tiers generate the most revenue?
-- Why: Guides product pricing and upgrade campaigns.

SELECT
    dc.card_category,
    COUNT(DISTINCT dc.customer_id) AS customers,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(
        SUM(ft.amount) / NULLIF(COUNT(DISTINCT dc.customer_id), 0), 0
    ) AS revenue_per_customer,
    COUNT(*) AS total_transactions,
    ROUND(SUM(ft.amount) / NULLIF(COUNT(*), 0), 0) AS avg_transaction_value
FROM fact_transactions ft
JOIN dim_customer dc ON ft.customer_id = dc.customer_id
GROUP BY dc.card_category
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------
-- KPI 5: Revenue by Transaction Channel
-- -----------------------------------------------------------
-- What: Which payment channels generate the most revenue?
-- Why: Guides digital investment (UPI vs. branch vs. cards).

SELECT
    ft.transaction_channel,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(AVG(ft.amount), 0) AS avg_transaction_value,
    COUNT(DISTINCT ft.customer_id) AS unique_customers,
    RANK() OVER (ORDER BY SUM(ft.amount) DESC) AS channel_rank
FROM fact_transactions ft
GROUP BY ft.transaction_channel
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------
-- KPI 6: Revenue by Merchant Category
-- -----------------------------------------------------------
-- What: Where do customers spend the most?
-- Why: Identifies spending patterns for merchant partnerships.

SELECT
    ft.merchant_category,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(AVG(ft.amount), 0) AS avg_transaction_value,
    COUNT(DISTINCT ft.customer_id) AS unique_customers,
    ROUND(SUM(ft.amount) / NULLIF(COUNT(DISTINCT ft.customer_id), 0), 0) AS spend_per_customer
FROM fact_transactions ft
GROUP BY ft.merchant_category
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------
-- KPI 7: Revenue by Geography (State)
-- -----------------------------------------------------------
-- What: Which states generate the most revenue?
-- Why: Identifies high-value markets for branch expansion.

SELECT
    dc.state,
    COUNT(DISTINCT dc.customer_id) AS customers,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(
        SUM(ft.amount) / NULLIF(COUNT(DISTINCT dc.customer_id), 0), 0
    ) AS revenue_per_customer,
    RANK() OVER (ORDER BY SUM(ft.amount) DESC) AS state_rank
FROM fact_transactions ft
JOIN dim_customer dc ON ft.customer_id = dc.customer_id
GROUP BY dc.state
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------
-- KPI 8: Revenue from Active vs Churned Customers
-- -----------------------------------------------------------
-- What: How much revenue are we losing to churn?
-- Why: Quantifies the business impact of churn in INR.

SELECT
    dc.customer_status,
    COUNT(DISTINCT dc.customer_id) AS customers,
    ROUND(SUM(ft.amount), 0) AS total_revenue,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(
        SUM(ft.amount) / NULLIF(COUNT(DISTINCT dc.customer_id), 0), 0
    ) AS revenue_per_customer,
    ROUND(AVG(ft.amount), 0) AS avg_transaction_value
FROM fact_transactions ft
JOIN dim_customer dc ON ft.customer_id = dc.customer_id
GROUP BY dc.customer_status;


-- -----------------------------------------------------------
-- KPI 9: Top 20 Revenue-Generating Customers
-- -----------------------------------------------------------
-- What: Who are the bank's most valuable customers?
-- Why: High-value retention priority list.
-- SQL Technique: ROW_NUMBER() with FIRST_VALUE() / LAST_VALUE()

WITH customer_revenue AS (
    SELECT
        ft.customer_id,
        dc.first_name || ' ' || dc.last_name AS customer_name,
        dc.card_category,
        dc.income_bracket,
        dc.city || ', ' || dc.state AS location,
        dc.customer_status,
        SUM(ft.amount) AS total_revenue,
        COUNT(*) AS transaction_count,
        ROUND(AVG(ft.amount), 0) AS avg_txn_value,
        MIN(ft.transaction_date) AS first_transaction,
        MAX(ft.transaction_date) AS last_transaction,
        ROW_NUMBER() OVER (ORDER BY SUM(ft.amount) DESC) AS revenue_rank
    FROM fact_transactions ft
    JOIN dim_customer dc ON ft.customer_id = dc.customer_id
    GROUP BY ft.customer_id, dc.first_name, dc.last_name, dc.card_category,
             dc.income_bracket, dc.city, dc.state, dc.customer_status
)
SELECT *
FROM customer_revenue
WHERE revenue_rank <= 20
ORDER BY revenue_rank;


-- -----------------------------------------------------------
-- KPI 10: Revenue Concentration (Pareto Analysis)
-- -----------------------------------------------------------
-- What: What % of revenue comes from top 20% of customers?
-- Why: Validates Pareto principle. High concentration = risk.
-- SQL Technique: NTILE(5) for quintile analysis

WITH customer_revenue AS (
    SELECT
        ft.customer_id,
        SUM(ft.amount) AS total_revenue,
        NTILE(5) OVER (ORDER BY SUM(ft.amount) DESC) AS revenue_quintile
    FROM fact_transactions ft
    GROUP BY ft.customer_id
)
SELECT
    revenue_quintile,
    CASE revenue_quintile
        WHEN 1 THEN 'Top 20%'
        WHEN 2 THEN '21-40%'
        WHEN 3 THEN '41-60%'
        WHEN 4 THEN '61-80%'
        WHEN 5 THEN 'Bottom 20%'
    END AS quintile_label,
    COUNT(*) AS customer_count,
    ROUND(SUM(total_revenue), 0) AS quintile_revenue,
    ROUND(
        SUM(total_revenue) * 100.0 / SUM(SUM(total_revenue)) OVER (), 2
    ) AS revenue_share_pct,
    ROUND(AVG(total_revenue), 0) AS avg_revenue_per_customer
FROM customer_revenue
GROUP BY revenue_quintile
ORDER BY revenue_quintile;
