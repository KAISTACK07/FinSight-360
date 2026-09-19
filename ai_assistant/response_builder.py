"""
FinSight 360 AI Analytics Assistant
Response Builder — Structured Response Assembly

Assembles the final structured response from all pipeline components.
Tags every piece of information by its source:
  - Database: factual data from PostgreSQL
  - ML Prediction: model-generated predictions
  - SHAP Explanation: model explainability outputs
  - LLM Interpretation: natural-language explanation
"""

import logging
from typing import Any, Optional

from ai_assistant.schema_metadata import get_feature_display_name
from ai_assistant.recommendation_engine import generate_recommendations, format_shap_drivers

logger = logging.getLogger("finsight360.response_builder")


def build_response(
    question: str,
    intent: str,
    sql: Optional[str],
    query_result: Optional[dict],
    explanation: Optional[dict],
    error: Optional[str] = None,
    validation_warnings: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Build the final structured response.

    Args:
        question: Original user question.
        intent: Detected intent.
        sql: The executed SQL query (or None).
        query_result: Result from database_service.execute_query().
        explanation: Result from llm_service.generate_explanation().
        error: Error message if the pipeline failed.
        validation_warnings: Warnings from SQL validation.

    Returns:
        Complete structured response dict.
    """
    if error:
        return _build_error_response(question, intent, error)

    if not query_result or not query_result.get("rows"):
        return _build_empty_response(question, intent, sql)

    data = query_result["rows"]
    columns = query_result["columns"]

    # Generate recommendations
    recommendations = generate_recommendations(intent, data)

    # Format SHAP drivers if present in data
    shap_drivers = []
    for row in data:
        if "top_risk_driver_1" in row:
            shap_drivers = format_shap_drivers(row)
            break

    # Enrich data with display names for SHAP features
    enriched_data = _enrich_data(data)

    # Determine data sources
    sources = _determine_sources(intent, columns)

    # Build the response
    response = {
        "success": True,
        "question": question,
        "intent": intent,
        "sql": sql,
        "data": {
            "columns": columns,
            "rows": enriched_data,
            "row_count": query_result["row_count"],
            "truncated": query_result.get("truncated", False),
        },
        "summary": explanation.get("summary", "") if explanation else _build_basic_summary(data),
        "insights": explanation.get("insights", []) if explanation else [],
        "recommendations": [r for r in (explanation.get("recommendations", []) if explanation else [])],
        "data_recommendations": recommendations,
        "shap_drivers": shap_drivers,
        "sources": sources,
        "warnings": validation_warnings,
    }

    return response


def build_unsupported_response(question: str) -> dict[str, Any]:
    """Build response for unsupported/unknown questions."""
    return {
        "success": False,
        "question": question,
        "intent": "UNKNOWN",
        "sql": None,
        "data": None,
        "summary": (
            "I can currently answer questions about:\n"
            "• **Revenue** — total revenue, average transaction value, revenue by segment\n"
            "• **Customers** — customer counts, profiles, demographics\n"
            "• **CLV** — predicted customer lifetime value, CLV tiers, rankings\n"
            "• **Churn** — churn risk, churn probability, at-risk customers\n"
            "• **Segments** — customer segments (Premium, Loyal, Growth, Value Seekers)\n"
            "• **Risk Drivers** — SHAP-based churn explanations\n"
            "• **Recommendations** — data-backed retention and engagement strategies\n\n"
            "Please rephrase your question to fit one of these categories."
        ),
        "insights": [],
        "recommendations": [],
        "data_recommendations": [],
        "shap_drivers": [],
        "sources": {},
        "warnings": None,
        "error": "Question not understood. Please ask about customers, revenue, CLV, churn, segments, risk, campaigns, or recommendations.",
    }


def _build_error_response(question: str, intent: str, error: str) -> dict[str, Any]:
    """Build response for pipeline errors."""
    return {
        "success": False,
        "question": question,
        "intent": intent,
        "sql": None,
        "data": None,
        "summary": f"I encountered an issue processing your question: {error}",
        "insights": [],
        "recommendations": [],
        "data_recommendations": [],
        "shap_drivers": [],
        "sources": {},
        "warnings": None,
        "error": error,
    }


def _build_empty_response(question: str, intent: str, sql: Optional[str]) -> dict[str, Any]:
    """Build response when query returns no data."""
    return {
        "success": True,
        "question": question,
        "intent": intent,
        "sql": sql,
        "data": {"columns": [], "rows": [], "row_count": 0, "truncated": False},
        "summary": "No data found matching your query. Please try a different question or adjust your criteria.",
        "insights": [],
        "recommendations": [],
        "data_recommendations": [],
        "shap_drivers": [],
        "sources": {"database": True},
        "warnings": None,
    }


def _determine_sources(intent: str, columns: list[str]) -> dict[str, bool]:
    """Determine which data sources contributed to the response."""
    sources = {"database": True}

    ml_columns = {"churn_probability", "churn_risk_tier", "predicted_clv_12m", "clv_tier", "behavioral_segment", "propensity_score", "propensity_tier", "target_priority_score", "priority_tier"}
    shap_columns = {"top_risk_driver_1", "top_risk_driver_2", "top_risk_driver_3"}

    if ml_columns.intersection(set(columns)):
        sources["ml_prediction"] = True

    if shap_columns.intersection(set(columns)):
        sources["shap_explanation"] = True

    # LLM interpretation is always used when we have an explanation
    sources["llm_interpretation"] = True

    return sources


def _enrich_data(data: list[dict]) -> list[dict]:
    """Add human-readable display names for SHAP features in the data."""
    enriched = []
    for row in data:
        new_row = dict(row)
        for key in ("top_risk_driver_1", "top_risk_driver_2", "top_risk_driver_3",
                     "risk_driver", "primary_driver"):
            if key in new_row and new_row[key]:
                display_key = f"{key}_display"
                new_row[display_key] = get_feature_display_name(new_row[key])
        enriched.append(new_row)
    return enriched


def _build_basic_summary(data: list[dict]) -> str:
    """Build a basic summary when no LLM explanation is available."""
    if not data:
        return "No data found."

    row_count = len(data)
    first_row = data[0]

    parts = [f"Found {row_count} result(s)."]
    for key, value in list(first_row.items())[:3]:
        if value is not None:
            display_key = key.replace("_", " ").title()
            parts.append(f"{display_key}: {value}")

    return " ".join(parts)
