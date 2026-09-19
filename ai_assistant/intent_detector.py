"""
FinSight 360 AI Analytics Assistant
Intent Detection Module

Classifies user questions into controlled business intents.
Two-tier approach:
  1. Deterministic keyword matching (fast, reliable)
  2. LLM fallback for ambiguous questions
"""

import re
from enum import Enum
from typing import Optional


class Intent(str, Enum):
    """Controlled set of business intents the AI assistant supports."""
    REVENUE_ANALYSIS = "REVENUE_ANALYSIS"
    CUSTOMER_ANALYSIS = "CUSTOMER_ANALYSIS"
    CLV_ANALYSIS = "CLV_ANALYSIS"
    CHURN_ANALYSIS = "CHURN_ANALYSIS"
    SEGMENT_ANALYSIS = "SEGMENT_ANALYSIS"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    COMPARISON = "COMPARISON"
    TREND_ANALYSIS = "TREND_ANALYSIS"
    RECOMMENDATION = "RECOMMENDATION"
    CAMPAIGN_TARGETING = "CAMPAIGN_TARGETING"
    CAMPAIGN_PROPENSITY = "CAMPAIGN_PROPENSITY"
    EXPERIMENT_ANALYSIS = "EXPERIMENT_ANALYSIS"
    CAMPAIGN_PERFORMANCE = "CAMPAIGN_PERFORMANCE"
    AUDIENCE_RECOMMENDATION = "AUDIENCE_RECOMMENDATION"
    UNKNOWN = "UNKNOWN"


# Intent descriptions for LLM classification
INTENT_DESCRIPTIONS = {
    Intent.REVENUE_ANALYSIS: "Questions about revenue, transaction amounts, transaction volume, average transaction value, revenue by segment/category/channel/time.",
    Intent.CUSTOMER_ANALYSIS: "Questions about customer demographics, customer count, customer lookup by ID/name, customer profiles, high-value customers, customer status.",
    Intent.CLV_ANALYSIS: "Questions about Customer Lifetime Value (CLV), predicted CLV, CLV tiers (Platinum/Gold/Silver/Bronze), CLV ranking, future customer value.",
    Intent.CHURN_ANALYSIS: "Questions about churn, churn probability, churn rate, churned customers, attrition, customers at risk of leaving.",
    Intent.SEGMENT_ANALYSIS: "Questions about customer segments (Premium/Loyal/Growth/Value Seekers), segment comparison, segment size, segment characteristics.",
    Intent.RISK_ANALYSIS: "Questions about risk drivers, SHAP explanations, why a customer is high risk, churn factors, top risk contributors.",
    Intent.COMPARISON: "Questions comparing two or more segments, tiers, categories, or groups side-by-side.",
    Intent.TREND_ANALYSIS: "Questions about trends over time, monthly/quarterly/yearly patterns, growth, decline, seasonal patterns.",
    Intent.RECOMMENDATION: "Questions asking for actionable recommendations, what to do about specific customers/segments, retention strategies, next best action.",
    Intent.CAMPAIGN_TARGETING: "Questions about which customers to target, target priority, and audience selection.",
    Intent.CAMPAIGN_PROPENSITY: "Questions about campaign response propensity, likelihood to respond, and propensity scores or tiers.",
    Intent.EXPERIMENT_ANALYSIS: "Questions about A/B testing, experiment results, conversion lift, control vs treatment performance.",
    Intent.CAMPAIGN_PERFORMANCE: "Questions about how a campaign performed, conversion rates, and ROI.",
    Intent.AUDIENCE_RECOMMENDATION: "Questions asking for an audience recommendation for a specific campaign or objective.",
    Intent.UNKNOWN: "Questions that do not fit any of the above categories or are outside the scope of the analytics platform.",
}

