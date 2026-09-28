-- ============================================================
-- FinSight 360 — Redshift star schema (gold → warehouse)
-- ============================================================
-- Mirrors the PostgreSQL star schema (src/sql/00_create_schema.sql)
-- but tuned for Redshift's MPP engine:
--
--   * DISTSTYLE / DISTKEY  -> co-locate fact rows with the customer
--                             dimension so joins stay node-local
--   * SORTKEY              -> date_key first for time-range scans /
--                             zone-map pruning
--   * Small dims -> DISTSTYLE ALL (replicated to every node)
--
-- Redshift ignores PRIMARY KEY / FOREIGN KEY enforcement (they are
-- informational only, used by the planner), so integrity is enforced
-- upstream by the data-quality gates instead.
--
-- When run against the local Postgres stand-in, the Redshift-only
-- keywords are stripped automatically by redshift_load.py.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS customer360;
SET search_path TO customer360;

-- ------------------------------------------------------------
-- Dimensions
-- ------------------------------------------------------------
DROP TABLE IF EXISTS dim_date CASCADE;
CREATE TABLE dim_date (
    date_key            INTEGER      NOT NULL,
    full_date           DATE         NOT NULL,
    day_of_week         SMALLINT,
    day_name            VARCHAR(10),
    day_of_month        SMALLINT,
    week_of_year        SMALLINT,
    month_number        SMALLINT,
    month_name          VARCHAR(10),
    quarter             SMALLINT,
    quarter_name        VARCHAR(5),
    year                SMALLINT,
    is_weekend          BOOLEAN,
    is_holiday          BOOLEAN,
    holiday_name        VARCHAR(50),
    fiscal_year         SMALLINT,
    fiscal_quarter      SMALLINT,
    fiscal_quarter_name VARCHAR(5),
    is_month_start      BOOLEAN,
    is_month_end        BOOLEAN,
    is_salary_week      BOOLEAN
)
DISTSTYLE ALL
SORTKEY (date_key);

DROP TABLE IF EXISTS dim_customer CASCADE;
CREATE TABLE dim_customer (
    customer_id              INTEGER      NOT NULL,
    first_name               VARCHAR(50),
    last_name                VARCHAR(50),
    age                      SMALLINT,
    gender                   VARCHAR(10),
    dependents               SMALLINT,
    education_level          VARCHAR(30),
    marital_status           VARCHAR(20),
    income_bracket           VARCHAR(20),
    city                     VARCHAR(50),
    state                    VARCHAR(50),
    customer_since           DATE,
    customer_tenure_months   SMALLINT,
    customer_status          VARCHAR(10),
    credit_limit             DECIMAL(15,2),
    total_revolving_bal      DECIMAL(15,2),
    avg_open_to_buy          DECIMAL(15,2),
    credit_utilization_ratio DECIMAL(5,4),
    card_category            VARCHAR(10),
    total_products_held      SMALLINT,
    months_inactive_12m      SMALLINT,
    contacts_count_12m       SMALLINT,
    total_trans_amt_12m      DECIMAL(15,2),
    total_trans_ct_12m       INTEGER,
    amt_change_q4_q1         DECIMAL(8,4),
    ct_change_q4_q1          DECIMAL(8,4),
    risk_category            VARCHAR(10),
    preferred_channel        VARCHAR(20)
)
DISTSTYLE ALL
SORTKEY (customer_id);

DROP TABLE IF EXISTS dim_product CASCADE;
CREATE TABLE dim_product (
    product_id       INTEGER      NOT NULL,
    product_name     VARCHAR(50),
    product_category VARCHAR(20),
    product_type     VARCHAR(30),
    annual_fee       DECIMAL(10,2),
    interest_rate    DECIMAL(5,2),
    min_balance      DECIMAL(12,2),
    launch_date      DATE,
    is_active        BOOLEAN
)
DISTSTYLE ALL
SORTKEY (product_id);

DROP TABLE IF EXISTS dim_campaign CASCADE;
CREATE TABLE dim_campaign (
    campaign_id      INTEGER      NOT NULL,
    campaign_name    VARCHAR(100),
    campaign_type    VARCHAR(30),
    campaign_channel VARCHAR(30),
    target_segment   VARCHAR(30),
    start_date       DATE,
    end_date         DATE,
    budget           DECIMAL(12,2),
    objective        VARCHAR(30),
    status           VARCHAR(15)
)
DISTSTYLE ALL
SORTKEY (campaign_id);

-- ------------------------------------------------------------
-- Facts  (distributed by customer_id, sorted by date_key)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS fact_transactions CASCADE;
CREATE TABLE fact_transactions (
    transaction_id      BIGINT,
    customer_id         INTEGER      NOT NULL,
    product_id          INTEGER,
    date_key            INTEGER,
    transaction_date    TIMESTAMP,
    transaction_type    VARCHAR(20),
    transaction_channel VARCHAR(20),
    merchant_category   VARCHAR(30),
    merchant_name       VARCHAR(100),
    amount              DECIMAL(15,2),
    balance_after       DECIMAL(15,2),
    is_high_value       BOOLEAN
)
DISTSTYLE KEY
DISTKEY (customer_id)
SORTKEY (date_key);

DROP TABLE IF EXISTS fact_service_logs CASCADE;
CREATE TABLE fact_service_logs (
    service_id            BIGINT,
    customer_id           INTEGER      NOT NULL,
    date_key              INTEGER,
    complaint_date        TIMESTAMP,
    complaint_category    VARCHAR(30),
    complaint_subcategory VARCHAR(50),
    priority              VARCHAR(10),
    channel               VARCHAR(20),
    resolution_date       TIMESTAMP,
    resolution_time_hours DECIMAL(8,2),
    status                VARCHAR(15),
    escalation_flag       BOOLEAN,
    csat_score            SMALLINT,
    agent_id              VARCHAR(10)
)
DISTSTYLE KEY
DISTKEY (customer_id)
SORTKEY (date_key);

DROP TABLE IF EXISTS fact_campaign_responses CASCADE;
CREATE TABLE fact_campaign_responses (
    response_id      BIGINT,
    campaign_id      INTEGER,
    customer_id      INTEGER      NOT NULL,
    date_key         INTEGER,
    response_date    TIMESTAMP,
    was_contacted    BOOLEAN,
    was_opened       BOOLEAN,
    was_clicked      BOOLEAN,
    was_accepted     BOOLEAN,
    response_channel VARCHAR(20),
    conversion_value DECIMAL(12,2),
    days_to_response SMALLINT
)
DISTSTYLE KEY
DISTKEY (customer_id)
SORTKEY (date_key);

-- ------------------------------------------------------------
-- Feature mart (output of the Spark window-function stage)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS customer_features CASCADE;
CREATE TABLE customer_features (
    customer_id          INTEGER      NOT NULL,
    last_txn_ts          TIMESTAMP,
    frequency            BIGINT,
    monetary             DECIMAL(18,2),
    avg_txn_amount       DECIMAL(18,2),
    recency_days         INTEGER,
    r_score              SMALLINT,
    f_score              SMALLINT,
    m_score              SMALLINT,
    rfm_score            SMALLINT,
    rolling_3m_amount    DECIMAL(18,2),
    lag_1m_amount        DECIMAL(18,2),
    lag_3m_amount        DECIMAL(18,2),
    mom_change           DECIMAL(18,2),
    tenure_months        SMALLINT,
    feature_generated_at TIMESTAMP
)
DISTSTYLE KEY
DISTKEY (customer_id)
SORTKEY (customer_id);
