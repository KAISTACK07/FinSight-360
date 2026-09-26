"""
Tests for the data-quality gate definitions and their enforcement.

The gate *rules* are validated for internal consistency, and the gate
*semantics* are exercised against the real Spark feature output converted
to pandas — proving the gold data actually satisfies the warehouse
expectations (PK uniqueness, RFM ranges, non-null keys) before load.
"""

from __future__ import annotations

from src.aws import data_quality as dq
from src.aws.spark_transform import build_customer_features


# --- rule-definition consistency -------------------------------------
def test_primary_keys_are_declared_not_null():
    """Every PK column must also be a NOT-NULL expectation."""
    for table, pk in dq.PRIMARY_KEY.items():
        assert pk in dq.NOT_NULL.get(table, []), f"{table}.{pk} missing from NOT_NULL"


def test_referential_targets_have_primary_keys():
    for _fact, _fk, dim, dim_key in dq.REFERENTIAL:
        assert dq.PRIMARY_KEY.get(dim) == dim_key


# --- gate semantics on real gold output ------------------------------
def test_feature_mart_satisfies_gates(spark, sample_transactions, sample_customers):
    pdf = build_customer_features(spark, sample_transactions, sample_customers).toPandas()

    # not-null on key columns
    for col in dq.NOT_NULL["customer_features"]:
        assert pdf[col].notna().all(), f"nulls found in customer_features.{col}"

    # primary key uniqueness
    assert pdf["customer_id"].is_unique

    # value ranges
    for col, (lo, hi) in dq.VALUE_RANGE["customer_features"].items():
        assert pdf[col].between(lo, hi).all(), f"{col} out of [{lo},{hi}]"