# Keyword patterns for deterministic classification
# Order matters — more specific patterns first
_KEYWORD_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.AUDIENCE_RECOMMENDATION, [
        r"\bwhich\s+audience\b", r"\bwho\s+should\s+we\s+target\b", 
        r"\brecommend\b.*\baudience\b", r"\baudience\s+recommendation\b",
        r"\btargeting\s+recommendation\b",
    ]),
    (Intent.RECOMMENDATION, [
        r"\bwhat\s+should\s+we\s+do\b",
        r"\brecommend\w*\b",
        r"\bprioritize\b", r"\bretention\s+strateg\w*\b",
        r"\baction\s+(?:should|can|to)\b",
        r"\bnext\s+best\s+action\b",
        r"\bwhat\s+action\b",
        r"\bhow\s+(?:to|can\s+we)\s+retain\b",
    ]),
    (Intent.EXPERIMENT_ANALYSIS, [
        r"\bexperiment\b", r"\bcontrol\s+(?:vs|against|and)\s+treatment\b", 
        r"\btreatment\b", r"\bcontrol\s+group\b", r"\ba/b\s+test\w*\b", 
        r"\blift\b", r"\bp-value\b", r"\bsignificance\b",
    ]),
    (Intent.CAMPAIGN_PERFORMANCE, [
        r"\bcampaign\s+performance\b", r"\bhow\s+did\s+(?:the\s+)?campaign\b", 
        r"\bconversion\s+rate\b", r"\bresponses\b", r"\baccepted\b", 
        r"\bconversion\b", r"\bcampaign\b.*\bperform\b",
    ]),
    (Intent.CAMPAIGN_TARGETING, [
        r"\btarget\s+priority\b", r"\btarget\w*\b", r"\btargetable\b", 
        r"\baudience\b", r"\bpriority\s+tier\b", r"\beligible\s+customers\b",
    ]),
    (Intent.CAMPAIGN_PROPENSITY, [
        r"\bpropensity\b", r"\blikelihood\s+to\s+respond\b", 
        r"\blikely\s+to\s+respond\b", r"\bpropensity\s+tier\b", 
        r"\bresponse\s+probability\b",
    ]),
    (Intent.RISK_ANALYSIS, [
        r"\brisk\s+driver\w*\b", r"\bshap\b",
        r"\bwhy\s+is\s+(?:customer|this)\b.*\brisk\b",
        r"\bwhy\s+(?:is|are)\b.*\bhigh\s+risk\b",
        r"\bchurn\s+driver\w*\b", r"\bchurn\s+factor\w*\b",
        r"\brisk\s+factor\w*\b", r"\bcontribut\w*\s+to\s+churn\b",
        r"\bbiggest\s+(?:churn|risk)\b",
        r"\bwhy\s+(?:might|would|will)\b.*\bchurn\b",
        r"\bwhat\s+(?:causes|drives)\s+churn\b",
        r"\bcommon\b.*\brisk\b",
    ]),
    (Intent.COMPARISON, [
        r"\bcompare\b", r"\bcomparison\b",
        r"\bvs\.?\b", r"\bversus\b",
        r"\bdifference\s+between\b",
        r"\b(?:premium|loyal|growth|value)\b.*\b(?:premium|loyal|growth|value)\b",
    ]),
    (Intent.REVENUE_ANALYSIS, [
        r"\brevenue\b", r"\btransactions?\s+(?:amount|value|volume)\b",
        r"\btotal\s+(?:revenue|sales|spending)\b",
        r"\baverage\s+transactions?\b",
        r"\btransactions?\s+(?:count|frequency)\b",
        r"\bspending\b", r"\bspend\b",
        r"\bmerchant\b", r"\bchannel\s+(?:revenue|volume)\b",
    ]),
    (Intent.CLV_ANALYSIS, [
        r"\bclv\b", r"\bcustomer\s+lifetime\s+value\b",
        r"\blifetime\s+value\b",
        r"\bpredicted\s+(?:clv|value)\b",
        r"\bclv\s+tier\b",
        r"\bfuture\s+(?:value|revenue)\b",
        r"\bplatinum\s+(?:tier|customers?)\b",
        r"\bgold\s+tier\b",
    ]),
    (Intent.CHURN_ANALYSIS, [
        r"\bchurn\w*\b", r"\battrition\b",
        r"\brisk\s+of\s+(?:leaving|churn)\b",
        r"\bhigh\s+risk\b",
        r"\bat\s+risk\b",
    ]),
    (Intent.SEGMENT_ANALYSIS, [
        r"\bsegments?\b", r"\bsegmentation\b",
        r"\bpremium\s+customers?\b", r"\bloyal\s+customers?\b",
        r"\bgrowth\s+customers?\b", r"\bvalue\s+seekers?\b",
        r"\bbehavioral\s+segments?\b",
        r"\bclusters?\b",
    ]),
    (Intent.TREND_ANALYSIS, [
        r"\btrend\w*\b", r"\bover\s+time\b",
        r"\bmonthly\b", r"\bquarterly\b", r"\byearly\b",
        r"\bgrowth\b.*\brate\b",
        r"\blast\s+(?:quarter|month|year)\b",
        r"\bseasonal\b", r"\btime\s+series\b",
    ]),
    (Intent.CUSTOMER_ANALYSIS, [
        r"\bcustomers?\b", r"\bhow\s+many\s+customers?\b",
        r"\bcustomer\s+(?:count|profile|detail|lookup)\b",
        r"\bhigh[\s-]value\s+customers?\b",
        r"\btotal\s+customers?\b",
        r"\bactive\s+customers?\b",
        r"\bcustomer\s+(?:id|#)\s*\d+\b",
        r"\bdemographics?\b",
    ]),
]


