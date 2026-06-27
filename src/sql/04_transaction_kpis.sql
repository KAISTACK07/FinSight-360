-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Transaction KPIs
-- ============================================================
-- Business Questions Answered:
--   • What is the average transaction value?
--   • How are transactions growing?
--   • Which transactions are high value?
--   • What are the spending patterns (time, day, season)?
--   • Who are the most active transactors?
--
-- SQL Techniques Demonstrated:
--   • PERCENTILE_CONT() for median/percentile analysis
--   • NTILE(4) for quartile bucketing
--   • DENSE_RANK() for customer ranking
--   • FIRST_VALUE() / LAST_VALUE() for first/last patterns
--   • Date functions for temporal analysis
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Transaction Overview
-- -----------------------------------------------------------

SELECT
    COUNT(*)                                        AS total_transactions,
    COUNT(DISTINCT customer_id)                     AS unique_customers,
    ROUND(SUM(amount), 0)                           AS total_volume,
    ROUND(AVG(amount), 2)                           AS avg_transaction_value,
    ROUND(
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount), 2
    )                                               AS median_transaction_value,
    ROUND(MIN(amount), 2)                           AS min_amount,
    ROUND(MAX(amount), 2)                           AS max_amount,
    COUNT(*) FILTER (WHERE is_high_value)            AS high_value_count,
    ROUND(
        COUNT(*) FILTER (WHERE is_high_value) * 100.0 / NULLIF(COUNT(*), 0), 2
    )                                               AS high_value_pct
FROM fact_transactions;


-- -----------------------------------------------------------
-- KPI 2: Transaction Quartile Analysis
-- -----------------------------------------------------------
-- What: Distribution of transaction sizes
-- Why: Identifies spending tiers for product segmentation.
-- SQL Technique: NTILE(4) for quartile bucketing

WITH txn_quartiles AS (
    SELECT
        amount,
        NTILE(4) OVER (ORDER BY amount) AS quartile
    FROM fact_transactions
)
SELECT
    quartile,
    CASE quartile
        WHEN 1 THEN 'Q1 (Lowest 25%)'
        WHEN 2 THEN 'Q2 (25-50%)'
        WHEN 3 THEN 'Q3 (50-75%)'
        WHEN 4 THEN 'Q4 (Highest 25%)'
    END AS quartile_label,
    COUNT(*) AS transaction_count,
    ROUND(MIN(amount), 2) AS min_amount,
    ROUND(MAX(amount), 2) AS max_amount,
    ROUND(AVG(amount), 2) AS avg_amount,
    ROUND(SUM(amount), 0) AS total_volume,
    ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 2) AS volume_share_pct
FROM txn_quartiles
GROUP BY quartile
ORDER BY quartile;


-- -----------------------------------------------------------
-- KPI 3: Transactions per Customer Distribution
-- -----------------------------------------------------------
-- What: How many transactions does each customer make?
-- Why: Identifies engagement levels. Low count = disengagement risk.
-- SQL Technique: DENSE_RANK() for top transactors

WITH customer_txn_counts AS (
    SELECT
        customer_id,
        COUNT(*) AS txn_count,
        DENSE_RANK() OVER (ORDER BY COUNT(*) DESC) AS activity_rank
    FROM fact_transactions
    GROUP BY customer_id
)
SELECT
    CASE
        WHEN txn_count <= 20 THEN '1-20'
        WHEN txn_count <= 50 THEN '21-50'
        WHEN txn_count <= 100 THEN '51-100'
        WHEN txn_count <= 150 THEN '101-150'
        ELSE '150+'
    END AS txn_count_band,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers,
    ROUND(AVG(txn_count), 1) AS avg_transactions
FROM customer_txn_counts
GROUP BY 1
ORDER BY MIN(txn_count);


-- -----------------------------------------------------------
-- KPI 4: Monthly Transaction Trend
-- -----------------------------------------------------------
-- What: How are transaction volumes growing?
-- Why: Tracks engagement trajectory and identifies seasonal patterns.

WITH monthly_txn AS (
    SELECT
        dd.year,
        dd.month_number,
        dd.month_name,
        COUNT(*) AS transaction_count,
        ROUND(SUM(ft.amount), 0) AS total_volume,
        ROUND(AVG(ft.amount), 2) AS avg_value,
        COUNT(DISTINCT ft.customer_id) AS active_customers
    FROM fact_transactions ft
    JOIN dim_date dd ON ft.date_key = dd.date_key
    GROUP BY dd.year, dd.month_number, dd.month_name
)
SELECT
    year,
    month_number,
    month_name,
    transaction_count,
    total_volume,
    avg_value,
    active_customers,
    ROUND(transaction_count * 1.0 / NULLIF(active_customers, 0), 1) AS txn_per_customer,
    LAG(transaction_count) OVER (ORDER BY year, month_number) AS prev_month_count,
    CASE
        WHEN LAG(transaction_count) OVER (ORDER BY year, month_number) > 0
        THEN ROUND(
            (transaction_count - LAG(transaction_count) OVER (ORDER BY year, month_number)) * 100.0
            / LAG(transaction_count) OVER (ORDER BY year, month_number), 2
        )
    END AS mom_txn_growth_pct
