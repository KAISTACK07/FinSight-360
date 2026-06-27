-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Customer KPIs
-- ============================================================
-- Business Questions Answered:
--   • Who are our customers?
--   • How many are active vs churned?
--   • What is our retention rate?
--   • How is our customer base growing?
--   • What products do customers own?
--
-- SQL Techniques Demonstrated:
--   • CTEs for readability
--   • Window Functions: LAG, NTILE, ROW_NUMBER
--   • CASE WHEN for conditional logic
--   • Aggregate functions with FILTER
--   • Date arithmetic
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Customer Overview
-- -----------------------------------------------------------
-- What: Snapshot of the customer base
-- Why: Foundation metric for all customer analytics

SELECT
    COUNT(*)                                                    AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Active')          AS active_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned')         AS churned_customers,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    )                                                           AS churn_rate_pct,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Active') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    )                                                           AS retention_rate_pct,
    ROUND(AVG(customer_tenure_months), 1)                       AS avg_tenure_months,
    ROUND(AVG(total_products_held), 2)                          AS avg_products_per_customer
FROM dim_customer;


-- -----------------------------------------------------------
-- KPI 2: Customer Distribution by Demographics
-- -----------------------------------------------------------
-- What: Customer breakdown by age, gender, income, education
-- Why: Identifies target demographics for product development

-- By Gender
SELECT
    gender,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(customer_tenure_months), 1) AS avg_tenure,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM dim_customer
GROUP BY gender
ORDER BY customer_count DESC;

-- By Income Bracket
SELECT
    income_bracket,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(credit_limit), 0) AS avg_credit_limit,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM dim_customer
GROUP BY income_bracket
ORDER BY customer_count DESC;

-- By Age Band (using CASE WHEN)
SELECT
    CASE
        WHEN age < 30 THEN '18-29'
        WHEN age < 40 THEN '30-39'
        WHEN age < 50 THEN '40-49'
        WHEN age < 60 THEN '50-59'
        ELSE '60+'
    END AS age_band,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM dim_customer
GROUP BY 1
ORDER BY 1;


-- -----------------------------------------------------------
-- KPI 3: Customer Tenure Distribution
-- -----------------------------------------------------------
-- What: How long customers stay with the bank
-- Why: Longer tenure = higher lifetime value. Identifies
--   at which tenure point customers tend to churn.
-- SQL Technique: NTILE() for quartile analysis

SELECT
    tenure_quartile,
    COUNT(*) AS customer_count,
    MIN(customer_tenure_months) AS min_tenure,
    MAX(customer_tenure_months) AS max_tenure,
    ROUND(AVG(customer_tenure_months), 1) AS avg_tenure,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY customer_tenure_months) AS tenure_quartile
    FROM dim_customer
) t
GROUP BY tenure_quartile
ORDER BY tenure_quartile;


-- -----------------------------------------------------------
-- KPI 4: Monthly New Customer Acquisition
-- -----------------------------------------------------------
-- What: How many customers joined each month?
-- Why: Tracks growth trajectory and seasonal acquisition patterns.
-- SQL Technique: LAG() for month-over-month growth

WITH monthly_new AS (
    SELECT
        DATE_TRUNC('month', customer_since) AS signup_month,
        COUNT(*) AS new_customers
    FROM dim_customer
    GROUP BY 1
)
SELECT
    signup_month,
    new_customers,
    LAG(new_customers) OVER (ORDER BY signup_month) AS prev_month_new,
    CASE
        WHEN LAG(new_customers) OVER (ORDER BY signup_month) IS NOT NULL
             AND LAG(new_customers) OVER (ORDER BY signup_month) > 0
        THEN ROUND(
            (new_customers - LAG(new_customers) OVER (ORDER BY signup_month)) * 100.0
            / LAG(new_customers) OVER (ORDER BY signup_month), 2
        )
    END AS mom_growth_pct,
    SUM(new_customers) OVER (ORDER BY signup_month) AS cumulative_customers
FROM monthly_new
ORDER BY signup_month;


-- -----------------------------------------------------------
-- KPI 5: Customer Churn Analysis
-- -----------------------------------------------------------
-- What: Who is churning and why?
-- Why: Identifies patterns in churned customers for retention.
-- SQL Technique: RANK() for top churn risk factors

