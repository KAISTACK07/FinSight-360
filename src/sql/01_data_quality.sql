-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- SQL-Based Data Quality Checks
-- ============================================================
-- Purpose:
--   Mirror Python DQ checks in SQL to demonstrate SQL proficiency
--   in interviews. These can be run independently of Python.
--
-- Usage:
--   psql -U postgres -d customer360 -f 01_data_quality.sql
-- ============================================================

SET search_path TO customer360;


-- ============================================================
-- 1. TABLE COMPLETENESS
-- ============================================================
-- How many records are in each table?
-- Business Value: Verify data loaded completely.

SELECT 'Table Row Counts' AS check_category;

SELECT
    'dim_customer'              AS table_name, COUNT(*) AS row_count FROM dim_customer
UNION ALL SELECT
    'dim_product',              COUNT(*) FROM dim_product
UNION ALL SELECT
    'dim_campaign',             COUNT(*) FROM dim_campaign
UNION ALL SELECT
    'dim_date',                 COUNT(*) FROM dim_date
UNION ALL SELECT
    'fact_transactions',        COUNT(*) FROM fact_transactions
UNION ALL SELECT
    'fact_service_logs',        COUNT(*) FROM fact_service_logs
UNION ALL SELECT
    'fact_campaign_responses',  COUNT(*) FROM fact_campaign_responses
ORDER BY table_name;


-- ============================================================
-- 2. NULL VALUE ANALYSIS
-- ============================================================
-- Which critical columns have missing values?
-- Business Value: Incomplete data produces incorrect KPIs.

SELECT 'NULL Value Analysis - dim_customer' AS check_category;

WITH null_counts AS (
    SELECT
        COUNT(*)                                                    AS total_records,
        COUNT(*) FILTER (WHERE customer_id IS NULL)                 AS null_customer_id,
        COUNT(*) FILTER (WHERE age IS NULL)                         AS null_age,
        COUNT(*) FILTER (WHERE gender IS NULL)                      AS null_gender,
        COUNT(*) FILTER (WHERE income_bracket IS NULL)              AS null_income_bracket,
        COUNT(*) FILTER (WHERE education_level IS NULL)             AS null_education_level,
        COUNT(*) FILTER (WHERE marital_status IS NULL)              AS null_marital_status,
        COUNT(*) FILTER (WHERE customer_status IS NULL)             AS null_customer_status,
        COUNT(*) FILTER (WHERE card_category IS NULL)               AS null_card_category,
        COUNT(*) FILTER (WHERE credit_limit IS NULL)                AS null_credit_limit,
        COUNT(*) FILTER (WHERE total_trans_amt_12m IS NULL)         AS null_total_trans_amt
    FROM dim_customer
)
SELECT
    total_records,
    null_customer_id,
    null_age,
    null_gender,
    null_income_bracket,
    null_education_level,
    null_marital_status,
    null_customer_status,
    null_card_category,
    null_credit_limit,
    null_total_trans_amt
FROM null_counts;


-- ============================================================
-- 3. DUPLICATE PRIMARY KEYS
-- ============================================================
-- Are primary keys unique?
-- Business Value: Duplicate customers mean double-counted KPIs.

SELECT 'Duplicate Primary Key Check' AS check_category;

SELECT 'dim_customer' AS table_name, customer_id, COUNT(*) AS occurrences
FROM dim_customer
GROUP BY customer_id
HAVING COUNT(*) > 1
LIMIT 10;

SELECT 'dim_product' AS table_name, product_id, COUNT(*) AS occurrences
FROM dim_product
GROUP BY product_id
HAVING COUNT(*) > 1
LIMIT 10;


-- ============================================================
-- 4. FOREIGN KEY INTEGRITY
-- ============================================================
-- Do all fact records reference valid dimension records?
-- Business Value: Orphan records break joins and produce NULLs in reports.

SELECT 'Foreign Key Integrity' AS check_category;

-- Transactions → Customers
SELECT
    'fact_transactions → dim_customer' AS fk_check,
    COUNT(*) AS orphan_records
FROM fact_transactions ft
WHERE NOT EXISTS (
    SELECT 1 FROM dim_customer dc WHERE dc.customer_id = ft.customer_id
);

-- Transactions → Products
SELECT
    'fact_transactions → dim_product' AS fk_check,
    COUNT(*) AS orphan_records
FROM fact_transactions ft
WHERE NOT EXISTS (
    SELECT 1 FROM dim_product dp WHERE dp.product_id = ft.product_id
);

-- Transactions → Dates
SELECT
    'fact_transactions → dim_date' AS fk_check,
    COUNT(*) AS orphan_records
FROM fact_transactions ft
WHERE NOT EXISTS (
    SELECT 1 FROM dim_date dd WHERE dd.date_key = ft.date_key
);

-- Service Logs → Customers
SELECT
    'fact_service_logs → dim_customer' AS fk_check,
    COUNT(*) AS orphan_records
FROM fact_service_logs fs
WHERE NOT EXISTS (
    SELECT 1 FROM dim_customer dc WHERE dc.customer_id = fs.customer_id
);

-- Campaign Responses → Campaigns
SELECT
    'fact_campaign_responses → dim_campaign' AS fk_check,
    COUNT(*) AS orphan_records
FROM fact_campaign_responses fcr
WHERE NOT EXISTS (
    SELECT 1 FROM dim_campaign dc WHERE dc.campaign_id = fcr.campaign_id
);


