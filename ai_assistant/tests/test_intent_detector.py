"""
FinSight 360 AI Analytics Assistant
Intent Detector Tests

Tests that business questions are correctly classified into the right intents.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from ai_assistant.intent_detector import detect_intent, Intent


class TestRevenueIntent:
    def test_total_revenue(self):
        assert detect_intent("What was the total revenue last quarter?") == Intent.REVENUE_ANALYSIS

    def test_average_transaction(self):
        assert detect_intent("What is the average transaction value?") == Intent.REVENUE_ANALYSIS

    def test_segment_revenue(self):
        assert detect_intent("Which customer segment generates the most revenue?") == Intent.REVENUE_ANALYSIS

    def test_segment_frequency(self):
        assert detect_intent("Which segment has the highest transaction frequency?") == Intent.REVENUE_ANALYSIS

    def test_spending(self):
        assert detect_intent("Show spending by merchant category") == Intent.REVENUE_ANALYSIS


class TestCustomerIntent:
    def test_how_many(self):
        assert detect_intent("How many customers do we have?") == Intent.CUSTOMER_ANALYSIS

    def test_high_value(self):
        assert detect_intent("Show high-value customers") == Intent.CUSTOMER_ANALYSIS

    def test_active(self):
        assert detect_intent("How many active customers are there?") == Intent.CUSTOMER_ANALYSIS


class TestCLVIntent:
    def test_average_clv(self):
        assert detect_intent("What is the average CLV?") == Intent.CLV_ANALYSIS

    def test_segment_clv(self):
        assert detect_intent("Which segment has the highest CLV?") == Intent.CLV_ANALYSIS

    def test_top_clv(self):
        assert detect_intent("Show the top 10 customers by predicted CLV") == Intent.CLV_ANALYSIS

    def test_lifetime_value(self):
        assert detect_intent("What is the customer lifetime value?") == Intent.CLV_ANALYSIS


class TestChurnIntent:
    def test_high_risk(self):
        assert detect_intent("Which customers are at high risk of churn?") == Intent.CHURN_ANALYSIS

    def test_percentage(self):
        assert detect_intent("What percentage of customers are high risk?") == Intent.CHURN_ANALYSIS

    def test_segment_churn(self):
        assert detect_intent("Which segment has the highest churn probability?") == Intent.CHURN_ANALYSIS

    def test_at_risk(self):
        assert detect_intent("Show me at risk customers") == Intent.CHURN_ANALYSIS


class TestSegmentIntent:
    def test_premium(self):
        assert detect_intent("How many Premium customers do we have?") == Intent.SEGMENT_ANALYSIS

class TestRiskIntent:
    def test_churn_drivers(self):
        assert detect_intent("What are the biggest churn drivers?") == Intent.RISK_ANALYSIS

    def test_why_high_risk(self):
        assert detect_intent("Why is customer 818770008 at high risk?") == Intent.RISK_ANALYSIS

    def test_common_drivers(self):
        assert detect_intent("Which risk drivers are most common among high-risk customers?") == Intent.RISK_ANALYSIS


class TestComparisonIntent:
    def test_compare(self):
        assert detect_intent("Compare Premium and Loyal customers") == Intent.COMPARISON

    def test_vs(self):
        assert detect_intent("Premium vs Value Seekers CLV") == Intent.COMPARISON


class TestRecommendationIntent:
    def test_what_should(self):
        assert detect_intent("What should we do about high-CLV high-risk customers?") == Intent.RECOMMENDATION

    def test_prioritize(self):
        assert detect_intent("Which customers should the bank prioritize for retention?") == Intent.RECOMMENDATION

    def test_action(self):
        assert detect_intent("What action should we take for Value Seekers?") == Intent.RECOMMENDATION


class TestUnknownIntent:
    def test_gibberish(self):
        assert detect_intent("asdfghjkl") == Intent.UNKNOWN

    def test_unrelated(self):
        assert detect_intent("What is the weather today?") == Intent.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