-- Churn by Card Category
SELECT
    card_category,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct,
    RANK() OVER (
        ORDER BY COUNT(*) FILTER (WHERE customer_status = 'Churned') * 1.0 
        / NULLIF(COUNT(*), 0) DESC
    ) AS churn_rank
FROM dim_customer
GROUP BY card_category
ORDER BY churn_rate_pct DESC;

-- Churn by Inactivity Level
SELECT
    months_inactive_12m,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_spend
FROM dim_customer
GROUP BY months_inactive_12m
ORDER BY months_inactive_12m;

-- Churn by Contact Frequency
SELECT
    contacts_count_12m,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE customer_status = 'Churned') AS churned,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM dim_customer
GROUP BY contacts_count_12m
ORDER BY contacts_count_12m;


-- -----------------------------------------------------------
-- KPI 6: Customer Risk Distribution
-- -----------------------------------------------------------
-- What: How are customers distributed by risk category?
-- Why: Prioritizes retention efforts for high-risk customers.

SELECT
    risk_category,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(AVG(credit_utilization_ratio), 4) AS avg_utilization,
    ROUND(AVG(months_inactive_12m), 1) AS avg_inactive_months
FROM dim_customer
GROUP BY risk_category
ORDER BY
    CASE risk_category WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;


-- -----------------------------------------------------------
-- KPI 7: Multi-Product Customer Analysis
-- -----------------------------------------------------------
-- What: How many products do customers hold?
-- Why: Multi-product customers have higher switching costs
--   and are less likely to churn. Identifies cross-sell gaps.
-- SQL Technique: DENSE_RANK() for product holding ranking

SELECT
    total_products_held,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct,
    DENSE_RANK() OVER (
        ORDER BY COUNT(*) FILTER (WHERE customer_status = 'Churned') * 1.0 
        / NULLIF(COUNT(*), 0) ASC
    ) AS retention_rank  -- 1 = best retention
FROM dim_customer
GROUP BY total_products_held
ORDER BY total_products_held;


-- -----------------------------------------------------------
-- KPI 8: Geographic Distribution
-- -----------------------------------------------------------
-- What: Where are our customers located?
-- Why: Identifies strong/weak markets for branch strategy.

SELECT
    state,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct,
    COUNT(DISTINCT city) AS cities_covered
FROM dim_customer
GROUP BY state
ORDER BY customer_count DESC;


-- -----------------------------------------------------------
-- KPI 9: Channel Preference Analysis
-- -----------------------------------------------------------
-- What: Which channels do customers prefer?
-- Why: Guides digital investment and branch optimization.

SELECT
    preferred_channel,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(age), 1) AS avg_age,
    ROUND(AVG(total_trans_amt_12m), 0) AS avg_annual_spend,
    ROUND(
        COUNT(*) FILTER (WHERE customer_status = 'Churned') * 100.0 
        / NULLIF(COUNT(*), 0), 2
    ) AS churn_rate_pct
FROM dim_customer
GROUP BY preferred_channel
ORDER BY customer_count DESC;


-- -----------------------------------------------------------
-- KPI 10: Top Customers by Value
-- -----------------------------------------------------------
-- What: Who are our most valuable customers?
-- Why: Focus retention and premium services on top contributors.
-- SQL Technique: ROW_NUMBER() for ranking, FIRST_VALUE()

WITH ranked_customers AS (
    SELECT
        customer_id,
        first_name || ' ' || last_name AS customer_name,
        city,
        state,
        card_category,
        total_trans_amt_12m,
        total_trans_ct_12m,
        customer_tenure_months,
        customer_status,
        ROW_NUMBER() OVER (ORDER BY total_trans_amt_12m DESC) AS value_rank
    FROM dim_customer
)
SELECT
    value_rank,
    customer_id,
    customer_name,
    city || ', ' || state AS location,
    card_category,
    total_trans_amt_12m AS annual_spend,
    total_trans_ct_12m AS annual_transactions,
    customer_tenure_months AS tenure_months,
    customer_status
FROM ranked_customers
WHERE value_rank <= 20
ORDER BY value_rank;