-- ============================================================
-- 5. VALUE RANGE VALIDATION
-- ============================================================
-- Are field values within expected business ranges?

SELECT 'Value Range Validation' AS check_category;

-- Customer age distribution
SELECT
    'Customer Age' AS metric,
    MIN(age) AS min_val,
    MAX(age) AS max_val,
    ROUND(AVG(age), 1) AS avg_val,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age) AS median_val,
    COUNT(*) FILTER (WHERE age < 18 OR age > 100) AS out_of_range
FROM dim_customer;

-- Credit limit distribution (INR)
SELECT
    'Credit Limit' AS metric,
    MIN(credit_limit) AS min_val,
    MAX(credit_limit) AS max_val,
    ROUND(AVG(credit_limit), 0) AS avg_val,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY credit_limit) AS median_val,
    COUNT(*) FILTER (WHERE credit_limit <= 0) AS invalid_count
FROM dim_customer;

-- Transaction amounts
SELECT
    'Transaction Amount' AS metric,
    MIN(amount) AS min_val,
    MAX(amount) AS max_val,
    ROUND(AVG(amount), 2) AS avg_val,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) AS median_val,
    COUNT(*) FILTER (WHERE amount <= 0) AS invalid_count
FROM fact_transactions;

-- CSAT score distribution
SELECT
    'CSAT Score' AS metric,
    MIN(csat_score) AS min_val,
    MAX(csat_score) AS max_val,
    ROUND(AVG(csat_score), 2) AS avg_val,
    COUNT(*) FILTER (WHERE csat_score < 1 OR csat_score > 5) AS out_of_range
FROM fact_service_logs
WHERE csat_score IS NOT NULL;


-- ============================================================
-- 6. BUSINESS RULE VALIDATION
-- ============================================================

SELECT 'Business Rule Validation' AS check_category;

-- Churn distribution (should be ~16% based on source data)
SELECT
    customer_status,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM dim_customer
GROUP BY customer_status;

-- Card category distribution
SELECT
    card_category,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM dim_customer
GROUP BY card_category
ORDER BY count DESC;

-- Campaign funnel logic: accepted must have clicked, clicked must have opened
SELECT
    'Broken funnel records' AS check_name,
    COUNT(*) AS invalid_count
FROM fact_campaign_responses
WHERE (was_accepted = TRUE AND was_clicked = FALSE)
   OR (was_clicked = TRUE AND was_opened = FALSE)
   OR (was_opened = TRUE AND was_contacted = FALSE);


-- ============================================================
-- 7. RECONCILIATION CHECK
-- ============================================================
-- Do transaction aggregates match dim_customer 12-month totals?
-- This validates the decomposition approach.

SELECT 'Transaction Reconciliation (Sample)' AS check_category;

WITH customer_actuals AS (
    SELECT
        customer_id,
        SUM(amount) AS actual_total_amt,
        COUNT(*) AS actual_total_ct
    FROM fact_transactions
    GROUP BY customer_id
),
reconciliation AS (
    SELECT
        dc.customer_id,
        dc.total_trans_amt_12m AS expected_amt,
        COALESCE(ca.actual_total_amt, 0) AS actual_amt,
        ABS(dc.total_trans_amt_12m - COALESCE(ca.actual_total_amt, 0)) AS amt_diff,
        dc.total_trans_ct_12m AS expected_ct,
        COALESCE(ca.actual_total_ct, 0) AS actual_ct
    FROM dim_customer dc
    LEFT JOIN customer_actuals ca ON dc.customer_id = ca.customer_id
)
SELECT
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE amt_diff <= 1.00) AS within_tolerance,
    COUNT(*) FILTER (WHERE amt_diff > 1.00) AS outside_tolerance,
    ROUND(AVG(amt_diff), 2) AS avg_amt_difference,
    MAX(amt_diff) AS max_amt_difference
FROM reconciliation;


-- ============================================================
-- 8. OVERALL DATA QUALITY SUMMARY
-- ============================================================

SELECT 'Overall Data Quality Summary' AS check_category;

WITH checks AS (
    SELECT 'No duplicate customer IDs' AS check_name,
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
    FROM (SELECT customer_id FROM dim_customer GROUP BY customer_id HAVING COUNT(*) > 1) d
    
    UNION ALL
    
    SELECT 'No orphan transactions',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM fact_transactions ft
    WHERE NOT EXISTS (SELECT 1 FROM dim_customer dc WHERE dc.customer_id = ft.customer_id)
    
    UNION ALL
    
    SELECT 'No negative transaction amounts',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM fact_transactions WHERE amount <= 0
    
    UNION ALL
    
    SELECT 'Valid CSAT scores (1-5)',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM fact_service_logs WHERE csat_score IS NOT NULL AND (csat_score < 1 OR csat_score > 5)
    
    UNION ALL
    
    SELECT 'Valid customer statuses',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM dim_customer WHERE customer_status NOT IN ('Active', 'Churned')
    
    UNION ALL
    
    SELECT 'Campaign funnel integrity',
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
    FROM fact_campaign_responses
    WHERE (was_accepted = TRUE AND was_clicked = FALSE)
       OR (was_clicked = TRUE AND was_opened = FALSE)
)
SELECT
    check_name,
    status
FROM checks
ORDER BY status DESC, check_name;
