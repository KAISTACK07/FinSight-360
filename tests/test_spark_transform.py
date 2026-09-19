"""
Unit tests for the PySpark feature-engineering stage.

These lock in the meaning of the engineered features (RFM, rolling, lag,
tenure) and their determinism — the guarantee that migrating from pandas
to Spark does NOT change your numbers.
"""

from __future__ import annotations

from src.aws.spark_transform import build_customer_features


def _as_dict(df, key="customer_id"):
    return {r[key]: r.asDict() for r in df.collect()}


def test_rfm_frequency_and_monetary(spark, sample_transactions, sample_customers):
    feats = _as_dict(build_customer_features(spark, sample_transactions, sample_customers))

    # Customer 1 made 4 transactions summing to 5000; customer 2 made 2 summing to 1000.
    assert feats[1]["frequency"] == 4
    assert feats[1]["monetary"] == 5000.0
    assert feats[2]["frequency"] == 2
    assert feats[2]["monetary"] == 1000.0


def test_recency_is_relative_to_dataset_max(spark, sample_transactions, sample_customers):
    feats = _as_dict(build_customer_features(spark, sample_transactions, sample_customers))
    # Dataset max is 2024-03-25 (customer 2). Customer 1's last txn is 2024-03-05 → 20 days.
    assert feats[1]["recency_days"] == 20
    assert feats[2]["recency_days"] == 0


def test_tenure_joined_from_dimension(spark, sample_transactions, sample_customers):
    feats = _as_dict(build_customer_features(spark, sample_transactions, sample_customers))
    assert feats[1]["tenure_months"] == 40
    assert feats[2]["tenure_months"] == 12


def test_lag_and_rolling_columns_present(spark, sample_transactions, sample_customers):
    feats = build_customer_features(spark, sample_transactions, sample_customers)
    for col in ("rolling_3m_amount", "lag_1m_amount", "lag_3m_amount", "mom_change", "rfm_score"):
        assert col in feats.columns


def test_rfm_scores_in_valid_range(spark, sample_transactions, sample_customers):
    feats = build_customer_features(spark, sample_transactions, sample_customers)
    for r in feats.collect():
        for score in ("r_score", "f_score", "m_score"):
            assert 1 <= r[score] <= 5
        assert 3 <= r["rfm_score"] <= 15


def _drop_runtime_cols(feats):
    # feature_generated_at is a load-time metadata stamp and is meant to
    # differ per run; exclude it from the data-determinism comparison.
    return feats.drop("feature_generated_at")


def test_determinism(spark, sample_transactions, sample_customers):
    """Same input → identical engineered values (the anti-drift guarantee)."""
    a = _as_dict(_drop_runtime_cols(build_customer_features(spark, sample_transactions, sample_customers)))
    b = _as_dict(_drop_runtime_cols(build_customer_features(spark, sample_transactions, sample_customers)))
    assert a == b
