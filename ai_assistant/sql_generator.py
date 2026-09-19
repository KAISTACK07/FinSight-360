"""
FinSight 360 AI Analytics Assistant
SQL Generator — Orchestrates SQL generation pipeline

Coordinates:
  1. Schema context injection
  2. LLM-based SQL generation
  3. SQL validation
  4. Customer ID extraction for single-customer queries
"""

import re
import logging
from typing import Optional

from ai_assistant.schema_metadata import get_schema_context_for_llm
from ai_assistant.llm_service import generate_sql as llm_generate_sql
from ai_assistant.sql_validator import validate_sql, ValidationResult

logger = logging.getLogger("finsight360.sql_generator")


def generate_and_validate_sql(question: str, intent: str) -> dict:
    """
    Generate SQL from a question and validate it.

    Args:
        question: User's natural-language question.
        intent: Detected intent category.

    Returns:
        dict with:
          - sql: validated SQL string (or None if failed)
          - validation: ValidationResult
          - generation_explanation: LLM's explanation of what the SQL does
          - error: error message if generation/validation failed
    """
    # Step 1: Get schema context
    schema_context = get_schema_context_for_llm()

    # Step 2: Generate SQL via LLM
    logger.info(f"Generating SQL for intent={intent}: {question[:80]}...")
    generation_result = llm_generate_sql(question, schema_context, intent)

    sql = generation_result.get("sql")
    explanation = generation_result.get("explanation", "")

    if not sql:
        return {
            "sql": None,
            "validation": None,
            "generation_explanation": explanation,
            "error": "Failed to generate SQL query. Please rephrase your question.",
        }

    # Step 3: Validate the generated SQL
    logger.info(f"Validating generated SQL...")
    validation = validate_sql(sql)

    if not validation.is_valid:
        logger.warning(f"SQL validation FAILED: {validation.error}")

        # Retry once with a simplified approach
        retry_result = _retry_with_simpler_query(question, intent, schema_context)
        if retry_result:
            return retry_result

        return {
            "sql": None,
            "validation": validation,
            "generation_explanation": explanation,
            "error": f"Generated SQL failed validation: {validation.error}",
        }

    logger.info("SQL generation and validation successful")
    return {
        "sql": validation.sanitized_sql,
        "validation": validation,
        "generation_explanation": explanation,
        "error": None,
    }


def _retry_with_simpler_query(question: str, intent: str, schema_context: str) -> Optional[dict]:
    """
    Retry SQL generation with a simplified prompt.
    Returns None if retry also fails.
    """
    logger.info("Retrying SQL generation with simplified approach...")

    # Use template-based generation as fallback
    from ai_assistant.llm_service import _template_generate_sql
    result = _template_generate_sql(question, intent)

    if result.get("sql"):
        validation = validate_sql(result["sql"])
        if validation.is_valid:
            logger.info("Retry with template succeeded")
            return {
                "sql": validation.sanitized_sql,
                "validation": validation,
                "generation_explanation": result.get("explanation", ""),
                "error": None,
            }

    return None


def extract_customer_id(question: str) -> Optional[int]:
    """
    Extract a customer ID from the question if present.
    Customer IDs in this dataset are 9-digit integers (e.g., 818770008).
    """
    match = re.search(r"\b(\d{6,10})\b", question)
    if match:
        return int(match.group(1))
    return None
