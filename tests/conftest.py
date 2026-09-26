"""
Shared pytest fixtures for the AWS data-engineering layer.

The Spark fixture is a plain local session (no S3 packages), so tests
run offline with just `pyspark` installed — no LocalStack, no JAR
downloads, no network. Skips cleanly if pyspark is unavailable.
"""

from __future__ import annotations

import pytest

pyspark = pytest.importorskip("pyspark")


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.appName("finsight-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def sample_transactions(spark):
    """Two customers, several months of transactions each."""
    rows = [
        # customer_id, transaction_date, amount
        (1, "2024-01-10 10:00:00", 1000.0),
        (1, "2024-01-20 10:00:00", 500.0),
        (1, "2024-02-15 10:00:00", 2000.0),
        (1, "2024-03-05 10:00:00", 1500.0),
        (2, "2024-01-05 10:00:00", 300.0),
        (2, "2024-03-25 10:00:00", 700.0),
    ]
    return spark.createDataFrame(rows, ["customer_id", "transaction_date", "amount"])


@pytest.fixture
def sample_customers(spark):
    rows = [(1, 40), (2, 12)]  # customer_id, tenure months
    return spark.createDataFrame(rows, ["customer_id", "customer_tenure_months"])
