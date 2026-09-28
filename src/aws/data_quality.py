"""
Data-quality gates for the warehouse.

Runs as the final pipeline stage (and in CI on sample data). A failing
check raises `DataQualityError`, which fails the Airflow task so bad data
never reaches downstream analytics. Checks are intentionally simple and
explainable — the kind a reviewer can read and trust:

    * row-count      : table is non-empty (and meets an optional minimum)
    * not-null       : key columns contain no NULLs
    * uniqueness     : primary key has no duplicates
    * value-range    : numeric columns fall inside sane bounds
    * referential    : fact FKs resolve to dimension keys

Usage:
    python -m src.aws.data_quality
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.aws.aws_config import REDSHIFT, get_redshift_engine

logger = logging.getLogger("finsight.dq")


class DataQualityError(AssertionError):
    """Raised when a data-quality gate fails."""


# ------------------------------------------------------------
# Declarative expectations per table.
# ------------------------------------------------------------
NOT_NULL = {
    "dim_customer": ["customer_id", "customer_status", "credit_limit"],
    "dim_product": ["product_id", "product_name"],
    "dim_campaign": ["campaign_id", "campaign_name"],
    "dim_date": ["date_key", "full_date"],
    "fact_transactions": ["customer_id", "amount"],
    "fact_campaign_responses": ["campaign_id", "customer_id"],
    "customer_features": ["customer_id", "rfm_score"],
}
PRIMARY_KEY = {
    "dim_customer": "customer_id",
    "dim_product": "product_id",
    "dim_campaign": "campaign_id",
    "dim_date": "date_key",
    "customer_features": "customer_id",
}
# column -> (min, max) inclusive bounds
VALUE_RANGE = {
    "dim_customer": {"credit_utilization_ratio": (0, 1), "age": (18, 100)},
    "fact_transactions": {"amount": (0, 1e9)},
    "customer_features": {"r_score": (1, 5), "f_score": (1, 5), "m_score": (1, 5)},
}
# fact table -> (fk_column, dimension, dim_key)
REFERENTIAL = [
    ("fact_transactions", "customer_id", "dim_customer", "customer_id"),
    ("fact_campaign_responses", "campaign_id", "dim_campaign", "campaign_id"),
    ("customer_features", "customer_id", "dim_customer", "customer_id"),
]


def _scalar(conn, sql: str) -> int:
    return conn.execute(text(sql)).scalar() or 0


def _table_exists(conn, table: str) -> bool:
    return bool(
        _scalar(
            conn,
            f"""SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema='{REDSHIFT['schema']}' AND table_name='{table}'""",
        )
    )


def run_checks(min_rows: dict[str, int] | None = None) -> list[str]:
    """Run every gate. Returns the list of passed checks; raises on failure."""
    schema = REDSHIFT["schema"]
    min_rows = min_rows or {}
    passed: list[str] = []
    failures: list[str] = []

    engine = get_redshift_engine()
    with engine.connect() as conn:
        tables = sorted(set(NOT_NULL) | set(PRIMARY_KEY))

        for table in tables:
            if not _table_exists(conn, table):
                continue
            fq = f"{schema}.{table}"

            # row-count
            n = _scalar(conn, f"SELECT COUNT(*) FROM {fq}")
            floor = min_rows.get(table, 1)
            (passed if n >= floor else failures).append(
                f"row_count[{table}]={n} (min {floor})"
            )

            # not-null
            for col in NOT_NULL.get(table, []):
                nulls = _scalar(conn, f"SELECT COUNT(*) FROM {fq} WHERE {col} IS NULL")
                (passed if nulls == 0 else failures).append(
                    f"not_null[{table}.{col}] nulls={nulls}"
                )

            # uniqueness
            pk = PRIMARY_KEY.get(table)
            if pk:
                dupes = _scalar(
                    conn,
                    f"SELECT COUNT(*) FROM (SELECT {pk} FROM {fq} "
                    f"GROUP BY {pk} HAVING COUNT(*) > 1) d",
                )
                (passed if dupes == 0 else failures).append(
                    f"unique[{table}.{pk}] dupes={dupes}"
                )

            # value-range
            for col, (lo, hi) in VALUE_RANGE.get(table, {}).items():
                bad = _scalar(
                    conn,
                    f"SELECT COUNT(*) FROM {fq} "
                    f"WHERE {col} IS NOT NULL AND ({col} < {lo} OR {col} > {hi})",
                )
                (passed if bad == 0 else failures).append(
                    f"range[{table}.{col} in {lo}..{hi}] violations={bad}"
                )

        # referential integrity
        for fact, fk, dim, dim_key in REFERENTIAL:
            if not (_table_exists(conn, fact) and _table_exists(conn, dim)):
                continue
            orphans = _scalar(
                conn,
                f"""SELECT COUNT(*) FROM {schema}.{fact} f
                    LEFT JOIN {schema}.{dim} d ON f.{fk} = d.{dim_key}
                    WHERE f.{fk} IS NOT NULL AND d.{dim_key} IS NULL""",
            )
            (passed if orphans == 0 else failures).append(
                f"fk[{fact}.{fk}→{dim}.{dim_key}] orphans={orphans}"
            )

    for check in passed:
        logger.info("PASS  %s", check)
    for check in failures:
        logger.error("FAIL  %s", check)

    if failures:
        raise DataQualityError(f"{len(failures)} data-quality gate(s) failed: {failures}")

    logger.info("All %d data-quality gates passed.", len(passed))
    return passed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
    run_checks()
