-- ============================================================
-- Customer Finance 360° Intelligence Platform
-- Star Schema DDL — PostgreSQL
-- ============================================================
-- Business Objective:
--   Create an analytically-optimized star schema warehouse
--   for a retail banking Customer 360° platform.
--
-- Design Decisions:
--   - Star schema (not snowflake) for query simplicity
--   - DECIMAL(15,2) for all monetary fields (INR precision)
--   - Integer surrogate keys for all dimensions
--   - Indian fiscal year support in dim_date
--   - Constraints enforce referential integrity
--
-- Execution:
--   psql -U postgres -d customer360 -f 00_create_schema.sql
-- ============================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS customer360;
SET search_path TO customer360;

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- -----------------------------------------------------------
-- dim_date: Calendar dimension with Indian fiscal year support
-- -----------------------------------------------------------
-- Why: Pre-computed date attributes eliminate repeated
--   DATE_PART / EXTRACT calls in analytical queries.
--   Indian FY (April–March) is critical for banking analytics.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS dim_date CASCADE;
CREATE TABLE dim_date (
    date_key            INTEGER         PRIMARY KEY,           -- YYYYMMDD format
    full_date           DATE            NOT NULL UNIQUE,
    day_of_week         SMALLINT        NOT NULL,              -- 0=Mon, 6=Sun
    day_name            VARCHAR(10)     NOT NULL,
    day_of_month        SMALLINT        NOT NULL,
    week_of_year        SMALLINT        NOT NULL,
    month_number        SMALLINT        NOT NULL,
    month_name          VARCHAR(10)     NOT NULL,
    quarter             SMALLINT        NOT NULL,              -- Calendar quarter (1-4)
    quarter_name        VARCHAR(5)      NOT NULL,              -- 'Q1', 'Q2', etc.
    year                SMALLINT        NOT NULL,
    is_weekend          BOOLEAN         NOT NULL DEFAULT FALSE,
    is_holiday          BOOLEAN         NOT NULL DEFAULT FALSE,
    holiday_name        VARCHAR(50),
    fiscal_year         SMALLINT        NOT NULL,              -- Indian FY: Apr 2024–Mar 2025 = FY2025
    fiscal_quarter      SMALLINT        NOT NULL,              -- FQ1 = Apr–Jun, FQ4 = Jan–Mar
    fiscal_quarter_name VARCHAR(5)      NOT NULL,
    is_month_start      BOOLEAN         NOT NULL DEFAULT FALSE,
    is_month_end        BOOLEAN         NOT NULL DEFAULT FALSE,
    is_salary_week      BOOLEAN         NOT NULL DEFAULT FALSE -- 1st and last week of month
);

COMMENT ON TABLE dim_date IS 'Calendar dimension with Indian fiscal year, holidays, and salary cycle flags.';
COMMENT ON COLUMN dim_date.fiscal_year IS 'Indian FY convention: Apr 2024–Mar 2025 = FY2025.';
COMMENT ON COLUMN dim_date.is_salary_week IS 'TRUE for 1st and last week of month (salary credit peaks).';


