-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Predictive Customer Lifetime Value (CLV) Outputs
-- ============================================================
-- Business Questions Answered:
--   • What is the predicted 12-month future value of each customer?
--   • Which tier (Platinum, Gold, Silver, Bronze) do they belong to?
-- ============================================================

SET search_path TO customer360;

-- -----------------------------------------------------------
-- 1. Create Table for CLV Model Outputs
-- -----------------------------------------------------------
DROP TABLE IF EXISTS clv_predictions CASCADE;
CREATE TABLE clv_predictions (
    customer_id             INTEGER         PRIMARY KEY,
    predicted_clv_12m       DECIMAL(15,2)   NOT NULL,
    clv_tier                VARCHAR(20)     NOT NULL,
    prediction_date         DATE            NOT NULL DEFAULT CURRENT_DATE,
    
    CONSTRAINT fk_clv_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id)
);

COMMENT ON TABLE clv_predictions IS 'Machine Learning outputs: 12-month predictive Customer Lifetime Value from Random Forest Regressor.';

-- -----------------------------------------------------------
-- 2. Create Power BI Ready View
-- -----------------------------------------------------------
CREATE OR REPLACE VIEW v_customer_clv_predictions AS
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.customer_status,
    c.card_category,
    c.risk_category,
    c.total_trans_amt_12m AS historical_12m_revenue,
    p.predicted_clv_12m,
    p.clv_tier,
    (p.predicted_clv_12m - c.total_trans_amt_12m) AS predicted_revenue_growth,
    p.prediction_date
FROM dim_customer c
JOIN clv_predictions p ON c.customer_id = p.customer_id;

COMMENT ON VIEW v_customer_clv_predictions IS 'Denormalized view joining customer dimensions with predictive CLV scores for Power BI.';
