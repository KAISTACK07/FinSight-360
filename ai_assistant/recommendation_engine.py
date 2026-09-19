"""
FinSight 360 AI Analytics Assistant
Recommendation Engine — Data-Grounded Business Recommendations

Generates actionable recommendations based on actual retrieved data.
Rules:
  - Recommendations are deterministic Python logic, NOT LLM hallucination
  - Every recommendation is grounded in observed data
  - Clearly distinguishes: Observed Fact / Model Prediction / Business Recommendation
"""

import logging
from ai_assistant.schema_metadata import get_feature_display_name

logger = logging.getLogger("finsight360.recommendations")

# SHAP driver → actionable recommendation mapping
DRIVER_RECOMMENDATIONS = {
    "months_inactive_12m": {
        "display": "Extended Inactivity",
        "action": "Launch re-engagement campaign with personalized offers",
        "detail": "Customer has been inactive for an extended period. Trigger a targeted re-engagement offer.",
    },
    "total_trans_ct_12m": {
        "display": "Low Transaction Frequency",
        "action": "Send engagement incentives to boost transaction frequency",
        "detail": "Low transaction count indicates disengagement. Consider cashback or reward multiplier offers.",
    },
    "total_trans_amt_12m": {
        "display": "Declining Transaction Value",
        "action": "Offer loyalty incentive or spending-based reward tiers",
        "detail": "Transaction amounts have declined. Consider category-specific cashback to re-stimulate spending.",
    },
    "ct_change_q4_q1": {
        "display": "Transaction Frequency Drop (Q4 vs Q1)",
        "action": "Send seasonal re-engagement campaign",
        "detail": "Transaction frequency has dropped quarter-over-quarter. Immediate outreach recommended.",
    },
    "amt_change_q4_q1": {
        "display": "Spending Decline (Q4 vs Q1)",
        "action": "Offer a personalized spending incentive",
        "detail": "Spending has declined between quarters. Consider offering bonus reward points.",
    },
    "credit_utilization_ratio": {
        "display": "High Credit Utilization",
        "action": "Proactively offer credit limit increase or balance transfer",
        "detail": "High credit utilization may indicate financial stress. Consider a limit increase or EMI conversion.",
    },
    "contacts_count_12m": {
        "display": "High Service Contact Frequency",
        "action": "Escalate to relationship manager for personalized resolution",
        "detail": "Frequent service contacts indicate dissatisfaction. Assign a dedicated relationship manager.",
    },
    "customer_tenure_months": {
        "display": "Short Customer Tenure",
        "action": "Strengthen onboarding experience and early engagement",
        "detail": "Newer customers are at higher churn risk. Enhance the first 90-day experience.",
    },
    "total_products_held": {
        "display": "Low Product Holdings",
        "action": "Cross-sell complementary banking products",
        "detail": "Customer holds few products. Cross-sell opportunity for insurance, FDs, or investment products.",
    },
    "age": {
        "display": "Age-Related Risk Factor",
        "action": "Tailor offers to the customer's life stage",
        "detail": "Age is contributing to churn risk. Ensure product mix aligns with life-stage needs.",
    },
}


def generate_recommendations(intent: str, data: list[dict]) -> list[dict]:
    """
    Generate data-grounded recommendations based on query results.

    Each recommendation contains:
      - category: 'fact' | 'prediction' | 'recommendation'
      - text: the recommendation text
      - priority: 'high' | 'medium' | 'low'
      - grounding: what data supports this recommendation

    Args:
        intent: The detected intent category.
        data: Query result rows.

    Returns:
        List of recommendation dicts.
    """
    if not data:
        return []

    recommendations = []

    if intent in ("CHURN_ANALYSIS", "RISK_ANALYSIS"):
        recommendations.extend(_churn_recommendations(data))
    elif intent == "CLV_ANALYSIS":
        recommendations.extend(_clv_recommendations(data))
    elif intent == "SEGMENT_ANALYSIS":
        recommendations.extend(_segment_recommendations(data))
    elif intent == "RECOMMENDATION":
        recommendations.extend(_cross_cutting_recommendations(data))
    elif intent in ("CAMPAIGN_TARGETING", "CAMPAIGN_PROPENSITY", "AUDIENCE_RECOMMENDATION"):
        recommendations.extend(_campaign_recommendations(data))
    elif intent == "EXPERIMENT_ANALYSIS":
        recommendations.extend(_experiment_recommendations(data))
    elif intent == "CAMPAIGN_PERFORMANCE":
        recommendations.extend(_campaign_performance_recommendations(data))
    elif intent == "REVENUE_ANALYSIS":
        recommendations.extend(_revenue_recommendations(data))

    return recommendations


