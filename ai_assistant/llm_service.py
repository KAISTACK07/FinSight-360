"""
FinSight 360 AI Analytics Assistant
LLM Service — Abstracted LLM Interface

Provides:
  - Intent classification
  - SQL generation from natural language
  - Natural language explanation of query results
  - Business recommendation generation

Supports Google Gemini (primary) with template-based fallback
when no LLM API key is configured.
"""

import os
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("finsight360.llm")

# Lazy-loaded client
_client = None
_provider = None


def _get_client():
    """Initialize and return the LLM client."""
    global _client, _provider

    if _client is not None:
        return _client, _provider

    _provider = os.getenv("AI_LLM_PROVIDER", "gemini").lower()
    api_key = os.getenv("AI_LLM_API_KEY", "")

    if _provider == "gemini" and api_key:
        try:
            from google import genai
            _client = genai.Client(api_key=api_key)
            logger.info("Initialized Google Gemini LLM client")
            return _client, _provider
        except ImportError:
            logger.warning("google-genai not installed, falling back to template mode")
            _provider = "none"
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini: {e}, falling back to template mode")
            _provider = "none"
    elif _provider == "openai" and api_key:
        try:
            import openai
            _client = openai.OpenAI(api_key=api_key)
            logger.info("Initialized OpenAI LLM client")
            return _client, _provider
        except ImportError:
            logger.warning("openai package not installed, falling back to template mode")
            _provider = "none"
    else:
        _provider = "none"
        logger.info("No LLM API configured — using template-based responses")

    _client = "template"  # Sentinel for template mode
    return _client, _provider


def generate_sql(question: str, schema_context: str, intent: str) -> dict:
    """
    Generate a SQL query from a natural-language question.

    Args:
        question: User's question
        schema_context: Schema metadata string
        intent: Detected intent category

    Returns:
        dict with 'sql' and 'explanation' keys
    """
    client, provider = _get_client()

    system_prompt = _build_sql_generation_prompt(schema_context, intent)

    if provider == "gemini":
        return _gemini_generate_sql(client, system_prompt, question)
    elif provider == "openai":
        return _openai_generate_sql(client, system_prompt, question)
    else:
        return _template_generate_sql(question, intent)


def generate_explanation(question: str, intent: str, sql: str,
                         data: list[dict], schema_context: str) -> dict:
    """
    Generate a natural-language explanation of query results.

    Returns:
        dict with 'summary', 'insights', 'recommendations' keys
    """
    client, provider = _get_client()

    if provider in ("gemini", "openai"):
        return _llm_generate_explanation(client, provider, question, intent, sql, data)
    else:
        return _template_generate_explanation(question, intent, data)


def classify_intent(question: str, intent_descriptions: dict) -> Optional[str]:
    """
    Use the LLM to classify the intent of a question.

    Returns:
        Intent string or None if classification fails.
    """
    client, provider = _get_client()

    if provider not in ("gemini", "openai"):
        return None

    prompt = (
        "Classify the following user question into exactly one of these intent categories.\n"
        "Return ONLY the intent name, nothing else.\n\n"
        "Categories:\n"
    )
    for intent_name, desc in intent_descriptions.items():
        prompt += f"- {intent_name.value}: {desc}\n"

    prompt += f"\nUser question: {question}\n\nIntent:"

    try:
        if provider == "gemini":
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text.strip().upper()
        elif provider == "openai":
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
            )
            return response.choices[0].message.content.strip().upper()
    except Exception as e:
        logger.warning(f"LLM intent classification failed: {e}")
        return None


# ============================================================
# GEMINI IMPLEMENTATION
# ============================================================

def _gemini_generate_sql(client, system_prompt: str, question: str) -> dict:
    """Generate SQL using Google Gemini."""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{system_prompt}\n\nUser Question: {question}",
        )
        return _parse_sql_response(response.text)
    except Exception as e:
        logger.error(f"Gemini SQL generation failed: {e}")
        return {"sql": None, "explanation": f"SQL generation failed: {str(e)}"}


