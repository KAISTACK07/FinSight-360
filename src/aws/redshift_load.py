"""
Stage 3 — Load: gold (S3 Parquet) ──► Redshift star schema.

Applies the Redshift DDL, then bulk-loads each gold table with
`COPY ... FROM 's3://.../gold/<table>' FORMAT AS PARQUET`, which is the
massively-parallel Redshift load path (every slice pulls Parquet files
straight from S3).

Two execution modes, chosen automatically from aws_config.is_local():

  * REAL AWS  -> real Redshift `COPY ... IAM_ROLE ...` from S3.
  * LOCAL     -> the docker-compose Postgres stand-in has no COPY-from-S3,
                 so we stream the same gold Parquet down from LocalStack
                 with pandas and load via SQLAlchemy. The DDL, table
                 shapes, load order and quality gates are identical — only
                 the physical COPY verb differs.

Dimensions are loaded before facts to respect referential order.

Usage:
    python -m src.aws.redshift_load
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from sqlalchemy import text

from src.aws.aws_config import (
    DIMENSIONS,
    FACTS,
    GOLD_PREFIX,
    LAKE_BUCKET,
    REDSHIFT,
    REDSHIFT_IAM_ROLE,
    get_redshift_engine,
    get_s3_client,
    is_local,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
logger = logging.getLogger("finsight.load")

DDL_PATH = Path(__file__).resolve().parent / "redshift_ddl.sql"
LOAD_ORDER = DIMENSIONS + FACTS + ["customer_features"]

# Redshift-only clauses to strip when running against local Postgres.
_REDSHIFT_ONLY = re.compile(
    r"\b(DISTSTYLE\s+\w+|DISTKEY\s*\([^)]*\)|SORTKEY\s*\([^)]*\))",
    flags=re.IGNORECASE,
)


def apply_ddl() -> None:
    """Create schema + tables. Strips MPP keywords for local Postgres."""
    ddl = DDL_PATH.read_text()
    if is_local():
        ddl = _REDSHIFT_ONLY.sub("", ddl)
    engine = get_redshift_engine()
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {REDSHIFT['schema']}"))
        # psycopg2 executes one statement at a time; split on ';'.
        for stmt in filter(str.strip, ddl.split(";")):
            conn.execute(text(stmt))
    logger.info("Applied Redshift DDL (%s mode)", "local" if is_local() else "aws")


def _copy_real_redshift(conn, table: str) -> None:
    """Native Redshift MPP COPY from S3 Parquet."""
    s3_path = f"s3://{LAKE_BUCKET}/{GOLD_PREFIX}/{table}"
    conn.execute(text(f"TRUNCATE {REDSHIFT['schema']}.{table}"))
    conn.execute(
        text(
            f"""
            COPY {REDSHIFT['schema']}.{table}
            FROM '{s3_path}'
            IAM_ROLE '{REDSHIFT_IAM_ROLE}'
            FORMAT AS PARQUET
            """
        )
    )
    logger.info("COPY  ← %-24s from %s", table, s3_path)


def _load_local(engine, table: str) -> None:
    """
    Local path: read gold Parquet from LocalStack S3 and load with pandas.
    Exercises the identical DDL, ordering and gates as the real COPY.
    """
    import pandas as pd

    s3 = get_s3_client()
    prefix = f"{GOLD_PREFIX}/{table}/"
    objs = s3.list_objects_v2(Bucket=LAKE_BUCKET, Prefix=prefix).get("Contents", [])
    parquet_keys = [o["Key"] for o in objs if o["Key"].endswith(".parquet")]
    if not parquet_keys:
        logger.warning("no gold Parquet for %s (skipping)", table)
        return

    frames = []
    for key in parquet_keys:
        body = s3.get_object(Bucket=LAKE_BUCKET, Key=key)["Body"].read()
        frames.append(pd.read_parquet(io.BytesIO(body)))
    df = pd.concat(frames, ignore_index=True)
    # Drop the Spark year_partition helper column if present.
    df = df.drop(columns=[c for c in ("year_partition",) if c in df.columns])

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {REDSHIFT['schema']}.{table}"))
    df.to_sql(
        table,
        engine,
        schema=REDSHIFT["schema"],
        if_exists="append",
        index=False,
        chunksize=10_000,
        method="multi",
    )
    logger.info("load  ← %-24s rows=%d (local)", table, len(df))


def load_all() -> None:
    """Apply DDL and load every gold table in dimension→fact order."""
    apply_ddl()
    engine = get_redshift_engine()

    if is_local():
        for table in LOAD_ORDER:
            _load_local(engine, table)
    else:
        with engine.begin() as conn:
            for table in LOAD_ORDER:
                _copy_real_redshift(conn, table)

    logger.info("Warehouse load complete (%d tables).", len(LOAD_ORDER))


if __name__ == "__main__":
    load_all()