-- -----------------------------------------------------------
-- dim_customer: Master customer dimension
-- -----------------------------------------------------------
-- Source: BankChurners.csv (localized to Indian context)
-- Why: Central dimension for all customer analytics.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS dim_customer CASCADE;
CREATE TABLE dim_customer (
    customer_id             INTEGER         PRIMARY KEY,
    first_name              VARCHAR(50)     NOT NULL,
    last_name               VARCHAR(50)     NOT NULL,
    age                     SMALLINT        NOT NULL,
    gender                  VARCHAR(10)     NOT NULL,            -- 'Male', 'Female'
    dependents              SMALLINT        NOT NULL DEFAULT 0,
    education_level         VARCHAR(30),                         -- 'Graduate', 'Post-Graduate', etc.
    marital_status          VARCHAR(20),                         -- 'Married', 'Single', etc.
    income_bracket          VARCHAR(20)     NOT NULL,            -- Indian INR brackets
    city                    VARCHAR(50)     NOT NULL,
    state                   VARCHAR(50)     NOT NULL,
    customer_since          DATE            NOT NULL,
    customer_tenure_months  SMALLINT        NOT NULL,
    customer_status         VARCHAR(10)     NOT NULL,            -- 'Active', 'Churned'
    credit_limit            DECIMAL(15,2)   NOT NULL,            -- In INR
    total_revolving_bal     DECIMAL(15,2)   NOT NULL DEFAULT 0,
    avg_open_to_buy         DECIMAL(15,2),
    credit_utilization_ratio DECIMAL(5,4)   NOT NULL DEFAULT 0,  -- 0.0000 to 1.0000
    card_category           VARCHAR(10)     NOT NULL,            -- 'Blue', 'Silver', 'Gold', 'Platinum'
    total_products_held     SMALLINT        NOT NULL DEFAULT 1,
    months_inactive_12m     SMALLINT        NOT NULL DEFAULT 0,
    contacts_count_12m      SMALLINT        NOT NULL DEFAULT 0,
    total_trans_amt_12m     DECIMAL(15,2)   NOT NULL DEFAULT 0,  -- 12-month aggregate (INR)
    total_trans_ct_12m      INTEGER         NOT NULL DEFAULT 0,  -- 12-month transaction count
    amt_change_q4_q1        DECIMAL(8,4),                        -- Spending change ratio
    ct_change_q4_q1         DECIMAL(8,4),                        -- Transaction count change ratio
    risk_category           VARCHAR(10)     NOT NULL DEFAULT 'Medium', -- 'Low', 'Medium', 'High'
    preferred_channel       VARCHAR(20)     NOT NULL DEFAULT 'Mobile Banking',
    created_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_customer_status CHECK (customer_status IN ('Active', 'Churned')),
    CONSTRAINT chk_card_category CHECK (card_category IN ('Blue', 'Silver', 'Gold', 'Platinum')),
    CONSTRAINT chk_risk_category CHECK (risk_category IN ('Low', 'Medium', 'High')),
    CONSTRAINT chk_gender CHECK (gender IN ('Male', 'Female')),
    CONSTRAINT chk_age_range CHECK (age BETWEEN 18 AND 100),
    CONSTRAINT chk_utilization CHECK (credit_utilization_ratio BETWEEN 0 AND 1)
);

COMMENT ON TABLE dim_customer IS 'Master customer dimension from BankChurners, localized to Indian banking context.';
COMMENT ON COLUMN dim_customer.income_bracket IS 'Indian INR brackets (Below ₹3L, ₹3L-₹5L, ₹5L-₹8L, ₹8L-₹15L, Above ₹15L).';
COMMENT ON COLUMN dim_customer.total_trans_amt_12m IS '12-month aggregate transaction amount in INR. Used for reconciliation with fact_transactions.';


-- -----------------------------------------------------------
-- dim_product: Banking product catalog
-- -----------------------------------------------------------
-- Source: Generated (12 Indian banking products)
-- Why: Enables product-level analytics, cross-sell analysis,
--   and portfolio distribution reports.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS dim_product CASCADE;
CREATE TABLE dim_product (
    product_id          INTEGER         PRIMARY KEY,
    product_name        VARCHAR(50)     NOT NULL,
    product_category    VARCHAR(20)     NOT NULL,            -- 'Deposits', 'Cards', 'Loans', 'Insurance', 'Investments'
    product_type        VARCHAR(30)     NOT NULL,            -- Sub-category
    annual_fee          DECIMAL(10,2)   NOT NULL DEFAULT 0,  -- In INR
    interest_rate       DECIMAL(5,2),                        -- Annual %
    min_balance         DECIMAL(12,2),                       -- Min balance / sum insured
    launch_date         DATE            NOT NULL DEFAULT '2015-01-01',
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    
    CONSTRAINT chk_product_category CHECK (
        product_category IN ('Deposits', 'Cards', 'Loans', 'Insurance', 'Investments')
    )
);

COMMENT ON TABLE dim_product IS 'Indian retail banking product catalog covering deposits, cards, loans, insurance, and investments.';