# ============================================================
# OPENAI IMPLEMENTATION
# ============================================================

def _openai_generate_sql(client, system_prompt: str, question: str) -> dict:
    """Generate SQL using OpenAI."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        return _parse_sql_response(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"OpenAI SQL generation failed: {e}")
        return {"sql": None, "explanation": f"SQL generation failed: {str(e)}"}


# ============================================================
# EXPLANATION GENERATION
# ============================================================

def _llm_generate_explanation(client, provider: str, question: str,
                              intent: str, sql: str, data: list[dict]) -> dict:
    """Generate explanation using LLM (Gemini or OpenAI)."""
    # Limit data sent to LLM to avoid token overflow
    data_sample = data[:20] if len(data) > 20 else data

    prompt = f"""You are a banking analytics assistant. Analyze these query results and provide a business-friendly response.

Question: {question}
Intent: {intent}
SQL Used: {sql}
Data (up to 20 rows): {json.dumps(data_sample, default=str)}

Respond in this exact JSON format:
{{
    "summary": "A 1-3 sentence business-friendly summary of the findings. Use ₹ for currency. Be precise with numbers.",
    "insights": ["Insight 1", "Insight 2", "Insight 3"],
    "recommendations": ["Recommendation 1", "Recommendation 2"]
}}

Rules:
- The summary must directly answer the question using the data provided.
- Do NOT invent numbers that aren't in the data.
- For SHAP/risk drivers, use the actual feature names from the data.
- Insights should be factual observations from the data.
- Recommendations should be actionable business suggestions grounded in the data.
- If the data is empty, say "No data found matching the query."
- Use ₹ symbol for INR values. Format large numbers with commas (e.g., ₹12,45,000).
"""

    try:
        if provider == "gemini":
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return _parse_explanation_response(response.text)
        elif provider == "openai":
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.3,
            )
            return _parse_explanation_response(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"LLM explanation failed: {e}")
        return _template_generate_explanation(question, intent, data)


# ============================================================
# TEMPLATE-BASED FALLBACK (no LLM)
# ============================================================

def _template_generate_sql(question: str, intent: str) -> dict:
    """Generate SQL using template patterns when no LLM is available."""
    from ai_assistant.schema_metadata import SCHEMA_NAME

    q_lower = question.lower()
    sql = None

    # Revenue templates
    if intent == "REVENUE_ANALYSIS":
        if "average transaction" in q_lower:
            sql = f"SELECT ROUND(AVG(amount), 2) AS avg_transaction_value FROM {SCHEMA_NAME}.fact_transactions"
        elif "total revenue" in q_lower:
            sql = f"SELECT SUM(amount) AS total_revenue FROM {SCHEMA_NAME}.fact_transactions"
        elif "segment" in q_lower and "revenue" in q_lower:
            sql = (
                f"SELECT seg.behavioral_segment, SUM(ft.amount) AS total_revenue, COUNT(ft.transaction_id) AS transaction_count "
                f"FROM {SCHEMA_NAME}.fact_transactions ft "
                f"JOIN {SCHEMA_NAME}.ml_customer_segments seg ON ft.customer_id = seg.customer_id "
                f"GROUP BY seg.behavioral_segment ORDER BY total_revenue DESC"
            )
        elif "segment" in q_lower and ("frequency" in q_lower or "transaction" in q_lower):
            sql = (
                f"SELECT seg.behavioral_segment, ROUND(AVG(dc.total_trans_ct_12m), 1) AS avg_txn_frequency, "
                f"ROUND(AVG(dc.total_trans_amt_12m), 2) AS avg_txn_amount "
                f"FROM {SCHEMA_NAME}.ml_customer_segments seg "
                f"JOIN {SCHEMA_NAME}.dim_customer dc ON seg.customer_id = dc.customer_id "
                f"GROUP BY seg.behavioral_segment ORDER BY avg_txn_frequency DESC"
            )
        else:
            sql = (
                f"SELECT SUM(amount) AS total_revenue, COUNT(transaction_id) AS total_transactions, "
                f"ROUND(AVG(amount), 2) AS avg_transaction_value "
                f"FROM {SCHEMA_NAME}.fact_transactions"
            )

    # Customer templates
    elif intent == "CUSTOMER_ANALYSIS":
        if "how many" in q_lower:
            sql = f"SELECT COUNT(*) AS total_customers, SUM(CASE WHEN customer_status = 'Active' THEN 1 ELSE 0 END) AS active_customers FROM {SCHEMA_NAME}.dim_customer"
        elif "high-value" in q_lower or "high value" in q_lower:
            sql = (
                f"SELECT dc.customer_id, dc.first_name || ' ' || dc.last_name AS customer_name, "
                f"dc.total_trans_amt_12m, cp.predicted_clv_12m, cp.clv_tier "
                f"FROM {SCHEMA_NAME}.dim_customer dc "
                f"JOIN {SCHEMA_NAME}.clv_predictions cp ON dc.customer_id = cp.customer_id "
                f"WHERE cp.clv_tier IN ('Platinum', 'Gold') "
                f"ORDER BY cp.predicted_clv_12m DESC LIMIT 20"
            )
        else:
            sql = (
                f"SELECT COUNT(*) AS total_customers, "
                f"SUM(CASE WHEN customer_status = 'Active' THEN 1 ELSE 0 END) AS active, "
                f"SUM(CASE WHEN customer_status = 'Churned' THEN 1 ELSE 0 END) AS churned, "
                f"ROUND(AVG(age), 1) AS avg_age, ROUND(AVG(customer_tenure_months), 1) AS avg_tenure "
                f"FROM {SCHEMA_NAME}.dim_customer"
            )

    # CLV templates
    elif intent == "CLV_ANALYSIS":
        if "top" in q_lower:
            sql = (
                f"SELECT dc.customer_id, dc.first_name || ' ' || dc.last_name AS customer_name, "
                f"cp.predicted_clv_12m, cp.clv_tier "
                f"FROM {SCHEMA_NAME}.clv_predictions cp "
                f"JOIN {SCHEMA_NAME}.dim_customer dc ON cp.customer_id = dc.customer_id "
                f"ORDER BY cp.predicted_clv_12m DESC LIMIT 10"
            )
        elif "segment" in q_lower:
            sql = (
                f"SELECT seg.behavioral_segment, ROUND(AVG(cp.predicted_clv_12m), 2) AS avg_clv, "
                f"COUNT(*) AS customer_count "
                f"FROM {SCHEMA_NAME}.clv_predictions cp "
                f"JOIN {SCHEMA_NAME}.ml_customer_segments seg ON cp.customer_id = seg.customer_id "
                f"GROUP BY seg.behavioral_segment ORDER BY avg_clv DESC"
            )
        elif "average" in q_lower or "avg" in q_lower:
            sql = f"SELECT ROUND(AVG(predicted_clv_12m), 2) AS avg_clv, clv_tier, COUNT(*) AS customers FROM {SCHEMA_NAME}.clv_predictions GROUP BY clv_tier ORDER BY avg_clv DESC"
        else:
            sql = (
                f"SELECT clv_tier, COUNT(*) AS customer_count, "
                f"ROUND(AVG(predicted_clv_12m), 2) AS avg_clv, "
                f"ROUND(SUM(predicted_clv_12m), 2) AS total_clv "
                f"FROM {SCHEMA_NAME}.clv_predictions GROUP BY clv_tier ORDER BY avg_clv DESC"
            )

    # Churn templates
    elif intent == "CHURN_ANALYSIS":
        if "percentage" in q_lower or "percent" in q_lower or "%" in q_lower:
            sql = (
                f"SELECT churn_risk_tier, COUNT(*) AS customer_count, "
                f"ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions GROUP BY churn_risk_tier ORDER BY percentage DESC"
            )
        elif "segment" in q_lower:
            sql = (
                f"SELECT seg.behavioral_segment, ROUND(AVG(mcp.churn_probability)::numeric, 4) AS avg_churn_prob, "
                f"SUM(CASE WHEN mcp.churn_risk_tier = 'High Risk' THEN 1 ELSE 0 END) AS high_risk_count "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions mcp "
                f"JOIN {SCHEMA_NAME}.ml_customer_segments seg ON mcp.customer_id = seg.customer_id "
                f"GROUP BY seg.behavioral_segment ORDER BY avg_churn_prob DESC"
            )
        elif "high risk" in q_lower:
            sql = (
                f"SELECT mcp.customer_id, dc.first_name || ' ' || dc.last_name AS customer_name, "
                f"ROUND(mcp.churn_probability::numeric, 4) AS churn_probability, mcp.churn_risk_tier, "
                f"mcp.top_risk_driver_1, mcp.top_risk_driver_2, mcp.top_risk_driver_3 "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions mcp "
                f"JOIN {SCHEMA_NAME}.dim_customer dc ON mcp.customer_id = dc.customer_id "
                f"WHERE mcp.churn_risk_tier = 'High Risk' "
                f"ORDER BY mcp.churn_probability DESC LIMIT 20"
            )
        else:
            sql = (
                f"SELECT churn_risk_tier, COUNT(*) AS customer_count, "
                f"ROUND(AVG(churn_probability)::numeric, 4) AS avg_churn_prob "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions GROUP BY churn_risk_tier ORDER BY avg_churn_prob DESC"
            )

    # Segment templates
    elif intent == "SEGMENT_ANALYSIS":
        if "premium" in q_lower and "how many" in q_lower:
            sql = (
                f"SELECT behavioral_segment, COUNT(*) AS customer_count "
                f"FROM {SCHEMA_NAME}.ml_customer_segments "
                f"WHERE behavioral_segment = 'Premium Customers' "
                f"GROUP BY behavioral_segment"
            )
        else:
            sql = (
                f"SELECT behavioral_segment, COUNT(*) AS customer_count, "
                f"ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS percentage "
                f"FROM {SCHEMA_NAME}.ml_customer_segments GROUP BY behavioral_segment ORDER BY customer_count DESC"
            )

    # Risk / SHAP templates
    elif intent == "RISK_ANALYSIS":
        # Check if asking about a specific customer
        customer_id_match = re.search(r'\b(\d{6,})\b', question)
        if customer_id_match:
            cust_id = customer_id_match.group(1)
            sql = (
                f"SELECT mcp.customer_id, dc.first_name || ' ' || dc.last_name AS customer_name, "
                f"ROUND(mcp.churn_probability::numeric, 4) AS churn_probability, mcp.churn_risk_tier, "
                f"mcp.top_risk_driver_1, mcp.top_risk_driver_2, mcp.top_risk_driver_3, "
                f"dc.months_inactive_12m, dc.total_trans_ct_12m, dc.credit_utilization_ratio, "
                f"dc.customer_tenure_months, dc.total_products_held "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions mcp "
                f"JOIN {SCHEMA_NAME}.dim_customer dc ON mcp.customer_id = dc.customer_id "
                f"WHERE mcp.customer_id = {cust_id}"
            )
        elif "common" in q_lower or "biggest" in q_lower or "most" in q_lower:
            sql = (
                f"SELECT top_risk_driver_1 AS risk_driver, COUNT(*) AS frequency "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions "
                f"WHERE churn_risk_tier = 'High Risk' "
                f"GROUP BY top_risk_driver_1 ORDER BY frequency DESC"
            )
        else:
            sql = (
                f"SELECT top_risk_driver_1 AS primary_driver, COUNT(*) AS customer_count "
                f"FROM {SCHEMA_NAME}.ml_churn_predictions "
                f"GROUP BY top_risk_driver_1 ORDER BY customer_count DESC"
            )

    # Recommendation templates
    elif intent == "RECOMMENDATION":
        sql = (
            f"SELECT seg.behavioral_segment, cp.clv_tier, mcp.churn_risk_tier, "
            f"COUNT(*) AS customer_count, ROUND(AVG(cp.predicted_clv_12m), 2) AS avg_clv, "
            f"ROUND(AVG(mcp.churn_probability)::numeric, 4) AS avg_churn_prob "
            f"FROM {SCHEMA_NAME}.ml_customer_segments seg "
            f"JOIN {SCHEMA_NAME}.clv_predictions cp ON seg.customer_id = cp.customer_id "
            f"JOIN {SCHEMA_NAME}.ml_churn_predictions mcp ON seg.customer_id = mcp.customer_id "
            f"GROUP BY seg.behavioral_segment, cp.clv_tier, mcp.churn_risk_tier "
            f"HAVING COUNT(*) > 5 "
            f"ORDER BY avg_churn_prob DESC, avg_clv DESC"
        )

    # Campaign Propensity templates
    elif intent == "CAMPAIGN_PROPENSITY":
        if "segment" in q_lower:
            sql = (
                f"SELECT seg.behavioral_segment, "
                f"ROUND(AVG(vt.propensity_score)::numeric, 4) AS avg_propensity, "
                f"COUNT(*) FILTER (WHERE vt.propensity_tier = 'High') AS high_propensity_count, "
                f"COUNT(*) AS total_customers "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"JOIN {SCHEMA_NAME}.ml_customer_segments seg ON vt.customer_id = seg.customer_id "
                f"GROUP BY seg.behavioral_segment ORDER BY avg_propensity DESC"
            )
        else:
            sql = (
                f"SELECT propensity_tier, priority_tier, COUNT(*) AS customer_count, "
                f"ROUND(AVG(propensity_score)::numeric, 4) AS avg_propensity, "
                f"ROUND(AVG(target_priority_score)::numeric, 4) AS avg_priority "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting "
                f"GROUP BY propensity_tier, priority_tier ORDER BY avg_priority DESC"
            )

    # Campaign Targeting templates
    elif intent == "CAMPAIGN_TARGETING":
        if "retention" in q_lower or ("high" in q_lower and ("clv" in q_lower or "propensity" in q_lower or "risk" in q_lower)):
            sql = (
                f"SELECT vt.customer_id, vt.customer_name, vt.behavioral_segment, vt.income_bracket, vt.card_category, "
                f"ROUND(vt.predicted_clv_12m::numeric, 2) AS clv, "
                f"ROUND(vt.churn_probability::numeric, 4) AS churn_prob, "
                f"ROUND(vt.propensity_score::numeric, 4) AS propensity, "
                f"ROUND(vt.target_priority_score::numeric, 4) AS target_priority, "
                f"vt.propensity_tier, vt.priority_tier "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"WHERE vt.priority_tier = 'High' AND vt.churn_probability >= 0.5 "
                f"ORDER BY vt.target_priority_score DESC LIMIT 25"
            )
        elif "cross-sell" in q_lower or "upgrade" in q_lower or "upsell" in q_lower:
            sql = (
                f"SELECT vt.customer_id, vt.customer_name, vt.behavioral_segment, vt.income_bracket, vt.card_category, "
                f"ROUND(vt.predicted_clv_12m::numeric, 2) AS clv, "
                f"ROUND(vt.propensity_score::numeric, 4) AS propensity, "
                f"ROUND(vt.target_priority_score::numeric, 4) AS target_priority, "
                f"vt.propensity_tier, vt.priority_tier "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"WHERE vt.propensity_tier = 'High' AND vt.churn_probability < 0.7 "
                f"ORDER BY vt.predicted_clv_12m DESC LIMIT 25"
            )
        else:
            sql = (
                f"SELECT priority_tier, COUNT(*) AS customer_count, "
                f"ROUND(AVG(propensity_score)::numeric, 4) AS avg_propensity, "
                f"ROUND(AVG(target_priority_score)::numeric, 4) AS avg_priority "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting "
                f"GROUP BY priority_tier ORDER BY avg_priority DESC"
            )

    # Experiment Analysis templates
    elif intent == "EXPERIMENT_ANALYSIS":
        sql = (
            f"SELECT experiment_id, campaign_id, campaign_name, objective, control_customers, treatment_customers, "
            f"control_responses, treatment_responses, "
            f"ROUND(control_conversion_rate::numeric, 4) AS control_conversion_rate, "
            f"ROUND(treatment_conversion_rate::numeric, 4) AS treatment_conversion_rate, "
            f"ROUND(absolute_lift::numeric, 4) AS absolute_lift, "
            f"ROUND(relative_lift::numeric, 4) AS relative_lift, "
            f"ROUND(z_statistic::numeric, 4) AS z_statistic, "
            f"ROUND(p_value::numeric, 6) AS p_value, "
            f"ROUND(confidence_interval_low::numeric, 4) AS confidence_interval_low, "
            f"ROUND(confidence_interval_high::numeric, 4) AS confidence_interval_high, "
            f"includes_synthetic_data "
            f"FROM {SCHEMA_NAME}.campaign_experiment_metrics "
            f"ORDER BY absolute_lift DESC"
        )

    # Campaign Performance templates
    elif intent == "CAMPAIGN_PERFORMANCE":
        sql = (
            f"SELECT dc.campaign_name, dc.objective, "
            f"COUNT(fcr.response_id) AS targeted, "
            f"SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) AS accepted, "
            f"ROUND(SUM(CASE WHEN fcr.was_accepted THEN 1 ELSE 0 END) * 100.0 / "
            f"NULLIF(COUNT(fcr.response_id), 0), 2) AS conversion_rate_pct, "
            f"ROUND(SUM(fcr.conversion_value), 0) AS total_revenue "
            f"FROM {SCHEMA_NAME}.fact_campaign_responses fcr "
            f"JOIN {SCHEMA_NAME}.dim_campaign dc ON fcr.campaign_id = dc.campaign_id "
            f"GROUP BY dc.campaign_id, dc.campaign_name, dc.objective "
            f"ORDER BY conversion_rate_pct DESC"
        )

    # Audience Recommendation templates
    elif intent == "AUDIENCE_RECOMMENDATION":
        if "retention" in q_lower:
            sql = (
                f"SELECT vt.behavioral_segment, vt.priority_tier, "
                f"COUNT(*) AS eligible_customers, "
                f"ROUND(AVG(vt.predicted_clv_12m)::numeric, 2) AS avg_clv, "
                f"ROUND(AVG(vt.churn_probability)::numeric, 4) AS avg_churn_prob, "
                f"ROUND(AVG(vt.propensity_score)::numeric, 4) AS avg_propensity "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"WHERE vt.priority_tier IN ('High', 'Medium') "
                f"AND vt.churn_probability > 0.5 "
                f"GROUP BY vt.behavioral_segment, vt.priority_tier "
                f"ORDER BY avg_churn_prob DESC, avg_clv DESC"
            )
        elif "upgrade" in q_lower or "cross-sell" in q_lower or "upsell" in q_lower:
            sql = (
                f"SELECT vt.behavioral_segment, vt.priority_tier, "
                f"COUNT(*) AS eligible_customers, "
                f"ROUND(AVG(vt.predicted_clv_12m)::numeric, 2) AS avg_clv, "
                f"ROUND(AVG(vt.propensity_score)::numeric, 4) AS avg_propensity "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"WHERE vt.propensity_tier = 'High' "
                f"AND vt.churn_probability < 0.3 "
                f"GROUP BY vt.behavioral_segment, vt.priority_tier "
                f"ORDER BY avg_clv DESC"
            )
        else:
            sql = (
                f"SELECT vt.behavioral_segment, vt.priority_tier, "
                f"COUNT(*) AS eligible_customers, "
                f"ROUND(AVG(vt.predicted_clv_12m)::numeric, 2) AS avg_clv, "
                f"ROUND(AVG(vt.churn_probability)::numeric, 4) AS avg_churn_prob, "
                f"ROUND(AVG(vt.propensity_score)::numeric, 4) AS avg_propensity "
                f"FROM {SCHEMA_NAME}.v_campaign_targeting vt "
                f"WHERE vt.priority_tier = 'High' "
                f"GROUP BY vt.behavioral_segment, vt.priority_tier "
                f"ORDER BY avg_propensity DESC"
            )

    if sql:
        return {"sql": sql, "explanation": "Generated from template pattern matching."}
    else:
        return {"sql": None, "explanation": "Could not generate SQL for this question. Please rephrase."}


def _template_generate_explanation(question: str, intent: str, data: list[dict]) -> dict:
    """Generate a basic explanation without LLM."""
    if not data:
        return {
            "summary": "No data found matching your query.",
            "insights": [],
            "recommendations": [],
        }

    # Build a basic summary from the first row
    first_row = data[0]
    row_count = len(data)

    summary_parts = []
    for key, value in first_row.items():
        if value is not None:
            summary_parts.append(f"{key.replace('_', ' ').title()}: {value}")

    summary = f"Query returned {row_count} result(s). " + "; ".join(summary_parts[:3]) + "."

    return {
        "summary": summary,
        "insights": [f"The query returned {row_count} row(s) of data."],
        "recommendations": [],
    }


# ============================================================
# RESPONSE PARSING HELPERS
# ============================================================

def _parse_sql_response(text: str) -> dict:
    """Parse LLM response to extract SQL and explanation."""
    # Try to extract SQL from code blocks
    sql_match = re.search(r"```(?:sql)?\s*\n?(.*?)\n?```", text, re.DOTALL | re.IGNORECASE)
    if sql_match:
        sql = sql_match.group(1).strip()
        # Get explanation (everything outside the code block)
        explanation = re.sub(r"```(?:sql)?\s*\n?.*?\n?```", "", text, flags=re.DOTALL).strip()
        return {"sql": sql, "explanation": explanation or "SQL generated successfully."}

    # Try JSON parsing
    try:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "sql": parsed.get("sql", "").strip(),
                "explanation": parsed.get("explanation", "SQL generated."),
            }
    except (json.JSONDecodeError, AttributeError):
        pass

    # Last resort: treat entire response as SQL if it looks like SQL
    cleaned = text.strip()
    if cleaned.upper().startswith(("SELECT", "WITH")):
        return {"sql": cleaned, "explanation": "SQL generated."}

    return {"sql": None, "explanation": text}


def _parse_explanation_response(text: str) -> dict:
    """Parse LLM explanation response (expected JSON)."""
    try:
        # Try to extract JSON from the response
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "summary": parsed.get("summary", text),
                "insights": parsed.get("insights", []),
                "recommendations": parsed.get("recommendations", []),
            }
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: use the raw text as summary
    return {
        "summary": text.strip(),
        "insights": [],
        "recommendations": [],
    }


def _build_sql_generation_prompt(schema_context: str, intent: str) -> str:
    """Build the system prompt for SQL generation."""
    return f"""You are a PostgreSQL SQL expert for a retail banking analytics platform.

Your task: Generate a single, correct PostgreSQL SELECT query to answer the user's question.

SCHEMA:
{schema_context}

RULES:
1. Use ONLY the tables and columns defined in the schema above.
2. Always prefix table names with 'customer360.' (e.g., customer360.dim_customer).
3. Generate ONLY SELECT or WITH...SELECT queries. No INSERT, UPDATE, DELETE, DROP, or ALTER.
4. Always include a LIMIT clause (default LIMIT 20 unless the user specifies a number).
5. Use appropriate JOINs based on the relationships defined above.
6. For monetary values, they are in INR (₹).
7. For churn analysis, use ml_churn_predictions table.
8. For CLV analysis, use clv_predictions table.
9. For segments, use ml_customer_segments table (behavioral_segment column).
10. For SHAP/risk analysis, use top_risk_driver_1/2/3 from ml_churn_predictions.
11. Round decimal values appropriately (2 places for currency, 4 for probabilities).
12. The detected intent is: {intent}

OUTPUT FORMAT:
Return ONLY the SQL query inside a ```sql code block. No explanation needed.

```sql
YOUR_QUERY_HERE
```
"""
