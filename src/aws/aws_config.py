"""
AWS / data-lake configuration for FinSight 360.

Single source of truth for bucket names, zone prefixes, S3 clients,
Spark sessions, and the Redshift connection — all LocalStack-aware so
the exact same code runs for free locally and unchanged on real AWS.

Design:
    - AWS_ENDPOINT_URL set   -> LocalStack (free local mode)
    - AWS_ENDPOINT_URL empty -> real AWS
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger("finsight.aws")

# ============================================================
# Mode + credentials
# ============================================================
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "").strip() or None
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
IS_LOCAL = AWS_ENDPOINT_URL is not None


def is_local() -> bool:
    """True when pointed at LocalStack (free local mode)."""
    return IS_LOCAL


# ============================================================
# Data lake layout
# ============================================================
LAKE_BUCKET = os.getenv("LAKE_BUCKET", "finsight-360-datalake")
BRONZE_PREFIX = os.getenv("BRONZE_PREFIX", "bronze")
SILVER_PREFIX = os.getenv("SILVER_PREFIX", "silver")
GOLD_PREFIX = os.getenv("GOLD_PREFIX", "gold")

# Logical datasets that flow through the lake. Order matters for
# referential-integrity aware loading (dimensions before facts).
DIMENSIONS = ["dim_date", "dim_customer", "dim_product", "dim_campaign"]
FACTS = ["fact_transactions", "fact_service_logs", "fact_campaign_responses"]
GOLD_TABLES = DIMENSIONS + FACTS


def s3_uri(zone: str, dataset: str | None = None) -> str:
    """Build an s3a:// URI for a lake zone (optionally a dataset)."""
    prefix = {
        "bronze": BRONZE_PREFIX,
        "silver": SILVER_PREFIX,
        "gold": GOLD_PREFIX,
    }[zone]
    base = f"s3a://{LAKE_BUCKET}/{prefix}"
    return f"{base}/{dataset}" if dataset else base


def s3_key(zone: str, dataset: str | None = None) -> str:
    """Build a plain S3 key prefix (for boto3, not Spark)."""
    prefix = {"bronze": BRONZE_PREFIX, "silver": SILVER_PREFIX, "gold": GOLD_PREFIX}[zone]
    return f"{prefix}/{dataset}" if dataset else prefix


# ============================================================
# boto3 client
# ============================================================
def get_s3_client():
    """Return a boto3 S3 client wired for LocalStack or real AWS."""
    import boto3

    kwargs = {"region_name": AWS_REGION}
    if AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = AWS_ENDPOINT_URL
        # Path-style addressing is required by LocalStack.
        from botocore.config import Config

        kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


def ensure_bucket(bucket: str = LAKE_BUCKET) -> None:
    """Create the lake bucket if it does not already exist (idempotent)."""
    s3 = get_s3_client()
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if bucket in existing:
        return
    if AWS_REGION == "us-east-1":
        s3.create_bucket(Bucket=bucket)
    else:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )
    logger.info("Created lake bucket s3://%s", bucket)


# ============================================================
# Spark session (LocalStack-aware S3A configuration)
# ============================================================
def get_spark(app_name: str = "finsight-transform"):
    """
    Build a SparkSession configured to read/write S3 (or LocalStack).

    Uses the s3a connector. On LocalStack we force path-style access
    and the local endpoint; on real AWS the defaults apply.
    """
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        # Deterministic output: stable shuffle partition count so
        # ordering-sensitive window features are reproducible.
        .config("spark.sql.shuffle.partitions", "8")
        .config(
            "spark.jars.packages",
            "org.apache.hadoop:hadoop-aws:3.3.4,"
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        )
    )

    spark = builder.getOrCreate()
    hadoop_conf = spark._jsc.hadoopConfiguration()
    hadoop_conf.set("fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID", "test"))
    hadoop_conf.set("fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY", "test"))
    hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    if AWS_ENDPOINT_URL:
        hadoop_conf.set("fs.s3a.endpoint", AWS_ENDPOINT_URL)
        hadoop_conf.set("fs.s3a.path.style.access", "true")
        hadoop_conf.set("fs.s3a.connection.ssl.enabled", "false")
        hadoop_conf.set(
            "fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
    return spark


# ============================================================
# Redshift / Postgres warehouse connection
# ============================================================
REDSHIFT = {
    "host": os.getenv("REDSHIFT_HOST", "localhost"),
    "port": os.getenv("REDSHIFT_PORT", "5439"),
    "db": os.getenv("REDSHIFT_DB", "customer360"),
    "user": os.getenv("REDSHIFT_USER", "admin"),
    "password": os.getenv("REDSHIFT_PASSWORD", "admin"),
    "schema": os.getenv("REDSHIFT_SCHEMA", "customer360"),
}
REDSHIFT_IAM_ROLE = os.getenv("REDSHIFT_IAM_ROLE", "")


def redshift_url() -> str:
    """SQLAlchemy URL for the warehouse (Redshift speaks the PG wire protocol)."""
    import urllib.parse

    pw = urllib.parse.quote_plus(REDSHIFT["password"])
    return (
        f"postgresql+psycopg2://{REDSHIFT['user']}:{pw}"
        f"@{REDSHIFT['host']}:{REDSHIFT['port']}/{REDSHIFT['db']}"
    )


def get_redshift_engine(echo: bool = False):
    """SQLAlchemy engine for the warehouse."""
    from sqlalchemy import create_engine

    return create_engine(redshift_url(), echo=echo)