-- -----------------------------------------------------------
-- dim_campaign: Marketing campaign dimension
-- -----------------------------------------------------------
-- Source: Generated (5 campaigns with Indian banking context)
-- Why: Enables campaign performance analytics, ROI tracking,
--   and marketing effectiveness measurement.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS dim_campaign CASCADE;
CREATE TABLE dim_campaign (
    campaign_id         INTEGER         PRIMARY KEY,
    campaign_name       VARCHAR(100)    NOT NULL,
    campaign_type       VARCHAR(30)     NOT NULL,            -- 'Email', 'SMS', 'Push Notification', 'Outbound Call', 'Branch'
    campaign_channel    VARCHAR(30),
    target_segment      VARCHAR(30)     NOT NULL,
    start_date          DATE            NOT NULL,
    end_date            DATE            NOT NULL,
    budget              DECIMAL(12,2)   NOT NULL,            -- In INR
    objective           VARCHAR(30)     NOT NULL,            -- 'Acquisition', 'Cross-sell', 'Retention', 'Engagement', 'Upsell'
    status              VARCHAR(15)     NOT NULL DEFAULT 'Completed',
    
    CONSTRAINT chk_campaign_status CHECK (status IN ('Active', 'Completed', 'Cancelled')),
    CONSTRAINT chk_campaign_dates CHECK (end_date >= start_date)
);

COMMENT ON TABLE dim_campaign IS 'Marketing campaign definitions with targeting criteria and budget allocation.';


-- ============================================================
-- FACT TABLES
-- ============================================================

-- -----------------------------------------------------------
-- fact_transactions: Individual customer transactions
-- -----------------------------------------------------------
-- Source: Derived by decomposing BankChurners aggregates
--   using Sparkov distribution patterns.
-- Why: Transaction-level grain enables temporal analysis,
--   merchant analytics, channel analysis, and ML features.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS fact_transactions CASCADE;
CREATE TABLE fact_transactions (
    transaction_id          SERIAL          PRIMARY KEY,
    customer_id             INTEGER         NOT NULL,
    product_id              INTEGER         NOT NULL,
    date_key                INTEGER         NOT NULL,
    transaction_date        TIMESTAMP       NOT NULL,
    transaction_type        VARCHAR(20)     NOT NULL,        -- 'Purchase', 'Payment', 'Refund', 'Transfer', 'EMI'
    transaction_channel     VARCHAR(20)     NOT NULL,        -- UPI, NEFT, Credit Card, etc.
    merchant_category       VARCHAR(30)     NOT NULL,        -- Localized category
    merchant_name           VARCHAR(100),
    amount                  DECIMAL(15,2)   NOT NULL,        -- In INR
    balance_after           DECIMAL(15,2),
    is_high_value           BOOLEAN         NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_trans_customer FOREIGN KEY (customer_id) 
        REFERENCES dim_customer(customer_id),
    CONSTRAINT fk_trans_product FOREIGN KEY (product_id)
        REFERENCES dim_product(product_id),
    CONSTRAINT fk_trans_date FOREIGN KEY (date_key)
        REFERENCES dim_date(date_key),
    CONSTRAINT chk_trans_amount CHECK (amount > 0)
);

COMMENT ON TABLE fact_transactions IS 'Individual transaction records derived from BankChurners aggregates + Sparkov distribution patterns.';
COMMENT ON COLUMN fact_transactions.amount IS 'Transaction amount in INR. SUM per customer reconciles to dim_customer.total_trans_amt_12m.';
COMMENT ON COLUMN fact_transactions.is_high_value IS 'TRUE if amount exceeds 75th percentile for the customer segment.';


