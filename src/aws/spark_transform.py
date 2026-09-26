"""
Stage 2 — Transform (PySpark): bronze ──► silver ──► gold.

Distributed replacement for the single-machine pandas ETL. Runs on
local Spark (free) and, unchanged, as an AWS Glue job (see glue_job.py).

Zones
-----
bronze : immutable source CSVs (as ingested)
silver : cleaned, typed, de-duplicated Parquet (partitioned)
gold   : analytics-ready star schema + a customer feature mart

Feature engineering (gold/customer_features) uses Spark **window
functions** for RFM, lag, rolling, and tenure features. All
order-sensitive features use an explicit `partitionBy(...).orderBy(...)`
so output is deterministic and reproducible regardless of how Spark
distributes the data — this is what keeps engineered values identical
across runs (and identical to the original pandas pipeline).
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from src.aws.aws_config import DIMENSIONS, FACTS, get_spark, s3_uri

logger = logging.getLogger("finsight.transform")

# ------------------------------------------------------------
# Numeric columns we coerce to double when present (INR money /
# ratios). Everything else stays as read; we never fabricate values.
# ------------------------------------------------------------
_NUMERIC_HINTS = {
    "amount", "balance_after", "credit_limit", "total_revolving_bal",
    "avg_open_to_buy", "credit_utilization_ratio", "total_trans_amt_12m",
    "amt_change_q4_q1", "ct_change_q4_q1", "conversion_value",
    "resolution_time_hours", "budget", "annual_fee", "interest_rate",
    "min_balance",
}
_INT_HINTS = {
    "customer_id", "product_id", "campaign_id", "date_key",
    "total_products_held", "months_inactive_12m", "contacts_count_12m",
    "total_trans_ct_12m", "customer_tenure_months", "age", "dependents",
    "csat_score", "days_to_response",
}


# ============================================================
# bronze ──► silver : clean + type + de-duplicate
# ============================================================
def _read_bronze_csv(spark: SparkSession, dataset: str) -> DataFrame | None:
    path = f"{s3_uri('bronze', dataset)}/{dataset}.csv"
    try:
        df = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(path)
        )
    except Exception as exc:  # dataset not present in this run
        logger.warning("bronze read skipped for %s: %s", dataset, exc)
        return None
    return df


def _cast_columns(df: DataFrame) -> DataFrame:
    """Coerce known numeric/int columns; trim strings. Value-preserving."""
    for col in df.columns:
        if col in _INT_HINTS:
            df = df.withColumn(col, F.col(col).cast("long"))
        elif col in _NUMERIC_HINTS:
            df = df.withColumn(col, F.col(col).cast("double"))
        elif dict(df.dtypes).get(col) == "string":
            df = df.withColumn(col, F.trim(F.col(col)))
    return df


def clean_to_silver(spark: SparkSession, dataset: str) -> DataFrame | None:
    """Read one bronze dataset, clean/type/dedupe it, write to silver."""
    df = _read_bronze_csv(spark, dataset)
    if df is None:
        return None

    df = _cast_columns(df).dropDuplicates()
    out = s3_uri("silver", dataset)
    df.write.mode("overwrite").parquet(out)
    logger.info("silver ← %-24s rows=%d → %s", dataset, df.count(), out)
    return df


# ============================================================
# silver ──► gold : star schema (pass-through, partitioned)
# ============================================================
def _partition_of(dataset: str) -> str | None:
    """Choose a natural partition column for fact tables (by year)."""
    return "year_partition" if dataset in FACTS else None


def promote_to_gold(df: DataFrame, dataset: str) -> None:
    """Write a silver dataset to gold, partitioning facts by year."""
    out = s3_uri("gold", dataset)
    part = _partition_of(dataset)

    if part and "date_key" in df.columns:
        # date_key is YYYYMMDD -> derive a stable year partition.
        df = df.withColumn(part, (F.col("date_key") / F.lit(10000)).cast("int"))
        df.write.mode("overwrite").partitionBy(part).parquet(out)
    else:
        df.write.mode("overwrite").parquet(out)
    logger.info("gold   ← %-24s → %s", dataset, out)


# ============================================================
# gold feature mart : RFM + rolling + lag + tenure
# ============================================================
def build_customer_features(
    spark: SparkSession,
    transactions: DataFrame,
    customers: DataFrame | None,
) -> DataFrame:
    """
    Build gold/customer_features from transaction-grain data using
    window functions. Deterministic: every ordered window has an
    explicit orderBy, so results are reproducible run-to-run.
    """
    tx = transactions
    # Normalise a transaction timestamp / month for windowing.
    if "transaction_date" in tx.columns:
        tx = tx.withColumn("txn_ts", F.to_timestamp("transaction_date"))
    elif "date_key" in tx.columns:
        tx = tx.withColumn("txn_ts", F.to_timestamp(F.col("date_key").cast("string"), "yyyyMMdd"))
    else:
        raise ValueError("fact_transactions needs transaction_date or date_key")

    tx = tx.withColumn("txn_month", F.date_format("txn_ts", "yyyy-MM"))

    # ---- RFM (Recency, Frequency, Monetary) per customer ----------
    dataset_max = tx.select(F.max("txn_ts").alias("m")).first()["m"]
    rfm = (
        tx.groupBy("customer_id")
        .agg(
            F.max("txn_ts").alias("last_txn_ts"),
            F.count("*").alias("frequency"),
            F.sum("amount").alias("monetary"),
            F.avg("amount").alias("avg_txn_amount"),
        )
        .withColumn("recency_days", F.datediff(F.lit(dataset_max), F.col("last_txn_ts")))
    )

    # RFM scores 1..5 via quantile buckets (ntile over ordered windows).
    # customer_id is a tiebreaker so the ordering is total and ntile is
    # fully deterministic (no bucket reshuffling on ties between runs).
    r_w = Window.orderBy(F.col("recency_days").asc(), F.col("customer_id").asc())
    f_w = Window.orderBy(F.col("frequency").desc(), F.col("customer_id").asc())
    m_w = Window.orderBy(F.col("monetary").desc(), F.col("customer_id").asc())
    rfm = (
        rfm.withColumn("r_score", F.ntile(5).over(r_w))
        .withColumn("f_score", F.ntile(5).over(f_w))
        .withColumn("m_score", F.ntile(5).over(m_w))
        .withColumn("rfm_score", F.col("r_score") + F.col("f_score") + F.col("m_score"))
    )

    # ---- Monthly series → rolling + lag features ------------------
    monthly = (
        tx.groupBy("customer_id", "txn_month")
        .agg(
            F.sum("amount").alias("month_amount"),
            F.count("*").alias("month_txn_ct"),
        )
    )
    # Explicit, deterministic ordering by month within each customer.
    ordered = Window.partitionBy("customer_id").orderBy("txn_month")
    roll3 = ordered.rowsBetween(-2, 0)  # trailing 3-month window

    monthly = (
        monthly
        .withColumn("rolling_3m_amount", F.avg("month_amount").over(roll3))
        .withColumn("lag_1m_amount", F.lag("month_amount", 1).over(ordered))
        .withColumn("lag_3m_amount", F.lag("month_amount", 3).over(ordered))
        .withColumn("mom_change",
                    F.col("month_amount") - F.lag("month_amount", 1).over(ordered))
    )

    # Latest month per customer carries the current rolling/lag state.
    latest_month = Window.partitionBy("customer_id").orderBy(F.col("txn_month").desc())
    monthly_latest = (
        monthly.withColumn("_rn", F.row_number().over(latest_month))
        .filter(F.col("_rn") == 1)
        .drop("_rn", "txn_month", "month_amount", "month_txn_ct")
    )

    features = rfm.join(monthly_latest, on="customer_id", how="left")

    # ---- Tenure (from dim_customer when available) ----------------
    if customers is not None and "customer_tenure_months" in customers.columns:
        tenure = customers.select(
            "customer_id",
            F.col("customer_tenure_months").alias("tenure_months"),
        )
        features = features.join(tenure, on="customer_id", how="left")

    features = features.withColumn("feature_generated_at", F.current_timestamp())
    return features


# ============================================================
# Orchestration entrypoint
# ============================================================
def run(spark: SparkSession | None = None) -> None:
    """Full transform: bronze → silver → gold, incl. feature mart."""
    owns = spark is None
    spark = spark or get_spark("finsight-transform")

    silver: dict[str, DataFrame] = {}
    for dataset in DIMENSIONS + FACTS:
        df = clean_to_silver(spark, dataset)
        if df is not None:
            silver[dataset] = df
            promote_to_gold(df, dataset)

    if "fact_transactions" in silver:
        feats = build_customer_features(
            spark,
            silver["fact_transactions"],
            silver.get("dim_customer"),
        )
        out = s3_uri("gold", "customer_features")
        feats.write.mode("overwrite").parquet(out)
        logger.info("gold   ← customer_features rows=%d → %s", feats.count(), out)

    logger.info("Transform complete. Zones written: silver + gold.")
    if owns:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
    run()