def _churn_recommendations(data: list[dict]) -> list[dict]:
    """Generate churn/risk-specific recommendations."""
    recs = []

    # Check for SHAP risk drivers in the data
    for row in data[:10]:
        driver_1 = row.get("top_risk_driver_1") or row.get("primary_driver") or row.get("risk_driver")
        if driver_1 and driver_1 in DRIVER_RECOMMENDATIONS:
            rec_info = DRIVER_RECOMMENDATIONS[driver_1]
            churn_prob = row.get("churn_probability")
            customer_name = row.get("customer_name", f"Customer {row.get('customer_id', 'N/A')}")

            recs.append({
                "category": "recommendation",
                "text": rec_info["action"],
                "detail": rec_info["detail"],
                "priority": "high" if (churn_prob and float(churn_prob) > 0.7) else "medium",
                "grounding": f"SHAP analysis identified '{rec_info['display']}' as the primary churn driver for {customer_name}.",
            })

    # Aggregate driver recommendations
    if any("frequency" in str(row.values()) for row in data):
        driver_counts = {}
        for row in data:
            driver = row.get("risk_driver") or row.get("primary_driver") or row.get("top_risk_driver_1")
            count = row.get("frequency") or row.get("customer_count", 1)
            if driver:
                driver_counts[driver] = int(count)

        if driver_counts:
            top_driver = max(driver_counts, key=driver_counts.get)
            if top_driver in DRIVER_RECOMMENDATIONS:
                rec_info = DRIVER_RECOMMENDATIONS[top_driver]
                recs.append({
                    "category": "recommendation",
                    "text": f"Address '{rec_info['display']}' — the most common churn driver across {driver_counts[top_driver]} high-risk customers.",
                    "detail": rec_info["detail"],
                    "priority": "high",
                    "grounding": f"SHAP analysis shows '{rec_info['display']}' is the #1 risk driver affecting {driver_counts[top_driver]} customers.",
                })

    if not recs:
        recs.append({
            "category": "recommendation",
            "text": "Monitor high-risk customers and prioritize retention campaigns for those with high CLV.",
            "priority": "medium",
            "grounding": "General recommendation based on churn analysis.",
        })

    return recs


def _clv_recommendations(data: list[dict]) -> list[dict]:
    """Generate CLV-specific recommendations."""
    recs = []

    # Find platinum/gold tier customers
    high_value_count = sum(1 for row in data if row.get("clv_tier") in ("Platinum", "Gold"))
    if high_value_count > 0:
        recs.append({
            "category": "recommendation",
            "text": f"Protect {high_value_count} high-value customers (Platinum/Gold tier) with premium retention programs.",
            "priority": "high",
            "grounding": f"Data shows {high_value_count} customers in top CLV tiers.",
        })

    return recs


def _segment_recommendations(data: list[dict]) -> list[dict]:
    """Generate segment-specific recommendations."""
    recs = []

    for row in data:
        segment = row.get("behavioral_segment", "")
        count = row.get("customer_count", 0)

        if segment == "Value Seekers":
            recs.append({
                "category": "recommendation",
                "text": f"Engage {count} Value Seekers with cross-sell offers and product upgrades.",
                "priority": "medium",
                "grounding": f"Value Seekers ({count} customers) represent upsell opportunity.",
            })
        elif segment == "Premium Customers":
            recs.append({
                "category": "recommendation",
                "text": f"Retain {count} Premium Customers with exclusive loyalty benefits and relationship management.",
                "priority": "high",
                "grounding": f"Premium Customers ({count}) generate the highest revenue — retention is critical.",
            })

    return recs


