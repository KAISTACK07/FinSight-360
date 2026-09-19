"""
Campaign experiment assignment and measurement utilities.

The project does not currently contain real control/treatment assignments, so
these helpers create reproducible synthetic assignments and calculate observed
metrics without forcing treatment to outperform control.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def assign_control_treatment(
    audience: pd.DataFrame,
    campaign_id: int,
    experiment_id: str = "RETENTION_PROPENSITY_2024",
    seed: int = 42,
) -> pd.DataFrame:
    """Assign eligible customers approximately 50/50 to Control/Treatment."""
    if "customer_id" not in audience.columns:
        raise ValueError("audience must contain customer_id")

    customer_ids = audience["customer_id"].drop_duplicates().sort_values().to_numpy()
    rng = np.random.default_rng(seed)
    shuffled = customer_ids.copy()
    rng.shuffle(shuffled)

    midpoint = len(shuffled) // 2
    control = set(shuffled[:midpoint])

    rows = []
    for customer_id in shuffled:
        rows.append(
            {
                "experiment_id": experiment_id,
                "campaign_id": int(campaign_id),
                "customer_id": int(customer_id),
                "assignment_group": "Control" if customer_id in control else "Treatment",
                "random_seed": int(seed),
                "eligibility_rule": "priority_tier = 'High'",
                "is_synthetic": True,
            }
        )
    return pd.DataFrame(rows)


def build_synthetic_experiment_outcomes(
    assignments: pd.DataFrame,
    propensity: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic observed outcomes from customer propensity.

    The same response probability is used for Control and Treatment so measured
    lift is an observed result of randomized assignment, not a forced effect.
    """
    required = {"experiment_id", "campaign_id", "customer_id", "assignment_group"}
    missing = required - set(assignments.columns)
    if missing:
        raise ValueError(f"assignments missing required columns: {sorted(missing)}")

    df = assignments.merge(
        propensity[["customer_id", "propensity_score"]],
        on="customer_id",
        how="left",
    )
    df["propensity_score"] = pd.to_numeric(df["propensity_score"], errors="coerce").fillna(0).clip(0, 1)

    rng = np.random.default_rng(seed)
    df["was_exposed"] = df["assignment_group"].eq("Treatment")
    df["converted"] = rng.random(len(df)) < df["propensity_score"]
    df["conversion_value"] = np.where(df["converted"], rng.uniform(500, 5000, len(df)).round(2), 0.0)
    df["is_synthetic"] = True
    return df[
        [
            "experiment_id",
            "campaign_id",
            "customer_id",
            "assignment_group",
            "was_exposed",
            "converted",
            "conversion_value",
            "is_synthetic",
        ]
    ]


def calculate_experiment_metrics(outcomes: pd.DataFrame) -> dict:
    """Calculate control/treatment conversion rates, lift, z-test, and CI."""
    grouped = outcomes.groupby("assignment_group")["converted"].agg(["count", "sum"])

    control_n = int(grouped.loc["Control", "count"]) if "Control" in grouped.index else 0
    treatment_n = int(grouped.loc["Treatment", "count"]) if "Treatment" in grouped.index else 0
    control_x = int(grouped.loc["Control", "sum"]) if "Control" in grouped.index else 0
    treatment_x = int(grouped.loc["Treatment", "sum"]) if "Treatment" in grouped.index else 0

    control_rate = _safe_rate(control_x, control_n)
    treatment_rate = _safe_rate(treatment_x, treatment_n)
    absolute_lift = treatment_rate - control_rate
    relative_lift = absolute_lift / control_rate if control_rate else None

    test = _two_proportion_test(control_x, control_n, treatment_x, treatment_n)

    return {
        "control_customers": control_n,
        "treatment_customers": treatment_n,
        "control_responses": control_x,
        "treatment_responses": treatment_x,
        "control_conversion_rate": control_rate,
        "treatment_conversion_rate": treatment_rate,
        "absolute_lift": absolute_lift,
        "relative_lift": relative_lift,
        **test,
    }


def validate_assignment_balance(assignments: pd.DataFrame, tolerance: float = 0.05) -> dict:
    """Validate assignment uniqueness and approximate group balance."""
    duplicate_customers = int(assignments["customer_id"].duplicated().sum())
    counts = assignments["assignment_group"].value_counts().to_dict()
    total = int(sum(counts.values()))
    control_share = counts.get("Control", 0) / total if total else 0
    treatment_share = counts.get("Treatment", 0) / total if total else 0
    return {
        "passed": duplicate_customers == 0 and abs(control_share - treatment_share) <= tolerance,
        "duplicate_customers": duplicate_customers,
        "control_share": control_share,
        "treatment_share": treatment_share,
        "tolerance": tolerance,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _two_proportion_test(control_x: int, control_n: int, treatment_x: int, treatment_n: int) -> dict:
    if min(control_n, treatment_n) == 0:
        return {"z_statistic": None, "p_value": None, "confidence_interval_low": None, "confidence_interval_high": None}

    p1 = control_x / control_n
    p2 = treatment_x / treatment_n
    pooled = (control_x + treatment_x) / (control_n + treatment_n)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / control_n + 1 / treatment_n))
    z_stat = (p2 - p1) / se_pooled if se_pooled else 0.0
    p_value = math.erfc(abs(z_stat) / math.sqrt(2))

    se_unpooled = math.sqrt((p1 * (1 - p1) / control_n) + (p2 * (1 - p2) / treatment_n))
    margin = 1.96 * se_unpooled
    diff = p2 - p1

    return {
        "z_statistic": z_stat,
        "p_value": p_value,
        "confidence_interval_low": diff - margin,
        "confidence_interval_high": diff + margin,
    }
