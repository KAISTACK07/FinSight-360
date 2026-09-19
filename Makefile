# ============================================================
# FinSight 360 — AWS data-lake pipeline helpers
# ============================================================
# Local ($0) workflow:
#   make up            # start LocalStack + local Redshift
#   make bootstrap     # create S3 lake bucket + zones
#   make pipeline      # ingest -> transform -> load -> validate
#   make test          # lint + unit tests
#   make down          # tear everything down
# ------------------------------------------------------------

COMPOSE = docker compose -f infra/docker-compose.yml
PY = python -m

.PHONY: help up down bootstrap ingest transform load validate pipeline test lint

help:
	@grep -E '^[a-zA-Z_-]+:.*?# .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?# "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:            # start LocalStack (S3/Lambda) + local Redshift
	$(COMPOSE) up -d

down:          # stop and remove the local stack
	$(COMPOSE) down

bootstrap:     # create the S3 lake bucket + bronze/silver/gold zones
	bash infra/bootstrap_localstack.sh

ingest:        # raw CSV -> S3 bronze
	$(PY) src.aws.s3_ingest

transform:     # PySpark: bronze -> silver -> gold (+ feature mart)
	$(PY) src.aws.spark_transform

load:          # gold -> Redshift star schema (COPY / local load)
	$(PY) src.aws.redshift_load

validate:      # run data-quality gates against the warehouse
	$(PY) src.aws.data_quality

pipeline: ingest transform load validate  # full end-to-end run

lint:          # ruff lint
	ruff check src/aws dags lambda tests

test: lint     # lint + unit tests
	python -m pytest -q
