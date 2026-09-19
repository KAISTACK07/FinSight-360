"""
Airflow DAG — FinSight 360 data-lake pipeline.

    ingest (raw→S3 bronze)
        └─► transform (PySpark/Glue: bronze→silver→gold)
                └─► load (gold→Redshift star schema)
                        └─► validate (data-quality gates)

Design notes
------------
* Idempotent tasks: ingest overwrites bronze objects, transform writes
  Parquet with mode="overwrite", load TRUNCATEs before COPY — so a retry
  or a re-run always converges to the same warehouse state.
* Retries with exponential backoff on every task.
* The DAG is import-safe for CI: heavy modules are imported *inside* the
  task callables, so `airflow dags list` / linting never needs Spark.

Deploy: drop this file in your Airflow `dags/` folder (local Docker
Airflow is free — do not use MWAA). Triggered on a schedule here, and on
demand by the S3-event Lambda (see lambda/s3_trigger_lambda.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

DEFAULT_ARGS = {
    "owner": "finsight",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
}


# --- task callables (import heavy deps lazily) -----------------------
def _ingest(**_):
    from src.aws.s3_ingest import ingest_all

    ingest_all()


def _transform(**_):
    from src.aws.spark_transform import run

    run()


def _load(**_):
    from src.aws.redshift_load import load_all

    load_all()


def _validate(**_):
    from src.aws.data_quality import run_checks

    # Guardrail floors; tune to your real volumes.
    run_checks(min_rows={"dim_customer": 1, "fact_transactions": 1})


with DAG(
    dag_id="finsight_datalake_pipeline",
    description="raw → S3 → Spark/Glue → Redshift → quality gates",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["finsight", "aws", "data-engineering"],
) as dag:
    ingest = PythonOperator(task_id="ingest_to_bronze", python_callable=_ingest)
    transform = PythonOperator(task_id="transform_spark", python_callable=_transform)
    load = PythonOperator(task_id="load_redshift", python_callable=_load)
    validate = PythonOperator(task_id="data_quality_gates", python_callable=_validate)

    ingest >> transform >> load >> validate
