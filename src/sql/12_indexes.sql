-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Performance Indexes
-- ============================================================
-- Creates indexes on foreign keys and commonly filtered 
-- dimensions to optimize dashboard query performance and 
-- analytical aggregations.
-- ============================================================

SET search_path TO customer360;

-- -----------------------------------------------------------
-- dim_customer
-- -----------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_customer_status 
    ON dim_customer(customer_status);

CREATE INDEX IF NOT EXISTS idx_dim_customer_card_cat 
    ON dim_customer(card_category);
    
CREATE INDEX IF NOT EXISTS idx_dim_customer_income 
    ON dim_customer(income_bracket);

-- -----------------------------------------------------------
-- fact_transactions
-- -----------------------------------------------------------
-- Foreign Keys
CREATE INDEX IF NOT EXISTS idx_fact_trans_cust_id 
    ON fact_transactions(customer_id);

CREATE INDEX IF NOT EXISTS idx_fact_trans_date_key 
    ON fact_transactions(date_key);
    
CREATE INDEX IF NOT EXISTS idx_fact_trans_prod_id 
    ON fact_transactions(product_id);

-- Common Filters/Aggregations
CREATE INDEX IF NOT EXISTS idx_fact_trans_merchant_cat 
    ON fact_transactions(merchant_category);

-- -----------------------------------------------------------
-- fact_service_logs
-- -----------------------------------------------------------
-- Foreign Keys
CREATE INDEX IF NOT EXISTS idx_fact_svc_cust_id 
    ON fact_service_logs(customer_id);

CREATE INDEX IF NOT EXISTS idx_fact_svc_date_key 
    ON fact_service_logs(date_key);

-- Common Filters
CREATE INDEX IF NOT EXISTS idx_fact_svc_priority 
    ON fact_service_logs(priority);
    
CREATE INDEX IF NOT EXISTS idx_fact_svc_escalation 
    ON fact_service_logs(escalation_flag);

-- -----------------------------------------------------------
-- fact_campaign_responses
-- -----------------------------------------------------------
-- Foreign Keys
CREATE INDEX IF NOT EXISTS idx_fact_camp_cust_id 
    ON fact_campaign_responses(customer_id);

CREATE INDEX IF NOT EXISTS idx_fact_camp_camp_id 
    ON fact_campaign_responses(campaign_id);

CREATE INDEX IF NOT EXISTS idx_fact_camp_date_key 
    ON fact_campaign_responses(date_key);

-- Filter
CREATE INDEX IF NOT EXISTS idx_fact_camp_accepted 
    ON fact_campaign_responses(was_accepted);