-- -----------------------------------------------------------
-- fact_service_logs: Customer service interactions
-- -----------------------------------------------------------
-- Source: Derived from BankChurners contacts_count_12m
--   and behavioral signals (churn, inactivity, card tier).
-- Why: Enables service quality analytics, CSAT tracking,
--   escalation analysis, and complaint resolution metrics.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS fact_service_logs CASCADE;
CREATE TABLE fact_service_logs (
    service_id              SERIAL          PRIMARY KEY,
    customer_id             INTEGER         NOT NULL,
    date_key                INTEGER         NOT NULL,
    complaint_date          TIMESTAMP       NOT NULL,
    complaint_category      VARCHAR(30)     NOT NULL,        -- Category based on card tier
    complaint_subcategory   VARCHAR(50),
    priority                VARCHAR(10)     NOT NULL DEFAULT 'Medium',  -- 'Low', 'Medium', 'High', 'Critical'
    channel                 VARCHAR(20)     NOT NULL,        -- 'Branch', 'Call Center', 'Email', 'App', 'Social Media'
    resolution_date         TIMESTAMP,                       -- NULL if unresolved
    resolution_time_hours   DECIMAL(8,2),                    -- NULL if unresolved
    status                  VARCHAR(15)     NOT NULL DEFAULT 'Resolved',
    escalation_flag         BOOLEAN         NOT NULL DEFAULT FALSE,
    csat_score              SMALLINT,                        -- 1–5 scale
    agent_id                VARCHAR(10),
    
    CONSTRAINT fk_service_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id),
    CONSTRAINT fk_service_date FOREIGN KEY (date_key)
        REFERENCES dim_date(date_key),
    CONSTRAINT chk_priority CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    CONSTRAINT chk_service_status CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Escalated')),
    CONSTRAINT chk_csat CHECK (csat_score BETWEEN 1 AND 5)
);

COMMENT ON TABLE fact_service_logs IS 'Customer service interactions derived from BankChurners contact and behavioral signals.';
COMMENT ON COLUMN fact_service_logs.resolution_time_hours IS 'Hours to resolution. Correlated with contacts_count_12m and churn status.';


-- -----------------------------------------------------------
-- fact_campaign_responses: Campaign response funnel
-- -----------------------------------------------------------
-- Source: Derived from BankChurners behavioral signals
--   using business-rule-based targeting and response logic.
-- Why: Enables campaign funnel analysis, ROI calculation,
--   and marketing effectiveness measurement.
-- -----------------------------------------------------------
DROP TABLE IF EXISTS fact_campaign_responses CASCADE;
CREATE TABLE fact_campaign_responses (
    response_id             SERIAL          PRIMARY KEY,
    campaign_id             INTEGER         NOT NULL,
    customer_id             INTEGER         NOT NULL,
    date_key                INTEGER         NOT NULL,
    response_date           TIMESTAMP       NOT NULL,
    was_contacted           BOOLEAN         NOT NULL DEFAULT TRUE,
    was_opened              BOOLEAN         NOT NULL DEFAULT FALSE,
    was_clicked             BOOLEAN         NOT NULL DEFAULT FALSE,
    was_accepted            BOOLEAN         NOT NULL DEFAULT FALSE,
    response_channel        VARCHAR(20),
    conversion_value        DECIMAL(12,2)   DEFAULT 0,       -- Revenue from conversion (INR)
    days_to_response        SMALLINT,
    
    CONSTRAINT fk_campaign_response_campaign FOREIGN KEY (campaign_id)
        REFERENCES dim_campaign(campaign_id),
    CONSTRAINT fk_campaign_response_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id),
    CONSTRAINT fk_campaign_response_date FOREIGN KEY (date_key)
        REFERENCES dim_date(date_key),
    CONSTRAINT chk_funnel_logic CHECK (
        -- Funnel must be sequential: contacted → opened → clicked → accepted
        (was_accepted = FALSE OR was_clicked = TRUE) AND
        (was_clicked = FALSE OR was_opened = TRUE) AND
        (was_opened = FALSE OR was_contacted = TRUE)
    )
);

COMMENT ON TABLE fact_campaign_responses IS 'Campaign response funnel with sequential conversion logic (contacted→opened→clicked→accepted).';
COMMENT ON COLUMN fact_campaign_responses.conversion_value IS 'Revenue attributed to campaign conversion in INR. Based on customer spending level.';


