"""
FinSight 360 — AWS Data Engineering layer.

Turns the local Python/PostgreSQL pipeline into a cloud data-lake
architecture:

    raw CSV ──► S3 bronze ──► PySpark/Glue ──► S3 silver/gold ──►
    Redshift star schema ──► (analytics / NL-SQL assistant)

Every module runs identically against LocalStack (free, local) and
real AWS. Orchestrated by Airflow, triggered by an S3-event Lambda,
and guarded by data-quality gates in CI.
"""
