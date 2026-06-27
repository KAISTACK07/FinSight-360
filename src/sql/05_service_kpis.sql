-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Customer Service KPIs
-- ============================================================
-- Business Questions Answered:
--   • What is our average CSAT score?
--   • How fast do we resolve complaints?
--   • Which segments complain the most?
--   • What are the main drivers of escalation?
--   • How does service impact churn?
--
-- SQL Techniques Demonstrated:
--   • CASE WHEN for bucketing (SLA calculation)
--   • Advanced Grouping
--   • Statistical Aggregation (AVG, MAX, MIN)
--   • Correlation indicators
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Service Overview
-- -----------------------------------------------------------

SELECT
    COUNT(*)                                        AS total_complaints,
    COUNT(DISTINCT customer_id)                     AS customers_with_complaints,
    ROUND(AVG(csat_score), 2)                       AS avg_csat_score,
    ROUND(AVG(resolution_time_hours), 1)            AS avg_resolution_hours,
    COUNT(*) FILTER (WHERE escalation_flag = TRUE)   AS escalated_complaints,
    ROUND(
        COUNT(*) FILTER (WHERE escalation_flag = TRUE) * 100.0 / NULLIF(COUNT(*), 0), 2
    )                                               AS escalation_rate_pct,
    COUNT(*) FILTER (WHERE status = 'Resolved')      AS resolved_complaints,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'Resolved') * 100.0 / NULLIF(COUNT(*), 0), 2
    )                                               AS resolution_rate_pct
FROM fact_service_logs;


-- -----------------------------------------------------------
-- KPI 2: Complaints by Category & Card Tier
-- -----------------------------------------------------------
-- What: What do different customer tiers complain about?
-- Why: Drives process improvements for specific customer segments.

SELECT
    dc.card_category,
    fs.complaint_category,
    COUNT(*) AS complaint_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY dc.card_category), 2) AS pct_of_tier_complaints,
    ROUND(AVG(fs.csat_score), 2) AS avg_csat,
    ROUND(AVG(fs.resolution_time_hours), 1) AS avg_resolution_hours
FROM fact_service_logs fs
JOIN dim_customer dc ON fs.customer_id = dc.customer_id
GROUP BY dc.card_category, fs.complaint_category
ORDER BY dc.card_category, complaint_count DESC;


-- -----------------------------------------------------------
-- KPI 3: SLA Performance (Resolution Time Buckets)
-- -----------------------------------------------------------
-- What: How many complaints are resolved within SLA (24h/48h)?
-- Why: Tracks operational efficiency.

WITH resolution_buckets AS (
    SELECT
        service_id,
        resolution_time_hours,
        CASE
            WHEN resolution_time_hours <= 12 THEN '0-12 Hours'
            WHEN resolution_time_hours <= 24 THEN '12-24 Hours'
            WHEN resolution_time_hours <= 48 THEN '24-48 Hours'
            WHEN resolution_time_hours <= 72 THEN '48-72 Hours'
            ELSE 'Over 72 Hours'
        END AS resolution_bucket
    FROM fact_service_logs
    WHERE status = 'Resolved'
)
SELECT
    resolution_bucket,
    COUNT(*) AS complaint_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM resolution_buckets
GROUP BY resolution_bucket
ORDER BY 
    CASE resolution_bucket
        WHEN '0-12 Hours' THEN 1
        WHEN '12-24 Hours' THEN 2
        WHEN '24-48 Hours' THEN 3
        WHEN '48-72 Hours' THEN 4
        ELSE 5
    END;


-- -----------------------------------------------------------
-- KPI 4: CSAT Distribution
-- -----------------------------------------------------------
-- What: Histogram of Customer Satisfaction scores
-- Why: Identifies the proportion of highly dissatisfied customers.

SELECT
    csat_score,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM fact_service_logs
WHERE csat_score IS NOT NULL
GROUP BY csat_score
ORDER BY csat_score DESC;


-- -----------------------------------------------------------
-- KPI 5: Escalation Drivers
-- -----------------------------------------------------------
-- What: Which complaint categories and channels lead to escalation?

SELECT
    complaint_category,
    channel,
    COUNT(*) AS total_complaints,
    COUNT(*) FILTER (WHERE escalation_flag = TRUE) AS escalated_count,
    ROUND(
        COUNT(*) FILTER (WHERE escalation_flag = TRUE) * 100.0 / NULLIF(COUNT(*), 0), 2
    ) AS escalation_rate_pct,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
    ROUND(AVG(csat_score), 2) AS avg_csat
FROM fact_service_logs
GROUP BY complaint_category, channel
HAVING COUNT(*) > 50
ORDER BY escalation_rate_pct DESC
LIMIT 10;


-- -----------------------------------------------------------
-- KPI 6: The Service-Churn Connection
-- -----------------------------------------------------------
-- What: Do churned customers have worse service experiences?
-- Why: Proves that poor service drives churn.

SELECT
    dc.customer_status,
    COUNT(DISTINCT dc.customer_id) AS customers,
    COUNT(fs.service_id) AS total_complaints,
    ROUND(COUNT(fs.service_id) * 1.0 / NULLIF(COUNT(DISTINCT dc.customer_id), 0), 2) AS complaints_per_customer,
    ROUND(AVG(fs.csat_score), 2) AS avg_csat,
    ROUND(AVG(fs.resolution_time_hours), 1) AS avg_resolution_hours,
    ROUND(
        COUNT(fs.service_id) FILTER (WHERE fs.escalation_flag = TRUE) * 100.0 / NULLIF(COUNT(fs.service_id), 0), 2
    ) AS escalation_rate_pct
FROM dim_customer dc
LEFT JOIN fact_service_logs fs ON dc.customer_id = fs.customer_id
GROUP BY dc.customer_status;


-- -----------------------------------------------------------
-- KPI 7: Service Channel Effectiveness
-- -----------------------------------------------------------
-- What: Which channels resolve issues fastest and with highest CSAT?

SELECT
    channel,
    COUNT(*) AS complaint_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS channel_share_pct,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
    ROUND(AVG(csat_score), 2) AS avg_csat,
    ROUND(
        COUNT(*) FILTER (WHERE escalation_flag = TRUE) * 100.0 / NULLIF(COUNT(*), 0), 2
    ) AS escalation_rate_pct
FROM fact_service_logs
GROUP BY channel
ORDER BY complaint_count DESC;


-- -----------------------------------------------------------
-- KPI 8: Priority Handling Validation
-- -----------------------------------------------------------
-- What: Are high-priority issues actually resolved faster?
-- Why: Validates operational compliance with priority SLAs.

SELECT
    priority,
    COUNT(*) AS complaint_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS priority_share_pct,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
    ROUND(AVG(csat_score), 2) AS avg_csat,
    ROUND(
        COUNT(*) FILTER (WHERE escalation_flag = TRUE) * 100.0 / NULLIF(COUNT(*), 0), 2
    ) AS escalation_rate_pct
FROM fact_service_logs
GROUP BY priority
ORDER BY 
    CASE priority
        WHEN 'Critical' THEN 1
        WHEN 'High' THEN 2
        WHEN 'Medium' THEN 3
        WHEN 'Low' THEN 4
        ELSE 5
    END;
