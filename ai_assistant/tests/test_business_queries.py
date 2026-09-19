"""
FinSight 360 AI Analytics Assistant
Business Query Integration Tests

Tests end-to-end query processing for representative business questions.
Requires a running PostgreSQL database with the customer360 schema.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import pytest
from ai_assistant.intent_detector import detect_intent
from ai_assistant.sql_generator import generate_and_validate_sql
from ai_assistant.database_service import execute_query, test_connection as check_db_connection, DatabaseError


# Skip all tests if database is not available
pytestmark = pytest.mark.skipif(
    not check_db_connection(),
    reason="PostgreSQL database not available"
)


class TestRevenueQueries:
    def test_total_revenue(self):
        result = generate_and_validate_sql("What was the total revenue?", "REVENUE_ANALYSIS")
        assert result["sql"] is not None, f"SQL generation failed: {result['error']}"
        data = execute_query(result["sql"])
        assert data["row_count"] > 0
        assert "total_revenue" in data["columns"] or len(data["rows"]) > 0

    def test_average_transaction(self):
        result = generate_and_validate_sql("What is the average transaction value?", "REVENUE_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0


class TestCLVQueries:
    def test_avg_clv(self):
        result = generate_and_validate_sql("What is the average CLV?", "CLV_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0

    def test_top_clv(self):
        result = generate_and_validate_sql("Show the top 10 customers by predicted CLV", "CLV_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0
        assert data["row_count"] <= 10

    def test_segment_clv(self):
        result = generate_and_validate_sql("Which segment has the highest CLV?", "CLV_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0


class TestChurnQueries:
    def test_high_risk_customers(self):
        result = generate_and_validate_sql("Which customers are at high risk of churn?", "CHURN_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0

    def test_churn_percentage(self):
        result = generate_and_validate_sql("What percentage of customers are high risk?", "CHURN_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0

    def test_segment_churn(self):
        result = generate_and_validate_sql("Which segment has the highest churn probability?", "CHURN_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0


class TestSegmentQueries:
    def test_segment_distribution(self):
        result = generate_and_validate_sql("How many Premium customers do we have?", "SEGMENT_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0

    def test_segment_frequency(self):
        result = generate_and_validate_sql("Which segment has the highest transaction frequency?", "SEGMENT_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0


class TestRiskQueries:
    def test_churn_drivers(self):
        result = generate_and_validate_sql("What are the biggest churn drivers?", "RISK_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0

    def test_customer_risk(self):
        """Test risk analysis for a specific customer (using known customer ID from the dataset)."""
        result = generate_and_validate_sql("Why is customer 818770008 at high risk?", "RISK_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0
        # Verify SHAP drivers are present
        row = data["rows"][0]
        assert "top_risk_driver_1" in row


class TestRecommendationQueries:
    def test_retention_recommendations(self):
        result = generate_and_validate_sql(
            "Which customers should we prioritize for retention?", "RECOMMENDATION"
        )
        assert result["sql"] is not None
        data = execute_query(result["sql"])
        assert data["row_count"] > 0


class TestSHAPCorrectness:
    """Verify that SHAP explanations come from actual stored data."""

    def test_shap_drivers_match_database(self):
        """Verify that risk driver values are actual feature names from the model."""
        valid_features = {
            "age", "customer_tenure_months", "total_products_held",
            "credit_utilization_ratio", "months_inactive_12m", "contacts_count_12m",
            "total_trans_amt_12m", "total_trans_ct_12m", "amt_change_q4_q1", "ct_change_q4_q1"
        }
        result = generate_and_validate_sql("What are the biggest churn drivers?", "RISK_ANALYSIS")
        assert result["sql"] is not None
        data = execute_query(result["sql"])

        for row in data["rows"]:
            driver = row.get("risk_driver") or row.get("primary_driver") or row.get("top_risk_driver_1")
            if driver:
                assert driver in valid_features, f"Unknown SHAP driver: {driver}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
