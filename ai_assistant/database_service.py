"""
FinSight 360 AI Analytics Assistant
Database Service — Secure Read-Only Query Execution

Executes validated SQL queries against the PostgreSQL analytical warehouse.
Enforces:
  - Read-only transactions (SET TRANSACTION READ ONLY)
  - Statement timeout (configurable, default 30s)
  - Row limit enforcement
  - Connection pooling via SQLAlchemy
"""

import os
import logging
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

logger = logging.getLogger("finsight360.database")

# Lazy-init engine
_engine = None


def _get_engine():
    """Create or return the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        # Import from existing project config
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.etl.config import get_connection_url

        connection_url = get_connection_url()
        timeout_ms = int(os.getenv("AI_DB_STATEMENT_TIMEOUT", "30000"))

        _engine = create_engine(
            connection_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={
                "options": f"-c statement_timeout={timeout_ms}"
            },
        )
        logger.info(f"Database engine created (timeout={timeout_ms}ms)")
    return _engine


def execute_query(sql: str, max_rows: int = 500) -> dict[str, Any]:
    """
    Execute a validated, read-only SQL query and return results.

    Args:
        sql: The validated SQL query string (must have passed sql_validator).
        max_rows: Maximum number of rows to return.

    Returns:
        dict with:
          - columns: list of column names
          - rows: list of row dicts
          - row_count: number of rows returned
          - truncated: whether results were truncated

    Raises:
        DatabaseError: If the query fails to execute.
    """
    engine = _get_engine()

    try:
        with engine.connect() as conn:
            # Force read-only mode — belt-and-suspenders with SQL validator
            conn.execute(text("SET TRANSACTION READ ONLY"))

            result = conn.execute(text(sql))
            columns = list(result.keys())

            rows = []
            truncated = False
            for i, row in enumerate(result):
                if i >= max_rows:
                    truncated = True
                    break
                # Convert Row to dict, handling special types
                row_dict = {}
                for col, val in zip(columns, row):
                    if val is None:
                        row_dict[col] = None
                    elif isinstance(val, (int, float, bool, str)):
                        row_dict[col] = val
                    else:
                        row_dict[col] = str(val)
                rows.append(row_dict)

            logger.info(f"Query returned {len(rows)} rows (truncated={truncated})")

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
            }

    except Exception as e:
        error_msg = str(e)
        # Sanitize error message — don't expose internal details
        if "statement_timeout" in error_msg.lower():
            raise DatabaseError("Query timed out. Please try a simpler query.")
        elif "permission denied" in error_msg.lower():
            raise DatabaseError("Permission denied. The AI assistant has read-only access.")
        elif "does not exist" in error_msg.lower():
            raise DatabaseError("Query references a table or column that does not exist.")
        else:
            logger.error(f"Database query failed: {error_msg}")
            raise DatabaseError("An error occurred while executing the query. Please try again.")


def test_connection() -> bool:
    """Test database connectivity."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


class DatabaseError(Exception):
    """Custom exception for database execution errors."""
    pass
