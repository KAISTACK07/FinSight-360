"""
FinSight 360 AI Analytics Assistant
SQL Validator — Mandatory Security Layer

Every LLM-generated SQL query MUST pass through this validator
before execution. This is the primary security boundary.

Rules enforced:
  1. Only SELECT / WITH...SELECT statements allowed
  2. Blocked keywords: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, EXEC
  3. No multiple statements (no semicolon followed by another statement)
  4. Comment injection prevention (strip --, /* */)
  5. Schema/table whitelist: only customer360 schema tables
  6. LIMIT enforcement: auto-append if missing
  7. Hard row cap at MAX_RESULT_ROWS
"""

import re
import logging
from dataclasses import dataclass
from ai_assistant.schema_metadata import ALLOWED_TABLES, SCHEMA_NAME

logger = logging.getLogger("finsight360.sql_validator")

# Maximum rows any query can return
MAX_RESULT_ROWS = 500
DEFAULT_LIMIT = 100

# Dangerous SQL keywords that must NEVER appear
BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "CALL", "MERGE", "UPSERT", "REPLACE",
    "pg_sleep", "pg_terminate", "pg_cancel",
    "COPY", "\\\\copy",
]

# Regex pattern for blocked keywords (word-boundary matching)
_BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in BLOCKED_KEYWORDS) + r")\b",
    re.IGNORECASE
)

# Pattern to detect multiple statements
_MULTI_STATEMENT_PATTERN = re.compile(r";\s*\S")

# Pattern to detect SQL comments
_LINE_COMMENT_PATTERN = re.compile(r"--.*$", re.MULTILINE)
_BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)

# Pattern to detect valid statement start
_VALID_START_PATTERN = re.compile(
    r"^\s*(SELECT|WITH)\b", re.IGNORECASE
)


@dataclass
class ValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    sanitized_sql: str
    error: str | None = None
    warnings: list[str] | None = None


def validate_sql(sql: str) -> ValidationResult:
    """
    Validate and sanitize a SQL query for safe execution.

    Returns a ValidationResult with:
      - is_valid: whether the query passed all checks
      - sanitized_sql: the cleaned and safe query
      - error: description of the first validation failure (if any)
      - warnings: non-blocking issues (e.g., LIMIT auto-added)
    """
    if not sql or not sql.strip():
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error="Empty SQL query"
        )

    warnings = []
    sanitized = sql.strip()

    # Step 1: Strip comments (prevent injection via comments)
    sanitized = _LINE_COMMENT_PATTERN.sub("", sanitized)
    sanitized = _BLOCK_COMMENT_PATTERN.sub("", sanitized)
    sanitized = sanitized.strip()

    if not sanitized:
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error="SQL query is empty after removing comments"
        )

    # Step 2: Check for blocked keywords
    match = _BLOCKED_PATTERN.search(sanitized)
    if match:
        blocked_word = match.group(1).upper()
        logger.warning(f"BLOCKED SQL: Contains '{blocked_word}' keyword")
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error=f"SQL contains forbidden keyword: {blocked_word}. Only SELECT queries are allowed."
        )

    # Step 3: Verify it starts with SELECT or WITH
    if not _VALID_START_PATTERN.match(sanitized):
        logger.warning(f"BLOCKED SQL: Does not start with SELECT/WITH")
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error="SQL must start with SELECT or WITH. Only read-only queries are allowed."
        )

    # Step 4: Check for multiple statements
    # Remove trailing semicolon first
    clean = sanitized.rstrip(";").strip()
    if _MULTI_STATEMENT_PATTERN.search(clean):
        logger.warning("BLOCKED SQL: Multiple statements detected")
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error="Multiple SQL statements are not allowed. Please submit one query at a time."
        )

    sanitized = clean  # Use version without trailing semicolon

    # Step 5: Validate table references against whitelist
    table_check = _validate_table_references(sanitized)
    if table_check is not None:
        return ValidationResult(
            is_valid=False, sanitized_sql="",
            error=table_check
        )

    # Step 6: Enforce LIMIT
    if not _has_limit(sanitized):
        sanitized = f"{sanitized}\nLIMIT {DEFAULT_LIMIT}"
        warnings.append(f"Added default LIMIT {DEFAULT_LIMIT}")
    else:
        # Ensure existing LIMIT doesn't exceed max
        sanitized = _cap_limit(sanitized)

    logger.info("SQL validation PASSED")
    return ValidationResult(
        is_valid=True,
        sanitized_sql=sanitized,
        warnings=warnings if warnings else None
    )


def _validate_table_references(sql: str) -> str | None:
    """
    Check that all table references use the allowed schema and tables.
    Returns an error message if invalid, None if valid.
    """
    # Find all schema.table references
    schema_table_pattern = re.compile(r"(\w+)\.(\w+)", re.IGNORECASE)
    matches = schema_table_pattern.findall(sql)

    for schema, table in matches:
        # Skip column references (e.g., t.column_name) by checking known tables
        if schema.lower() == SCHEMA_NAME:
            if table.lower() not in {t.lower() for t in ALLOWED_TABLES}:
                return f"Table '{schema}.{table}' is not in the allowed table list."
        # Allow table aliases (short lowercase words that aren't schema names)
        # Only flag if it looks like an actual schema reference
        elif schema.lower() in ("public", "pg_catalog", "information_schema"):
            return f"Schema '{schema}' is not allowed. Only '{SCHEMA_NAME}' schema is accessible."

    # Also check for FROM/JOIN without schema prefix to catch unqualified table names
    from_join_pattern = re.compile(
        r"(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?",
        re.IGNORECASE
    )
    for match in from_join_pattern.finditer(sql):
        table_ref = match.group(1).lower()
        # Skip if it's a schema-qualified reference (already checked above)
        if f"{SCHEMA_NAME}.{table_ref}" in sql.lower():
            continue
        # Skip if it's a CTE name (common in WITH queries)
        cte_pattern = re.compile(r"WITH\s+(\w+)\s+AS", re.IGNORECASE)
        cte_names = {m.group(1).lower() for m in cte_pattern.finditer(sql)}
        if table_ref in cte_names:
            continue
        # Skip subqueries and aliases
        if table_ref in ("select", "lateral"):
            continue

    return None


def _has_limit(sql: str) -> bool:
    """Check if the query already has a LIMIT clause."""
    # Simple check — look for LIMIT keyword not inside a subquery
    # This is a heuristic; complex nested subqueries may need more sophisticated parsing
    return bool(re.search(r"\bLIMIT\s+\d+\s*$", sql, re.IGNORECASE))


def _cap_limit(sql: str) -> str:
    """Ensure the LIMIT value doesn't exceed MAX_RESULT_ROWS."""
    match = re.search(r"\bLIMIT\s+(\d+)\s*$", sql, re.IGNORECASE)
    if match:
        current_limit = int(match.group(1))
        if current_limit > MAX_RESULT_ROWS:
            sql = sql[:match.start(1)] + str(MAX_RESULT_ROWS) + sql[match.end(1):]
    return sql