FROM monthly_txn
ORDER BY year, month_number;


-- -----------------------------------------------------------
-- KPI 5: Day-of-Week Spending Pattern
-- -----------------------------------------------------------
-- What: Which days see the most spending?
-- Why: Optimizes campaign timing and staffing.

SELECT
    dd.day_of_week,
    dd.day_name,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_volume,
    ROUND(AVG(ft.amount), 2) AS avg_value,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_transactions
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY dd.day_of_week, dd.day_name
ORDER BY dd.day_of_week;


-- -----------------------------------------------------------
-- KPI 6: Weekend vs Weekday Spending
-- -----------------------------------------------------------
-- What: Do customers spend differently on weekends?
-- Why: Influences merchant category promotions and offers.

SELECT
    CASE WHEN dd.is_weekend THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_volume,
    ROUND(AVG(ft.amount), 2) AS avg_value,
    COUNT(DISTINCT ft.customer_id) AS unique_customers,
    ROUND(
        SUM(ft.amount) * 100.0 / SUM(SUM(ft.amount)) OVER (), 2
    ) AS volume_share_pct
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY CASE WHEN dd.is_weekend THEN 'Weekend' ELSE 'Weekday' END;


-- -----------------------------------------------------------
-- KPI 7: Holiday vs Non-Holiday Spending
-- -----------------------------------------------------------
-- What: Does Diwali season drive higher spending?
-- Why: Validates seasonal campaign timing.

SELECT
    CASE
        WHEN dd.holiday_name = 'Diwali Season' THEN 'Diwali Season'
        WHEN dd.is_holiday THEN 'Other Holiday'
        ELSE 'Regular Day'
    END AS period,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_volume,
    ROUND(AVG(ft.amount), 2) AS avg_value,
    COUNT(DISTINCT ft.customer_id) AS unique_customers
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY 1
ORDER BY total_volume DESC;


-- -----------------------------------------------------------
-- KPI 8: Salary Week vs Non-Salary Week
-- -----------------------------------------------------------
-- What: Does spending spike during salary credit weeks?
-- Why: Indian salary cycles (1st and last week) drive spending.

SELECT
    CASE WHEN dd.is_salary_week THEN 'Salary Week' ELSE 'Non-Salary Week' END AS period,
    COUNT(*) AS transaction_count,
    ROUND(SUM(ft.amount), 0) AS total_volume,
    ROUND(AVG(ft.amount), 2) AS avg_value
FROM fact_transactions ft
JOIN dim_date dd ON ft.date_key = dd.date_key
GROUP BY CASE WHEN dd.is_salary_week THEN 'Salary Week' ELSE 'Non-Salary Week' END;


-- -----------------------------------------------------------
-- KPI 9: First and Last Transaction per Customer
-- -----------------------------------------------------------
-- What: When did each customer first/last transact?
-- Why: Last transaction recency is a key churn indicator.
-- SQL Technique: FIRST_VALUE() and LAST_VALUE()

WITH customer_txn_timeline AS (
    SELECT
        ft.customer_id,
        dc.customer_status,
        dc.customer_tenure_months,
        MIN(ft.transaction_date) AS first_transaction,
        MAX(ft.transaction_date) AS last_transaction,
        MAX(ft.transaction_date)::DATE - MIN(ft.transaction_date)::DATE AS active_span_days,
        COUNT(*) AS total_transactions,
        FIRST_VALUE(ft.merchant_category) OVER (
            PARTITION BY ft.customer_id ORDER BY ft.transaction_date ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS first_category,
        LAST_VALUE(ft.merchant_category) OVER (
            PARTITION BY ft.customer_id ORDER BY ft.transaction_date ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_category
    FROM fact_transactions ft
    JOIN dim_customer dc ON ft.customer_id = dc.customer_id
    GROUP BY ft.customer_id, dc.customer_status, dc.customer_tenure_months,
             ft.merchant_category, ft.transaction_date
)
SELECT
    customer_status,
    COUNT(DISTINCT customer_id) AS customers,
    ROUND(AVG(active_span_days), 0) AS avg_active_span_days,
    ROUND(AVG(CURRENT_DATE - last_transaction::DATE), 0) AS avg_days_since_last_txn,
    ROUND(AVG(total_transactions), 1) AS avg_transactions
FROM customer_txn_timeline
GROUP BY customer_status;


-- -----------------------------------------------------------
-- KPI 10: High Value Transaction Analysis
-- -----------------------------------------------------------
-- What: Characteristics of high-value transactions
-- Why: Identifies premium spending patterns for targeted offers.

SELECT
    ft.merchant_category,
    COUNT(*) AS high_value_count,
    ROUND(SUM(ft.amount), 0) AS total_volume,
    ROUND(AVG(ft.amount), 0) AS avg_amount,
    COUNT(DISTINCT ft.customer_id) AS unique_customers,
    ROUND(
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2
    ) AS pct_of_high_value
FROM fact_transactions ft
WHERE ft.is_high_value = TRUE
GROUP BY ft.merchant_category
ORDER BY total_volume DESC;
