-- ============================================================
-- FinSight 360
-- Campaign Propensity, Targeting, and Experimentation Structures
-- ============================================================

CREATE SCHEMA IF NOT EXISTS customer360;
SET search_path TO customer360;

-- ------------------------------------------------------------
-- 1. Campaign Propensity & Targeting
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_campaign_propensity (
    customer_id             INTEGER         PRIMARY KEY,
    propensity_score        DECIMAL(5,4)    NOT NULL CHECK (propensity_score BETWEEN 0 AND 1),
    propensity_tier         VARCHAR(20)     NOT NULL CHECK (propensity_tier IN ('Low', 'Medium', 'High')),
    target_priority_score   DECIMAL(5,4)    NOT NULL CHECK (target_priority_score BETWEEN 0 AND 1),
    priority_tier           VARCHAR(20)     NOT NULL CHECK (priority_tier IN ('Low', 'Medium', 'High')),
    normalized_clv          DECIMAL(5,4)    NOT NULL DEFAULT 0 CHECK (normalized_clv BETWEEN 0 AND 1),
    model_version           VARCHAR(50)     NOT NULL DEFAULT 'campaign_propensity_v1',
    prediction_date         DATE            NOT NULL DEFAULT CURRENT_DATE,
    is_synthetic_training   BOOLEAN         NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_propensity_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id)
);

COMMENT ON TABLE ml_campaign_propensity IS 'Campaign response propensity model outputs and target priority heuristic. Training response history is synthetic/generated demo data where applicable.';
COMMENT ON COLUMN ml_campaign_propensity.target_priority_score IS 'Business heuristic: 0.4 propensity + 0.4 normalized CLV + 0.2 churn probability. Not a predictive probability.';

CREATE INDEX IF NOT EXISTS idx_campaign_propensity_tier
    ON ml_campaign_propensity(propensity_tier);
CREATE INDEX IF NOT EXISTS idx_campaign_priority_tier
    ON ml_campaign_propensity(priority_tier);
CREATE INDEX IF NOT EXISTS idx_campaign_priority_score
    ON ml_campaign_propensity(target_priority_score DESC);

-- ------------------------------------------------------------
-- 2. Campaign Experiments: Assignment
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_experiments (
    experiment_id           VARCHAR(80)     NOT NULL,
    campaign_id             INTEGER         NOT NULL,
    customer_id             INTEGER         NOT NULL,
    assignment_group        VARCHAR(20)     NOT NULL CHECK (assignment_group IN ('Control', 'Treatment')),
    assignment_date         DATE            NOT NULL DEFAULT CURRENT_DATE,
    random_seed             INTEGER         NOT NULL DEFAULT 42,
    eligibility_rule        TEXT            NOT NULL,
    is_synthetic            BOOLEAN         NOT NULL DEFAULT TRUE,

    PRIMARY KEY (experiment_id, customer_id),
    CONSTRAINT fk_experiment_campaign FOREIGN KEY (campaign_id)
        REFERENCES dim_campaign(campaign_id),
    CONSTRAINT fk_experiment_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id)
);

COMMENT ON TABLE campaign_experiments IS 'Control/Treatment assignments for campaign experiments. Synthetic where is_synthetic = TRUE.';

CREATE INDEX IF NOT EXISTS idx_campaign_experiments_campaign
    ON campaign_experiments(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_experiments_group
    ON campaign_experiments(experiment_id, assignment_group);

-- ------------------------------------------------------------
-- 3. Campaign Experiment Outcomes
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_experiment_outcomes (
    experiment_id           VARCHAR(80)     NOT NULL,
    campaign_id             INTEGER         NOT NULL,
    customer_id             INTEGER         NOT NULL,
    assignment_group        VARCHAR(20)     NOT NULL CHECK (assignment_group IN ('Control', 'Treatment')),
    was_exposed             BOOLEAN         NOT NULL DEFAULT FALSE,
    converted               BOOLEAN         NOT NULL DEFAULT FALSE,
    conversion_value        DECIMAL(12,2)   NOT NULL DEFAULT 0,
    outcome_date            DATE            NOT NULL DEFAULT CURRENT_DATE,
    is_synthetic            BOOLEAN         NOT NULL DEFAULT TRUE,

    PRIMARY KEY (experiment_id, customer_id),
    CONSTRAINT fk_experiment_outcome_assignment FOREIGN KEY (experiment_id, customer_id)
        REFERENCES campaign_experiments(experiment_id, customer_id),
    CONSTRAINT fk_experiment_outcome_campaign FOREIGN KEY (campaign_id)
        REFERENCES dim_campaign(campaign_id),
    CONSTRAINT fk_experiment_outcome_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id)
);

