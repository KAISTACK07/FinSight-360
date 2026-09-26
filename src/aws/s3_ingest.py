"""
Stage 1 — Ingestion: land source data in the S3 **bronze** zone.

Bronze holds immutable, as-received data. We do not regenerate any of
the (partly stochastic) source data here — we take whatever the base
pipeline already produced as the source of truth and copy it in, so
row counts and engineered features are preserved exactly.

Sources, in priority order:
    1. data/processed/*.csv   (output of the base ETL, if present)
    2. data/raw/*.csv         (raw inputs)

Usage:
    python -m src.aws.s3_ingest              # ingest everything found
    python -m src.aws.s3_ingest dim_customer # ingest one dataset
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.aws.aws_config import (
    GOLD_TABLES,
    LAKE_BUCKET,
    ensure_bucket,
    get_s3_client,
    s3_key,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
logger = logging.getLogger("finsight.ingest")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEARCH_DIRS = [
    PROJECT_ROOT / "data" / "processed",
    PROJECT_ROOT / "data" / "raw",
]


def _find_source(dataset: str) -> Path | None:
    """Locate a CSV for `dataset` across the known data directories."""
    for d in SEARCH_DIRS:
        candidate = d / f"{dataset}.csv"
        if candidate.exists():
            return candidate
    return None


def ingest_dataset(dataset: str) -> bool:
    """Upload one dataset's CSV into the bronze zone. Returns True on success."""
    src = _find_source(dataset)
    if src is None:
        logger.warning("No source CSV found for '%s' (skipping)", dataset)
        return False

    s3 = get_s3_client()
    key = f"{s3_key('bronze', dataset)}/{dataset}.csv"
    s3.upload_file(str(src), LAKE_BUCKET, key)
    size_mb = src.stat().st_size / 1e6
    logger.info("bronze ← %-24s (%6.2f MB) → s3://%s/%s", dataset, size_mb, LAKE_BUCKET, key)
    return True


def ingest_all(datasets: list[str] | None = None) -> dict[str, bool]:
    """Ingest all known datasets (or a provided subset)."""
    ensure_bucket()
    targets = datasets or GOLD_TABLES
    results = {ds: ingest_dataset(ds) for ds in targets}
    ok = sum(results.values())
    logger.info("Ingestion complete: %d/%d datasets landed in bronze", ok, len(targets))
    return results


if __name__ == "__main__":
    picked = sys.argv[1:] or None
    ingest_all(picked)
