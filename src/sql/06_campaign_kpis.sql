-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Campaign & Marketing KPIs
-- ============================================================
-- Business Questions Answered:
--   • What is the conversion rate of each campaign?
--   • What is the campaign funnel drop-off?
--   • What is the ROI of marketing spend?
--   • Which channels have the highest engagement?
--   • How long does it take for customers to respond?
--
-- SQL Techniques Demonstrated:
--   • Funnel Analysis
--   • ROI Calculation
--   • Aggregation with joins
-- ============================================================

SET search_path TO customer360;


-- -----------------------------------------------------------
-- KPI 1: Campaign Funnel Overview
-- -----------------------------------------------------------
-- What: Drop-off at each stage of the marketing funnel.
-- Why: Identifies where the campaign is failing (e.g., low open rate vs low click rate).

SELECT
    dc.campaign_name,
    dc.campaign_type,
    COUNT(fcr.response_id) AS targeted_customers,
    SUM(CASE WHEN fcr.was_contacted THEN 1 ELSE 0 END) AS contacted,
    SUM(CASE WHEN fcr.was_opened THEN 1 ELSE 0 END) AS opened,
    SUM(CASE WHEN fcr.was_clicked THEN 1 ELSE 0 END) AS clicked,
    SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) AS accepted,
    ROUND(
        SUM(CASE WHEN fcr.was_opened THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(fcr.response_id), 0), 2
    ) AS open_rate_pct,
    ROUND(
        SUM(CASE WHEN fcr.was_clicked THEN 1 ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN fcr.was_opened THEN 1 ELSE 0 END), 0), 2
    ) AS click_to_open_rate_pct,
    ROUND(
        SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(fcr.response_id), 0), 2
    ) AS overall_conversion_rate_pct
FROM fact_campaign_responses fcr
JOIN dim_campaign dc ON fcr.campaign_id = dc.campaign_id
GROUP BY dc.campaign_name, dc.campaign_type
ORDER BY overall_conversion_rate_pct DESC;


-- -----------------------------------------------------------
-- KPI 2: Campaign ROI Analysis
-- -----------------------------------------------------------
-- What: Return on Investment for marketing spend.
-- Why: Measures marketing effectiveness and justifies budget.

SELECT
    dc.campaign_name,
    dc.budget AS campaign_budget,
    COUNT(fcr.response_id) AS targeted_customers,
    SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) AS conversions,
    ROUND(SUM(fcr.conversion_value), 0) AS generated_revenue,
    ROUND(
        (SUM(fcr.conversion_value) - dc.budget) / NULLIF(dc.budget, 0) * 100.0, 2
    ) AS roi_pct,
    ROUND(
        dc.budget / NULLIF(SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END), 0), 0
    ) AS cost_per_acquisition
FROM fact_campaign_responses fcr
JOIN dim_campaign dc ON fcr.campaign_id = dc.campaign_id
GROUP BY dc.campaign_id, dc.campaign_name, dc.budget
ORDER BY roi_pct DESC;


-- -----------------------------------------------------------
-- KPI 3: Channel Effectiveness
-- -----------------------------------------------------------
-- What: Which marketing channels drive the best engagement?

SELECT
    dc.campaign_type AS channel,
    COUNT(fcr.response_id) AS volume,
    ROUND(
        SUM(CASE WHEN fcr.was_opened THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(fcr.response_id), 0), 2
    ) AS open_rate_pct,
    ROUND(
        SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(fcr.response_id), 0), 2
    ) AS conversion_rate_pct,
    ROUND(AVG(fcr.conversion_value) FILTER (WHERE fcr.was_accepted), 0) AS avg_value_per_conversion
FROM fact_campaign_responses fcr
JOIN dim_campaign dc ON fcr.campaign_id = dc.campaign_id
GROUP BY dc.campaign_type
ORDER BY conversion_rate_pct DESC;


-- -----------------------------------------------------------
-- KPI 4: Time to Response
-- -----------------------------------------------------------
-- What: How long does it take for a customer to accept an offer?
-- Why: Helps set campaign duration and follow-up timing.

SELECT
    dc.campaign_name,
    ROUND(AVG(fcr.days_to_response), 1) AS avg_days_to_response,
    MIN(fcr.days_to_response) AS min_days,
    MAX(fcr.days_to_response) AS max_days,
    COUNT(fcr.response_id) FILTER (WHERE fcr.days_to_response <= 7) AS responses_within_week
FROM fact_campaign_responses fcr
JOIN dim_campaign dc ON fcr.campaign_id = dc.campaign_id
WHERE fcr.was_accepted = TRUE
GROUP BY dc.campaign_name
ORDER BY avg_days_to_response;


-- -----------------------------------------------------------
-- KPI 5: Audience Engagement by Income Segment
-- -----------------------------------------------------------
-- What: Which income segments respond best to campaigns?

SELECT
    cust.income_bracket,
    COUNT(fcr.response_id) AS targeted_count,
    ROUND(
        SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(fcr.response_id), 0), 2
    ) AS conversion_rate_pct,
    ROUND(SUM(fcr.conversion_value), 0) AS total_value_generated
FROM fact_campaign_responses fcr
JOIN dim_customer cust ON fcr.customer_id = cust.customer_id
GROUP BY cust.income_bracket
ORDER BY conversion_rate_pct DESC;
