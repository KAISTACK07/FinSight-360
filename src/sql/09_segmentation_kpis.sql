-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Customer Segmentation KPIs (RFM)
-- ============================================================
-- Business Questions Answered:
--   • Who are our "Champions" vs "At Risk" customers?
--   • What is the RFM (Recency, Frequency, Monetary) breakdown?
--
-- SQL Techniques Demonstrated:
--   • NTILE(5) for quintile scoring
--   • Multi-stage CTEs
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: RFM Scoring Model
-- -----------------------------------------------------------
-- Step 1: Calculate raw R, F, M metrics
-- Step 2: Convert to 1-5 scores using NTILE
-- Step 3: Map scores to segments

WITH rfm_raw AS (
    SELECT
        dc.customer_id,
        MAX(ft.transaction_date)::DATE AS last_purchase_date,
        CURRENT_DATE - MAX(ft.transaction_date)::DATE AS recency_days,
        COUNT(ft.transaction_id) AS frequency,
        SUM(ft.amount) AS monetary
    FROM dim_customer dc
    JOIN fact_transactions ft ON dc.customer_id = ft.customer_id
    GROUP BY dc.customer_id
),
rfm_scores AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score, -- 5 is most recent
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,     -- 5 is most frequent
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score       -- 5 is highest spend
    FROM rfm_raw
),
rfm_segments AS (
    SELECT
        customer_id,
        r_score,
        f_score,
        m_score,
        r_score::text || f_score::text || m_score::text AS rfm_cell,
        (r_score + f_score + m_score) AS rfm_total_score,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '1. Champions'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '2. Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN '3. Recent Customers'
            WHEN r_score <= 2 AND f_score >= 4 THEN '4. At Risk (High Engagement)'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 4 THEN '5. Cannot Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN '6. Lost / Hibernating'
            ELSE '7. Average'
        END AS rfm_segment
    FROM rfm_scores
)
SELECT
    rfm_segment,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS segment_share_pct,
    ROUND(AVG(r.recency_days), 0) AS avg_recency_days,
    ROUND(AVG(r.frequency), 1) AS avg_frequency,
    ROUND(AVG(r.monetary), 0) AS avg_monetary_value
FROM rfm_segments s
JOIN rfm_raw r ON s.customer_id = r.customer_id
GROUP BY rfm_segment
ORDER BY rfm_segment;