def detect_intent_keyword(question: str) -> Optional[Intent]:
    """
    Attempt to classify intent using deterministic keyword matching.
    Returns None if no confident match is found (triggers LLM fallback).
    """
    q_lower = question.lower().strip()

    for intent, patterns in _KEYWORD_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, q_lower):
                return intent

    return None


def detect_intent(question: str, llm_classify_fn=None) -> Intent:
    """
    Classify the user's question into a controlled intent.

    1. Try deterministic keyword matching first (fast, reliable).
    2. If no match, use the LLM classification function if provided.
    3. Default to UNKNOWN if both fail.

    Args:
        question: The user's natural-language question.
        llm_classify_fn: Optional async-compatible function that takes
                         (question, intent_descriptions) and returns an Intent.

    Returns:
        Classified Intent enum value.
    """
    # Tier 1: Keyword-based
    keyword_intent = detect_intent_keyword(question)
    if keyword_intent is not None:
        return keyword_intent

    # Tier 2: LLM-based (if available)
    if llm_classify_fn is not None:
        try:
            llm_intent = llm_classify_fn(question, INTENT_DESCRIPTIONS)
            if llm_intent and llm_intent in Intent.__members__:
                return Intent(llm_intent)
        except Exception:
            pass

    return Intent.UNKNOWN


def get_supported_categories() -> list[dict]:
    """Return a list of supported question categories for the API."""
    return [
        {
            "intent": intent.value,
            "description": desc,
            "examples": _get_intent_examples(intent),
        }
        for intent, desc in INTENT_DESCRIPTIONS.items()
        if intent != Intent.UNKNOWN
    ]


def _get_intent_examples(intent: Intent) -> list[str]:
    """Return example questions for each intent category."""
    examples = {
        Intent.REVENUE_ANALYSIS: [
            "What was the total revenue last quarter?",
            "Which customer segment generates the most revenue?",
            "What is the average transaction value?",
        ],
        Intent.CUSTOMER_ANALYSIS: [
            "How many customers do we have?",
            "Show high-value customers.",
            "How many active customers are there?",
        ],
        Intent.CLV_ANALYSIS: [
            "What is the average CLV?",
            "Which segment has the highest CLV?",
            "Show the top 10 customers by predicted CLV.",
        ],
        Intent.CHURN_ANALYSIS: [
            "Which customers are at high risk of churn?",
            "What percentage of customers are high risk?",
            "Which segment has the highest churn probability?",
        ],
        Intent.SEGMENT_ANALYSIS: [
            "How many Premium customers do we have?",
            "Which segment has the highest transaction frequency?",
            "Compare Premium and Loyal customers.",
        ],
        Intent.RISK_ANALYSIS: [
            "What are the biggest churn drivers?",
            "Why is this customer high risk?",
            "Which risk drivers are most common?",
        ],
        Intent.COMPARISON: [
            "Compare Premium and Value Seekers.",
            "How do Gold and Platinum card holders differ?",
        ],
        Intent.TREND_ANALYSIS: [
            "What was the revenue trend last quarter?",
            "Show monthly transaction trends.",
        ],
        Intent.RECOMMENDATION: [
            "What should we do about high-CLV high-risk customers?",
            "Which customers should we prioritize for retention?",
        ],
        Intent.CAMPAIGN_TARGETING: [
            "Which segment should we target?",
            "Show me the high priority target tier.",
        ],
        Intent.CAMPAIGN_PROPENSITY: [
            "Which segment has the highest campaign propensity?",
            "What is the average propensity score for Premium customers?",
        ],
        Intent.EXPERIMENT_ANALYSIS: [
            "How did treatment perform against control?",
            "What was the conversion lift?",
        ],
        Intent.CAMPAIGN_PERFORMANCE: [
            "Which campaign had the highest conversion?",
            "Show the campaign performance.",
        ],
        Intent.AUDIENCE_RECOMMENDATION: [
            "Who should we target for a retention campaign?",
            "Which audience should we target for a product upgrade?",
        ],
    }
    return examples.get(intent, [])
