"""
FinSight 360: Campaign Propensity and Experimentation Pipeline.

Trains an interpretable response propensity model from existing campaign
response history, calculates a transparent target priority heuristic, and
creates a reproducible synthetic-labeled Control/Treatment experiment.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text

from src.etl.campaign_features import (
    aggregate_customer_propensity,
    audit_campaign_leakage,
    build_model_matrix,
    calculate_target_priority,
    load_campaign_scoring_data,
    load_campaign_training_data,
)
from src.etl.config import PROJECT_ROOT, SCHEMA, get_connection_url
from src.ml.campaign_experiment import (
    assign_control_treatment,
    build_synthetic_experiment_outcomes,
    calculate_experiment_metrics,
    validate_assignment_balance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)-24s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("customer360.campaign_propensity")

MODEL_VERSION = "campaign_propensity_v1"
TARGET_CAMPAIGN_ID = 3
EXPERIMENT_ID = "RETENTION_PROPENSITY_2024"
RANDOM_SEED = 42

def _load_campaign_context(engine) -> dict:
    """Fetch campaign metadata used to persist the summary metrics row."""
    query = text(
        f"""
        SELECT campaign_name, objective
        FROM {SCHEMA}.dim_campaign
        WHERE campaign_id = :campaign_id
        """
    )
    with engine.begin() as conn:
        row = conn.execute(query, {"campaign_id": TARGET_CAMPAIGN_ID}).mappings().first()
    if row is None:
        return {"campaign_name": f"Campaign {TARGET_CAMPAIGN_ID}", "objective": "Unknown"}
    return {"campaign_name": row["campaign_name"], "objective": row["objective"]}



def run_campaign_propensity():
    """Train propensity, score customers, assign experiment, and load outputs."""
    logger.info("=" * 60)
    logger.info("Starting Campaign Propensity Modeling & Experimentation")
    logger.info("=" * 60)

    engine = create_engine(get_connection_url())
    campaign_context = _load_campaign_context(engine)

    training_df = load_campaign_training_data(engine)
    if training_df.empty:
        raise ValueError("No campaign response rows found for propensity training")

    positive_rate = float(training_df["target_response"].mean())
    logger.info("Historical campaign response rows: %s", len(training_df))
    logger.info("Positive response rate: %.2f%%", positive_rate * 100)

    X, feature_columns = build_model_matrix(training_df)
    y = training_df["target_response"].astype(int)

    leakage_audit = audit_campaign_leakage(feature_columns)
    logger.info("Leakage audit: %s", leakage_audit)
    if not leakage_audit["passed"]:
        raise ValueError(f"Campaign feature leakage detected: {leakage_audit['leakage_columns_found']}")

    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

    stratify = y if y.nunique() == 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled,
        y,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=stratify,
    )

    model = LogisticRegression(random_state=RANDOM_SEED, class_weight="balanced", max_iter=1000)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = _build_metrics(y_test, y_pred, y_prob, feature_columns, leakage_audit, positive_rate)
    logger.info("Campaign propensity metrics: %s", metrics)

    scoring_df = load_campaign_scoring_data(engine)
    X_score, _ = build_model_matrix(scoring_df, feature_columns)
    X_score_scaled = pd.DataFrame(scaler.transform(X_score), columns=X_score.columns)
    scoring_df["campaign_probability"] = model.predict_proba(X_score_scaled)[:, 1]

    customer_propensity = aggregate_customer_propensity(scoring_df)
    propensity_df = calculate_target_priority(customer_propensity, engine)
    propensity_df["model_version"] = MODEL_VERSION
    propensity_df["prediction_date"] = pd.Timestamp.now().date()
    propensity_df["is_synthetic_training"] = True

    db_propensity_df = propensity_df[
        [
            "customer_id",
            "propensity_score",
            "propensity_tier",
            "target_priority_score",
            "priority_tier",
            "normalized_clv",
            "model_version",
            "prediction_date",
            "is_synthetic_training",
        ]
    ].copy()

    audience = db_propensity_df[db_propensity_df["priority_tier"] == "High"]
    assignments = assign_control_treatment(
        audience,
        campaign_id=TARGET_CAMPAIGN_ID,
        experiment_id=EXPERIMENT_ID,
        seed=RANDOM_SEED,
    )
    balance = validate_assignment_balance(assignments)
    outcomes = build_synthetic_experiment_outcomes(assignments, db_propensity_df, seed=RANDOM_SEED)
    experiment_metrics = calculate_experiment_metrics(outcomes)
    experiment_metrics["assignment_balance"] = balance
    experiment_metrics["experiment_id"] = EXPERIMENT_ID
    experiment_metrics["campaign_id"] = TARGET_CAMPAIGN_ID
    experiment_metrics.update(campaign_context)
    experiment_metrics["is_synthetic"] = True

    metrics_df = pd.DataFrame([experiment_metrics])

    _save_artifacts(model, scaler, feature_columns, metrics, experiment_metrics, db_propensity_df, assignments, outcomes, metrics_df)
    _load_outputs(engine, db_propensity_df, assignments, outcomes, metrics_df)

    logger.info("=" * 60)
    logger.info("Campaign Propensity Modeling Complete")
    logger.info("=" * 60)
    return {
        "metrics": metrics,
        "experiment_metrics": experiment_metrics,
        "propensity_rows": len(db_propensity_df),
        "experiment_rows": len(assignments),
    }


def _build_metrics(y_test, y_pred, y_prob, feature_columns, leakage_audit, positive_rate: float) -> dict:
    return {
        "model": "LogisticRegression",
        "model_version": MODEL_VERSION,
        "target": "fact_campaign_responses.was_accepted",
        "training_grain": "customer_campaign",
        "output_grain": "customer",
        "evaluation_type": "stratified_holdout",
        "test_size": 0.2,
        "random_seed": RANDOM_SEED,
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
        "positive_response_rate": positive_rate,
        "feature_count": len(feature_columns),
        "features_used": feature_columns,
        "leakage_audit": leakage_audit,
        "synthetic_data_disclosure": (
            "fact_campaign_responses is generated demo campaign history in this project; "
            "metrics are calculated from holdout rows and are not hardcoded."
        ),
        "target_priority_formula": "0.4 * propensity_score + 0.4 * normalized_clv + 0.2 * churn_probability",
    }


def _save_artifacts(model, scaler, feature_columns, metrics, experiment_metrics, propensity_df, assignments, outcomes, metrics_df):
    output_dir = Path(PROJECT_ROOT) / "data" / "output"
    models_dir = Path(PROJECT_ROOT) / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, models_dir / "campaign_propensity_lr.pkl")
    joblib.dump(scaler, models_dir / "campaign_propensity_scaler.pkl")
    with open(models_dir / "campaign_propensity_features.json", "w", encoding="utf-8") as f:
        json.dump({"features": feature_columns, "model_version": MODEL_VERSION}, f, indent=4)

    propensity_df.to_csv(output_dir / "campaign_propensity_scores.csv", index=False)
    assignments.to_csv(output_dir / "campaign_experiment_assignments.csv", index=False)
    outcomes.to_csv(output_dir / "campaign_experiment_outcomes.csv", index=False)
    metrics_df.to_csv(output_dir / "campaign_experiment_metrics.csv", index=False)

    with open(output_dir / "campaign_propensity_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)
    with open(output_dir / "campaign_experiment_metrics.json", "w", encoding="utf-8") as f:
        json.dump(experiment_metrics, f, indent=4)


def _load_outputs(engine, propensity_df, assignments, outcomes, metrics_df):
    sql_path = os.path.join(PROJECT_ROOT, "src", "sql", "14_campaign_propensity.sql")
    with engine.begin() as conn:
        with open(sql_path, "r", encoding="utf-8-sig") as f:
            sql_script = f.read()
        for statement in sql_script.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))

        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.campaign_experiment_metrics CASCADE"))
        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.campaign_experiment_outcomes CASCADE"))
        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.campaign_experiments CASCADE"))
        conn.execute(text(f"TRUNCATE TABLE {SCHEMA}.ml_campaign_propensity CASCADE"))

        propensity_df.to_sql(
            name="ml_campaign_propensity",
            con=conn,
            schema=SCHEMA,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
        assignments.to_sql(
            name="campaign_experiments",
            con=conn,
            schema=SCHEMA,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
        outcomes.to_sql(
            name="campaign_experiment_outcomes",
            con=conn,
            schema=SCHEMA,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
        metrics_df.to_sql(
            name="campaign_experiment_metrics",
            con=conn,
            schema=SCHEMA,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )

    logger.info("Loaded %s propensity rows", len(propensity_df))
    logger.info("Loaded %s experiment assignments", len(assignments))
    logger.info("Loaded %s experiment outcomes", len(outcomes))
    logger.info("Loaded %s experiment metric rows", len(metrics_df))


if __name__ == "__main__":
    run_campaign_propensity()

