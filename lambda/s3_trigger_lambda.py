"""
AWS Lambda — event-driven pipeline trigger.

Wired to an S3 `ObjectCreated` notification on the bronze prefix. When a
new source file lands, this handler kicks off the pipeline instead of
waiting for the daily schedule, giving a hands-off, event-driven ingest.

Two trigger backends (chosen by env var so the same code works locally
and on real AWS):

    PIPELINE_TRIGGER=airflow  -> POST to the Airflow REST API to unpause
                                 / trigger `finsight_datalake_pipeline`
                                 (works with local Docker Airflow, free)
    PIPELINE_TRIGGER=inline   -> run ingest→transform→load→validate in
                                 process (handy for LocalStack demos)

Deploy (real AWS, free tier):
    zip lambda.zip lambda/s3_trigger_lambda.py
    aws lambda create-function --function-name finsight-s3-trigger \
        --runtime python3.11 --handler s3_trigger_lambda.handler \
        --role <role-arn> --zip-file fileb://lambda.zip
    aws s3api put-bucket-notification-configuration ... (bronze prefix)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

logger = logging.getLogger("finsight.lambda")
logger.setLevel(logging.INFO)

DAG_ID = os.getenv("PIPELINE_DAG_ID", "finsight_datalake_pipeline")
TRIGGER = os.getenv("PIPELINE_TRIGGER", "airflow").lower()
AIRFLOW_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "airflow")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD", "airflow")


def _extract_records(event: dict) -> list[str]:
    """Pull the S3 object keys out of the event (best-effort)."""
    keys = []
    for rec in event.get("Records", []):
        try:
            keys.append(rec["s3"]["object"]["key"])
        except (KeyError, TypeError):
            continue
    return keys


def _trigger_airflow() -> dict:
    import base64

    url = f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}/dagRuns"
    creds = base64.b64encode(f"{AIRFLOW_USER}:{AIRFLOW_PASSWORD}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=json.dumps({}).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return {"status": resp.status, "dag_id": DAG_ID}


def _trigger_inline() -> dict:
    from src.aws.data_quality import run_checks
    from src.aws.redshift_load import load_all
    from src.aws.s3_ingest import ingest_all
    from src.aws.spark_transform import run as transform

    ingest_all()
    transform()
    load_all()
    run_checks(min_rows={"dim_customer": 1, "fact_transactions": 1})
    return {"status": "completed", "mode": "inline"}


def handler(event, context=None):  # noqa: ANN001 - Lambda signature
    keys = _extract_records(event or {})
    logger.info("S3 event received for %d object(s): %s", len(keys), keys)

    result = _trigger_airflow() if TRIGGER == "airflow" else _trigger_inline()
    logger.info("Pipeline trigger result: %s", result)
    return {"statusCode": 200, "body": json.dumps(result)}


if __name__ == "__main__":
    # Local smoke test with a synthetic S3 event.
    sample = {"Records": [{"s3": {"object": {"key": "bronze/dim_customer/dim_customer.csv"}}}]}
    print(handler(sample))
