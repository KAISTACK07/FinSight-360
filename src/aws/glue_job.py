"""
AWS Glue entrypoint for the FinSight transform.

Glue provides a managed (serverless) Spark runtime. This thin wrapper
lets the SAME transform logic in `spark_transform.run()` execute as a
Glue job with zero code duplication.

Deploy (real AWS):
    aws s3 cp src/aws/glue_job.py            s3://<bucket>/glue/glue_job.py
    aws s3 cp src/aws/spark_transform.py     s3://<bucket>/glue/
    aws s3 cp src/aws/aws_config.py          s3://<bucket>/glue/
    aws glue create-job \
        --name finsight-transform \
        --role  <GlueServiceRole> \
        --command Name=glueetl,ScriptLocation=s3://<bucket>/glue/glue_job.py,PythonVersion=3 \
        --glue-version 4.0 \
        --default-arguments '{"--extra-py-files":"s3://<bucket>/glue/spark_transform.py,s3://<bucket>/glue/aws_config.py"}'

Run locally (free) with the identical logic:
    python -m src.aws.spark_transform

Cost note: Glue has no permanent free tier. Develop with the
`amazon/aws-glue-libs` Docker image or local Spark for $0; do one real
Glue run for screenshots (a few cents–dollars, or covered by new-account
credits) when you want a real-AWS artifact.
"""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
logger = logging.getLogger("finsight.glue")


def main() -> None:
    # Inside Glue, GlueContext/SparkContext already exist; we reuse the
    # active SparkSession so the transform runs on Glue's Spark cluster.
    try:
        from awsglue.context import GlueContext  # provided by the Glue runtime
        from pyspark.context import SparkContext

        sc = SparkContext.getOrCreate()
        glue_ctx = GlueContext(sc)
        spark = glue_ctx.spark_session
        logger.info("Running inside AWS Glue runtime.")
    except Exception:
        # Local fallback: build our own configured session.
        from src.aws.aws_config import get_spark

        spark = get_spark("finsight-transform-glue-local")
        logger.info("Glue runtime not detected — using local Spark session.")

    from src.aws.spark_transform import run

    run(spark)


if __name__ == "__main__":
    main()