def _cross_cutting_recommendations(data: list[dict]) -> list[dict]:
    """Generate recommendations that cross CLV + churn + segments."""
    recs = []

    # Look for high-CLV + high-risk combinations
    for row in data:
        clv_tier = row.get("clv_tier", "")
        risk_tier = row.get("churn_risk_tier", "")
        segment = row.get("behavioral_segment", "")
        count = row.get("customer_count", 0)
        avg_clv = row.get("avg_clv")

        if clv_tier in ("Platinum", "Gold") and risk_tier == "High Risk":
            recs.append({
                "category": "recommendation",
                "text": f"URGENT: {count} {clv_tier}-tier customers in '{segment}' segment are High Risk. "
                        f"Immediate retention intervention needed.",
                "priority": "high",
                "grounding": f"{count} customers with avg CLV ₹{avg_clv:,.0f} are predicted as High Risk churn." if avg_clv else
                             f"{count} high-value customers are predicted as High Risk churn.",
            })
        elif clv_tier == "Bronze" and risk_tier == "Low Risk":
            recs.append({
                "category": "recommendation",
                "text": f"{count} Bronze-tier Low Risk customers: potential growth segment for cross-sell campaigns.",
                "priority": "low",
                "grounding": f"Low risk of churn but low CLV — product cross-sell opportunity.",
            })

    if not recs:
        recs.append({
            "category": "recommendation",
            "text": "Prioritize retention for high-CLV customers with elevated churn risk.",
            "priority": "high",
            "grounding": "General recommendation based on CLV-churn cross-analysis.",
        })

    return recs


def _revenue_recommendations(data: list[dict]) -> list[dict]:
    """Generate revenue-specific recommendations."""
    return [{
        "category": "recommendation",
        "text": "Focus revenue growth efforts on high-frequency segments and underperforming channels.",
        "priority": "medium",
        "grounding": "Revenue analysis data.",
    }]


def _campaign_recommendations(data: list[dict]) -> list[dict]:
    if not data:
        return []
    top_row = max(
        data,
        key=lambda row: float(row.get("target_priority_score") or row.get("avg_priority") or row.get("propensity_score") or 0),
    )
    return [{
        "category": "recommendation",
        "text": f"Prioritize {top_row.get('behavioral_segment', 'the selected audience')} customers in the {top_row.get('priority_tier', top_row.get('propensity_tier', 'High'))} tier for the next campaign wave.",
        "priority": "high",
        "grounding": f"Observed propensity {top_row.get('avg_propensity') or top_row.get('propensity_score')} and CLV {top_row.get('avg_clv') or top_row.get('predicted_clv_12m')}.",
    }]


def _experiment_recommendations(data: list[dict]) -> list[dict]:
    if not data:
        return []
    row = data[0]
    control_rate = float(row.get("control_conversion_rate") or 0)
    treatment_rate = float(row.get("treatment_conversion_rate") or 0)
    lift = float(row.get("absolute_lift") or 0)
    p_value = row.get("p_value")
    if treatment_rate > control_rate:
        text = "Observed treatment conversion is above control; consider scaling the treatment to a broader eligible audience."
        priority = "high"
    else:
        text = "Observed treatment conversion is not above control; review the offer, audience, or channel before expanding."
        priority = "medium"
    grounding = f"Control rate {control_rate:.4f}, treatment rate {treatment_rate:.4f}, absolute lift {lift:.4f}."
    if p_value is not None:
        grounding += f" p-value {float(p_value):.6f}."
    return [{
        "category": "recommendation",
        "text": text,
        "priority": priority,
        "grounding": grounding,
    }]


def _campaign_performance_recommendations(data: list[dict]) -> list[dict]:
    if not data:
        return []
    best = max(data, key=lambda row: float(row.get("conversion_rate_pct") or 0))
    return [{
        "category": "recommendation",
        "text": f"Replicate the best-performing campaign objective: {best.get('campaign_name', 'the top campaign')}.",
        "priority": "medium",
        "grounding": f"Highest observed conversion rate: {best.get('conversion_rate_pct')}.",
    }]



def format_shap_drivers(row: dict) -> list[dict]:
    """
    Format SHAP risk drivers from a query result row into a human-readable list.

    Args:
        row: A dict containing top_risk_driver_1/2/3 fields.

    Returns:
        List of dicts with 'rank', 'feature', 'display_name', 'recommendation'.
    """
    drivers = []
    for i in range(1, 4):
        feature = row.get(f"top_risk_driver_{i}")
        if feature:
            rec_info = DRIVER_RECOMMENDATIONS.get(feature, {})
            drivers.append({
                "rank": i,
                "feature": feature,
                "display_name": get_feature_display_name(feature),
                "recommendation": rec_info.get("action", "Monitor this factor."),
            })
    return drivers
