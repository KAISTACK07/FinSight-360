# Campaign Targeting & Experimentation Design

## 1. Business Problem
FinSight 360 now extends from customer analytics into campaign targeting, audience selection, experimentation, and conversion measurement. The objective is to identify customers who are valuable, at risk, and likely to respond to a campaign, then measure observed treatment performance with a controlled Control vs Treatment framework.

## 2. Existing Architecture
The solution reuses the current PostgreSQL customer360 warehouse, the existing feature engineering layer, the CLV and churn prediction outputs, the AI assistant SQL pipeline, the React analytics frontend, and the Power BI semantic model.

## 3. Propensity Methodology
The campaign response model is an interpretable Logistic Regression classifier trained on historical campaign response labels from `fact_campaign_responses.was_accepted`. The model scores customer-campaign rows using only pre-campaign features.

## 4. Target Definition
The target is a binary response label: accepted = 1, not accepted = 0. The target is derived from historical campaign response history already present in PostgreSQL.

## 5. Feature Engineering
Features include transaction frequency, monetary value, recency, customer tenure, product count, credit utilization, service contacts, campaign type, campaign channel, and campaign objective. Customer-level CLV and churn outputs are used only after prediction to build the business heuristic, not as model targets.

## 6. Leakage Prevention
The feature set excludes response fields, treatment assignment, conversion value, future transactions, and any post-campaign outcomes. The pipeline performs an explicit leakage audit before training.

## 7. Target Priority Score
Target Priority Score is a business heuristic, not a predictive model. It is computed as:

`0.4 * propensity_score + 0.4 * normalized_clv + 0.2 * churn_probability`

The score is normalized to the 0 to 1 range and bucketed into Low, Medium, and High priority tiers.

## 8. Audience Creation
The primary audience is the high-priority customer population. The system can return customer-level targeting lists as well as segment-level summaries for retention, cross-sell, upgrade, and engagement campaigns.

## 9. A/B Testing
The existing data does not contain a true operational treatment assignment, so the implementation uses a clearly synthetic Control vs Treatment experiment with a fixed random seed. The assignment is reproducible, balanced, and does not force the treatment group to outperform control.

## 10. Metrics
The pipeline persists ROC-AUC, accuracy, precision, recall, F1, PR-AUC, control/treatment conversion rates, absolute lift, relative lift, z-statistic, p-value, and confidence intervals.

## 11. Database Design
The campaign layer adds four minimal structures:

- `ml_campaign_propensity` for customer-level propensity and priority scores
- `campaign_experiments` for Control vs Treatment assignments
- `campaign_experiment_outcomes` for observed outcomes
- `campaign_experiment_metrics` for summarized experiment metrics

## 12. AI Integration
The AI assistant now supports campaign targeting, campaign propensity, experiment analysis, campaign performance, and audience recommendation intents. SQL generation is constrained to the whitelisted customer360 schema, and numerical answers are grounded in PostgreSQL query results.

## 13. Power BI Additions
The semantic model adds campaign propensity, audience targeting, and experiment lift measures without redesigning the dashboard.

## 14. Limitations
Campaign response and experiment data are synthetic where applicable and are used to demonstrate the analytics workflow. The synthetic Control vs Treatment analysis is suitable for measurement workflow validation, not causal production claims.