COMMENT ON TABLE campaign_experiment_outcomes IS 'Observed experiment outcomes at customer-campaign-experiment grain. Synthetic where is_synthetic = TRUE.';

CREATE INDEX IF NOT EXISTS idx_campaign_outcomes_group
    ON campaign_experiment_outcomes(experiment_id, assignment_group);
CREATE INDEX IF NOT EXISTS idx_campaign_outcomes_converted
    ON campaign_experiment_outcomes(converted);


-- ------------------------------------------------------------
-- 4. Campaign Experiment Metrics
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_experiment_metrics (
    experiment_id               VARCHAR(80)     NOT NULL,
    campaign_id                 INTEGER         NOT NULL,
    campaign_name               VARCHAR(255)    NOT NULL,
    objective                   VARCHAR(50)     NOT NULL,
    control_customers           INTEGER         NOT NULL DEFAULT 0,
    treatment_customers         INTEGER         NOT NULL DEFAULT 0,
    control_responses           INTEGER         NOT NULL DEFAULT 0,
    treatment_responses         INTEGER         NOT NULL DEFAULT 0,
    control_conversion_rate     DECIMAL(10,6)   NOT NULL DEFAULT 0,
    treatment_conversion_rate   DECIMAL(10,6)   NOT NULL DEFAULT 0,
    absolute_lift               DECIMAL(10,6)   NOT NULL DEFAULT 0,
    relative_lift               DECIMAL(10,6),
    z_statistic                 DECIMAL(18,8),
    p_value                     DECIMAL(18,8),
    confidence_interval_low     DECIMAL(18,8),
    confidence_interval_high    DECIMAL(18,8),
    includes_synthetic_data     BOOLEAN         NOT NULL DEFAULT TRUE,
    calculated_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (experiment_id, campaign_id),
    CONSTRAINT fk_campaign_metrics_campaign FOREIGN KEY (campaign_id)
        REFERENCES dim_campaign(campaign_id)
);

COMMENT ON TABLE campaign_experiment_metrics IS 'Experiment-level summary metrics for Control vs Treatment analysis. Synthetic where includes_synthetic_data = TRUE.';

CREATE INDEX IF NOT EXISTS idx_campaign_metrics_campaign
    ON campaign_experiment_metrics(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_metrics_pvalue
    ON campaign_experiment_metrics(p_value);
-- ------------------------------------------------------------
-- 4. Views for Power BI and AI Assistant
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_campaign_targeting AS
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.customer_status,
    c.income_bracket,
    c.card_category,
    COALESCE(s.behavioral_segment, 'Unsegmented') AS behavioral_segment,
    COALESCE(clv.predicted_clv_12m, 0) AS predicted_clv_12m,
    COALESCE(ch.churn_probability, 0) AS churn_probability,
    p.propensity_score,
    p.propensity_tier,
    p.target_priority_score,
    p.priority_tier,
    p.normalized_clv,
    p.model_version,
    p.prediction_date,
    p.is_synthetic_training
FROM dim_customer c
JOIN ml_campaign_propensity p ON c.customer_id = p.customer_id
LEFT JOIN ml_customer_segments s ON c.customer_id = s.customer_id
LEFT JOIN clv_predictions clv ON c.customer_id = clv.customer_id
LEFT JOIN ml_churn_predictions ch ON c.customer_id = ch.customer_id;

COMMENT ON VIEW v_campaign_targeting IS 'Customer-level audience selection view with propensity, CLV, churn probability, segment, and priority tier.';

CREATE OR REPLACE VIEW v_campaign_audience_summary AS
SELECT
    behavioral_segment,
    priority_tier,
    propensity_tier,
    COUNT(*) AS eligible_customers,
    ROUND(AVG(predicted_clv_12m)::numeric, 2) AS avg_clv,
    ROUND(AVG(churn_probability)::numeric, 4) AS avg_churn_probability,
    ROUND(AVG(propensity_score)::numeric, 4) AS avg_propensity,
    ROUND(AVG(target_priority_score)::numeric, 4) AS avg_target_priority
FROM v_campaign_targeting
GROUP BY behavioral_segment, priority_tier, propensity_tier;

CREATE OR REPLACE VIEW v_campaign_experiment_metrics AS
SELECT
    experiment_id,
    campaign_id,
    campaign_name,
    objective,
    control_customers,
    treatment_customers,
    control_responses,
    treatment_responses,
    control_conversion_rate,
    treatment_conversion_rate,
    absolute_lift,
    relative_lift,
    z_statistic,
    p_value,
    confidence_interval_low,
    confidence_interval_high,
    includes_synthetic_data,
    calculated_at
FROM campaign_experiment_metrics;

COMMENT ON VIEW v_campaign_experiment_metrics IS 'Experiment-level Control vs Treatment conversion and lift metrics.';
