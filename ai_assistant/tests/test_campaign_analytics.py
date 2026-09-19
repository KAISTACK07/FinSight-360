"""
FinSight 360 Campaign Targeting & Experimentation Tests
"""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ai_assistant.intent_detector import detect_intent, Intent
from ai_assistant.sql_validator import validate_sql
from src.etl.campaign_features import (
    aggregate_customer_propensity,
    audit_campaign_leakage,
    build_model_matrix,
    calculate_target_priority,
)
from src.ml.campaign_experiment import (
    assign_control_treatment,
    build_synthetic_experiment_outcomes,
    calculate_experiment_metrics,
    validate_assignment_balance,
)


class TestCampaignIntents:
    def test_retention_intent(self):
        assert detect_intent("Who should we target for retention?") == Intent.AUDIENCE_RECOMMENDATION

    def test_propensity_intent(self):
        assert detect_intent("Which segment has the highest campaign propensity?") == Intent.CAMPAIGN_PROPENSITY

    def test_experiment_intent(self):
        assert detect_intent("Did treatment perform better than control?") == Intent.EXPERIMENT_ANALYSIS

    def test_campaign_performance_intent(self):
        assert detect_intent("Which campaign had the highest conversion?") == Intent.CAMPAIGN_PERFORMANCE


class TestCampaignSqlValidation:
    def test_campaign_targeting_query_is_allowed(self):
        sql = "SELECT * FROM customer360.v_campaign_targeting LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid, result.error

    def test_campaign_experiment_metrics_query_is_allowed(self):
        sql = "SELECT * FROM customer360.campaign_experiment_metrics LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid, result.error


class TestCampaignFeatures:
    def test_feature_matrix_and_leakage_audit(self):
        df = pd.DataFrame([
            {
                "customer_id": 1,
                "age": 40,
                "tenure_months_at_campaign": 12,
                "total_products_held": 3,
                "credit_utilization_ratio": 0.4,
                "months_inactive_12m": 2,
                "contacts_count_12m": 1,
                "hist_frequency": 20,
                "hist_monetary": 50000,
                "hist_avg_transaction_value": 2500,
                "hist_recency_days": 15,
                "campaign_budget": 100000,
                "gender": "Male",
                "income_bracket": "Above ₹15L",
                "card_category": "Gold",
                "preferred_channel": "Mobile Banking",
                "campaign_type": "Email",
                "campaign_channel": "Digital",
                "campaign_objective": "Retention",
                "target_segment": "Premium Customers",
            }
        ])
        matrix, feature_columns = build_model_matrix(df)
        assert not matrix.empty
        audit = audit_campaign_leakage(feature_columns)
        assert audit["passed"]

    def test_target_priority_normalization(self, monkeypatch):
        propensity_df = pd.DataFrame({"customer_id": [1, 2], "propensity_score": [0.8, 0.2]})
        enrichment = pd.DataFrame({
            "customer_id": [1, 2],
            "predicted_clv_12m": [100000, 5000],
            "churn_probability": [0.7, 0.1],
        })

        monkeypatch.setattr("src.etl.campaign_features.pd.read_sql", lambda *args, **kwargs: enrichment)
        result = calculate_target_priority(propensity_df, engine=object())
        assert result["target_priority_score"].between(0, 1).all()
        assert set(result["priority_tier"].unique()) <= {"Low", "Medium", "High"}

    def test_customer_propensity_aggregation(self):
        scored_rows = pd.DataFrame({
            "customer_id": [1, 1, 2],
            "campaign_probability": [0.8, 0.6, 0.2],
        })
        result = aggregate_customer_propensity(scored_rows)
        assert result.loc[result["customer_id"] == 1, "propensity_score"].iloc[0] == pytest.approx(0.7)


class TestCampaignExperimentation:
    def test_assignment_balance(self):
        audience = pd.DataFrame({"customer_id": list(range(1, 11))})
        assignments = assign_control_treatment(audience, campaign_id=3, seed=42)
        balance = validate_assignment_balance(assignments)
        assert balance["passed"]
        assert set(assignments["assignment_group"].unique()) == {"Control", "Treatment"}

    def test_experiment_metrics(self):
        outcomes = pd.DataFrame({
            "assignment_group": ["Control", "Control", "Treatment", "Treatment"],
            "converted": [False, True, True, True],
        })
        metrics = calculate_experiment_metrics(outcomes)
        assert metrics["control_customers"] == 2
        assert metrics["treatment_customers"] == 2
        assert metrics["absolute_lift"] >= 0

    def test_zero_denominator(self):
        outcomes = pd.DataFrame({"assignment_group": [], "converted": []})
        metrics = calculate_experiment_metrics(outcomes)
        assert metrics["control_conversion_rate"] == 0.0
        assert metrics["treatment_conversion_rate"] == 0.0

    def test_synthetic_outcomes_shape(self):
        assignments = pd.DataFrame({
            "experiment_id": ["E1", "E1"],
            "campaign_id": [3, 3],
            "customer_id": [1, 2],
            "assignment_group": ["Control", "Treatment"],
        })
        propensity = pd.DataFrame({"customer_id": [1, 2], "propensity_score": [0.2, 0.8]})
        outcomes = build_synthetic_experiment_outcomes(assignments, propensity, seed=42)
        assert set(outcomes.columns) == {
            "experiment_id", "campaign_id", "customer_id", "assignment_group", "was_exposed", "converted", "conversion_value", "is_synthetic"
        }
        assert outcomes["is_synthetic"].all()
