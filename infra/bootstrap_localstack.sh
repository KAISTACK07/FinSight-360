#!/usr/bin/env bash
# ============================================================
# Bootstrap the local data lake on LocalStack ($0).
# Creates the lake bucket and the bronze/silver/gold zones.
# Idempotent — safe to re-run.
# ============================================================
set -euo pipefail

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
REGION="${AWS_REGION:-ap-south-1}"
BUCKET="${LAKE_BUCKET:-finsight-360-datalake}"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$REGION"

aws() { command aws --endpoint-url "$ENDPOINT" "$@"; }

echo "→ Creating lake bucket: s3://${BUCKET}"
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --create-bucket-configuration LocationConstraint="$REGION" \
  2>/dev/null || echo "  (bucket already exists)"

# Zone markers so the prefixes exist even before data lands.
for zone in bronze silver gold; do
  echo "→ Ensuring zone: ${zone}/"
  echo "FinSight 360 ${zone} zone" | aws s3 cp - "s3://${BUCKET}/${zone}/_zone"
done

echo "✅ Data lake ready:"
aws s3 ls "s3://${BUCKET}/" --recursive
