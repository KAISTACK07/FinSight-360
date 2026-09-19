"""
Campaign feature engineering for FinSight 360.

Builds point-in-time customer-campaign features from PostgreSQL. The training
target comes from fact_campaign_responses.was_accepted, while all feature
aggregates are restricted to transactions before each campaign start date.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.etl.config import SCHEMA, get_engine

logger = logging.getLogger("customer360.campaign_features")


LEAKAGE_COLUMNS = {
    "response_id",
    "response_date",
    "was_contacted",
    "was_opened",
    "was_clicked",
    "was_accepted",
    "conversion_value",
    "days_to_response",
    "assignment_group",
    "experiment_id",
    "converted",
    "outcome_date",
    "customer_status",
    "total_trans_amt_12m",
    "total_trans_ct_12m",
}

NUMERIC_FEATURES = [
    "age",
    "tenure_months_at_campaign",
    "total_products_held",
    "credit_utilization_ratio",
    "months_inactive_12m",
    "contacts_count_12m",
    "hist_frequency",
    "hist_monetary",
    "hist_avg_transaction_value",
    "hist_recency_days",
    "campaign_budget",
]

CATEGORICAL_FEATURES = [
    "gender",
    "income_bracket",
    "card_category",
    "preferred_channel",
    "campaign_type",
    "campaign_channel",
    "campaign_objective",
    "target_segment",
]


def load_campaign_training_data(engine=None) -> pd.DataFrame:
    """Load customer-campaign training rows with historical response target."""
    return _load_campaign_rows(include_target=True, engine=engine)


def load_campaign_scoring_data(engine=None) -> pd.DataFrame:
    """Load every customer-campaign combination for portfolio scoring."""
    return _load_campaign_rows(include_target=False, engine=engine)


def build_model_matrix(
    df: pd.DataFrame,
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Convert raw campaign features into a model matrix.

    If feature_columns is provided, the output is aligned to that column set.
    This keeps training and scoring matrices consistent.
    """
    missing = [col for col in NUMERIC_FEATURES + CATEGORICAL_FEATURES if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required campaign feature columns: {missing}")

    features = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    for col in NUMERIC_FEATURES:
        features[col] = pd.to_numeric(features[col], errors="coerce").fillna(0)
    for col in CATEGORICAL_FEATURES:
        features[col] = features[col].fillna("Unknown").astype(str)

    encoded = pd.get_dummies(features, columns=CATEGORICAL_FEATURES, drop_first=False)
    encoded = encoded.astype(float)

    if feature_columns is not None:
        encoded = encoded.reindex(columns=feature_columns, fill_value=0.0)
        return encoded, feature_columns

    return encoded, list(encoded.columns)


def audit_campaign_leakage(feature_columns: list[str]) -> dict:
    """Return a deterministic leakage audit for the selected model features."""
    lower_columns = {col.lower() for col in feature_columns}
    leaked = sorted(col for col in LEAKAGE_COLUMNS if col.lower() in lower_columns)
    return {
        "passed": len(leaked) == 0,
        "leakage_columns_found": leaked,
        "leakage_columns_excluded": sorted(LEAKAGE_COLUMNS),
        "feature_count": len(feature_columns),
    }


def _load_campaign_rows(include_target: bool, engine=None) -> pd.DataFrame:
    engine = engine or get_engine()
    base_relation = f"{SCHEMA}.fact_campaign_responses fcr JOIN {SCHEMA}.dim_campaign camp ON fcr.campaign_id = camp.campaign_id"
    target_columns = """
        fcr.response_id,
        fcr.was_accepted::int AS target_response,
    """
    if not include_target:
        base_relation = f"{SCHEMA}.dim_customer dc CROSS JOIN {SCHEMA}.dim_campaign camp"
        target_columns = ""

    if include_target:
        customer_join = f"JOIN {SCHEMA}.dim_customer dc ON fcr.customer_id = dc.customer_id"
        id_columns = """
            fcr.customer_id,
            fcr.campaign_id,
        """
    else:
        customer_join = ""
        id_columns = """
            dc.customer_id,
            camp.campaign_id,
        """

    query = f"""
    SELECT
        {id_columns}
        {target_columns}
        dc.age,
        dc.gender,
        dc.income_bracket,
        dc.card_category,
        dc.preferred_channel,
        GREATEST(
            0,
            (
                EXTRACT(YEAR FROM age(camp.start_date, dc.customer_since)) * 12
                + EXTRACT(MONTH FROM age(camp.start_date, dc.customer_since))
            )::int
        ) AS tenure_months_at_campaign,
        dc.total_products_held,
        dc.credit_utilization_ratio,
        dc.months_inactive_12m,
        dc.contacts_count_12m,
        camp.campaign_type,
        COALESCE(camp.campaign_channel, 'Unknown') AS campaign_channel,
        camp.objective AS campaign_objective,
        camp.target_segment,
        camp.budget AS campaign_budget,
        COALESCE(tx.hist_frequency, 0) AS hist_frequency,
        COALESCE(tx.hist_monetary, 0) AS hist_monetary,
        CASE
            WHEN COALESCE(tx.hist_frequency, 0) > 0
                THEN COALESCE(tx.hist_monetary, 0) / tx.hist_frequency
            ELSE 0
        END AS hist_avg_transaction_value,
        COALESCE((camp.start_date - tx.last_transaction_date::date), 365) AS hist_recency_days
    FROM {base_relation}
    {customer_join}
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*) AS hist_frequency,
            SUM(ft.amount) AS hist_monetary,
            MAX(ft.transaction_date) AS last_transaction_date
        FROM {SCHEMA}.fact_transactions ft
        WHERE ft.customer_id = dc.customer_id
          AND ft.transaction_date < camp.start_date
    ) tx ON TRUE
    ORDER BY dc.customer_id, camp.campaign_id
    """
    logger.info("Loading campaign %s data from PostgreSQL", "training" if include_target else "scoring")
    df = pd.read_sql(text(query), engine)
    logger.info("Loaded %s campaign rows", len(df))
    return df


def aggregate_customer_propensity(scored_rows: pd.DataFrame) -> pd.DataFrame:
    """Collapse customer-campaign probabilities into customer-level scores."""
    if "campaign_probability" not in scored_rows.columns:
        raise ValueError("campaign_probability column is required")
    return (
        scored_rows.groupby("customer_id", as_index=False)["campaign_probability"]
        .mean()
        .rename(columns={"campaign_probability": "propensity_score"})
    )


def calculate_target_priority(propensity_df: pd.DataFrame, engine=None) -> pd.DataFrame:
    """Join CLV/churn outputs and calculate the transparent priority heuristic."""
    engine = engine or get_engine()
    enrich_query = f"""
    SELECT
        dc.customer_id,
        COALESCE(clv.predicted_clv_12m, 0) AS predicted_clv_12m,
        COALESCE(ch.churn_probability, 0) AS churn_probability
    FROM {SCHEMA}.dim_customer dc
    LEFT JOIN {SCHEMA}.clv_predictions clv ON dc.customer_id = clv.customer_id
    LEFT JOIN {SCHEMA}.ml_churn_predictions ch ON dc.customer_id = ch.customer_id
    """
    enrich = pd.read_sql(text(enrich_query), engine)
    df = propensity_df.merge(enrich, on="customer_id", how="left")
    df["propensity_score"] = pd.to_numeric(df["propensity_score"], errors="coerce").fillna(0).clip(0, 1)
    df["predicted_clv_12m"] = pd.to_numeric(df["predicted_clv_12m"], errors="coerce").fillna(0)
    df["churn_probability"] = pd.to_numeric(df["churn_probability"], errors="coerce").fillna(0).clip(0, 1)

    p01 = df["predicted_clv_12m"].quantile(0.01)
    p99 = df["predicted_clv_12m"].quantile(0.99)
    if not np.isfinite(p99) or p99 <= p01:
        df["normalized_clv"] = 0.0
    else:
        clipped = df["predicted_clv_12m"].clip(lower=p01, upper=p99)
        df["normalized_clv"] = ((clipped - p01) / (p99 - p01)).clip(0, 1)

    df["target_priority_score"] = (
        df["propensity_score"] * 0.4
        + df["normalized_clv"] * 0.4
        + df["churn_probability"] * 0.2
    ).clip(0, 1)

    df["propensity_tier"] = pd.cut(
        df["propensity_score"],
        bins=[-0.001, 0.4, 0.7, 1.0],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    df["priority_tier"] = pd.cut(
        df["target_priority_score"],
        bins=[-0.001, 0.33, 0.66, 1.0],
        labels=["Low", "Medium", "High"],
    ).astype(str)

    return df[
        [
            "customer_id",
            "propensity_score",
            "propensity_tier",
            "target_priority_score",
            "priority_tier",
            "normalized_clv",
        ]
    ]