-- ============================================================
-- SEED DATA: dim_product (12 Indian Banking Products)
-- ============================================================
INSERT INTO dim_product (product_id, product_name, product_category, product_type, annual_fee, interest_rate, min_balance, launch_date, is_active)
VALUES
    (1,  'Savings Account',           'Deposits',    'Savings',         0,      3.50,  1000.00,    '2010-01-01', TRUE),
    (2,  'Current Account',           'Deposits',    'Current',         0,      0.00,  10000.00,   '2010-01-01', TRUE),
    (3,  'Fixed Deposit',             'Deposits',    'Term Deposit',    0,      7.10,  25000.00,   '2010-01-01', TRUE),
    (4,  'Credit Card - Blue',        'Cards',       'Basic',           499,    36.00, NULL,       '2012-01-01', TRUE),
    (5,  'Credit Card - Silver',      'Cards',       'Silver',          999,    30.00, NULL,       '2012-06-01', TRUE),
    (6,  'Credit Card - Gold',        'Cards',       'Gold',            2499,   24.00, NULL,       '2013-01-01', TRUE),
    (7,  'Credit Card - Platinum',    'Cards',       'Platinum',        4999,   18.00, NULL,       '2014-01-01', TRUE),
    (8,  'Personal Loan',             'Loans',       'Unsecured',       0,      12.50, NULL,       '2011-01-01', TRUE),
    (9,  'Home Loan',                 'Loans',       'Secured',         0,      8.50,  NULL,       '2010-01-01', TRUE),
    (10, 'Vehicle Loan',              'Loans',       'Secured',         0,      9.75,  NULL,       '2011-06-01', TRUE),
    (11, 'Health Insurance',          'Insurance',   'Health',          0,      NULL,  500000.00,  '2015-01-01', TRUE),
    (12, 'Mutual Fund SIP',           'Investments', 'Equity',          0,      NULL,  500.00,     '2016-01-01', TRUE);


-- ============================================================
-- SEED DATA: dim_campaign (5 Bank Campaigns)
-- ============================================================
INSERT INTO dim_campaign (campaign_id, campaign_name, campaign_type, campaign_channel, target_segment, start_date, end_date, budget, objective, status)
VALUES
    (1, 'Credit Limit Upgrade',      'Email',             'Digital',   'High Utilization',   '2024-01-15', '2024-03-15', 500000,  'Cross-sell',  'Completed'),
    (2, 'Premium Card Upgrade',      'Outbound Call',     'Direct',    'Affluent',           '2024-04-01', '2024-06-30', 800000,  'Upsell',      'Completed'),
    (3, 'Re-engagement Offer',       'SMS',               'Digital',   'At Risk',            '2024-07-01', '2024-08-31', 300000,  'Retention',   'Completed'),
    (4, 'Cross-sell Insurance',      'Push Notification', 'Digital',   'Mass',               '2024-09-01', '2024-11-30', 450000,  'Cross-sell',  'Completed'),
    (5, 'Loyalty Rewards Program',   'Email',             'Digital',   'Loyal',              '2024-10-01', '2024-12-31', 600000,  'Engagement',  'Completed');


-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- Run these after loading data to validate the schema:

-- Check table existence
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'customer360' ORDER BY table_name;

-- Check foreign key constraints
-- SELECT conname, conrelid::regclass, confrelid::regclass
-- FROM pg_constraint WHERE contype = 'f' AND connamespace = 'customer360'::regnamespace;

-- Check row counts
-- SELECT 'dim_customer' AS tbl, COUNT(*) FROM customer360.dim_customer
-- UNION ALL SELECT 'dim_product', COUNT(*) FROM customer360.dim_product
-- UNION ALL SELECT 'dim_campaign', COUNT(*) FROM customer360.dim_campaign
-- UNION ALL SELECT 'dim_date', COUNT(*) FROM customer360.dim_date
-- UNION ALL SELECT 'fact_transactions', COUNT(*) FROM customer360.fact_transactions
-- UNION ALL SELECT 'fact_service_logs', COUNT(*) FROM customer360.fact_service_logs
-- UNION ALL SELECT 'fact_campaign_responses', COUNT(*) FROM customer360.fact_campaign_responses;
