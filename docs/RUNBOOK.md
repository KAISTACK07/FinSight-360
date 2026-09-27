# FinSight 360 — Local Runbook

A step-by-step checklist to run the **AWS data-lake pipeline** end-to-end on your
own machine, for free, using LocalStack + local Spark + local Postgres. Everything
here runs identically against real AWS later (see the last section).

---

## 1. Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| **Docker** (running) | LocalStack (S3/Lambda) + local Redshift (Postgres) | `docker ps` |
| **Java 17** | Spark needs a JVM | `java -version` |
| **Python 3.11** | pipeline + tests | `python --version` |
| **AWS CLI** *(optional)* | used by the bootstrap script | `aws --version` |

Docker is already installed on your machine. Install Java 17 if `java -version`
fails:

```bash
# macOS
brew install openjdk@17
# Ubuntu/Debian
sudo apt-get install -y openjdk-17-jdk
```

---

## 2. One-time setup

```bash
git clone https://github.com/kaistack07/finsight-360.git
cd finsight-360

# Python deps (base + AWS layer)
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-aws.txt

# Environment: local ($0) mode is the default in this template
cp .env.aws.example .env
```

> **PySpark install note:** if `pip install` fails building pyspark with
> `AttributeError: install_layout`, it's a newer-setuptools issue. Fix:
> ```bash
> pip install "setuptools<71" wheel
> SETUPTOOLS_USE_DISTUTILS=stdlib pip install --no-build-isolation pyspark==3.5.1
> ```

---

## 3. Provide your data

The `data/` folder is git-ignored, so the pipeline needs your CSVs placed locally.
Drop them in **`data/processed/`** (preferred) or **`data/raw/`**, named to match the
table names the pipeline expects:

```
data/processed/
├── dim_customer.csv
├── dim_product.csv
├── dim_campaign.csv
├── dim_date.csv
├── fact_transactions.csv
├── fact_service_logs.csv
└── fact_campaign_responses.csv
```

Any table whose CSV is missing is simply skipped (a warning is logged) — you can
start with just `dim_customer.csv` + `fact_transactions.csv` to smoke-test.

> Don't have the CSVs handy? Generate them first with the base ETL
> (`python -m src.etl.data_ingestion` etc.), which writes to `data/processed/`.

---

## 4. Run the pipeline

```bash
make up          # start LocalStack + local Redshift (Postgres on :5439)
make bootstrap   # create the S3 lake bucket + bronze/silver/gold zones
make pipeline    # ingest → transform → load → validate
make test        # ruff + pytest (9 tests)
```

`make pipeline` runs the four stages in order:

1. `ingest`   → uploads CSVs to `s3://finsight-360-datalake/bronze/`
2. `transform`→ PySpark: bronze → silver → gold (+ `customer_features`)
3. `load`     → gold → Redshift (local Postgres) star schema
4. `validate` → data-quality gates (nulls, uniqueness, ranges, referential integrity)

Inspect results:

```bash
# what landed in the lake
docker exec finsight-localstack awslocal s3 ls s3://finsight-360-datalake/ --recursive

# query the warehouse
docker exec -it finsight-redshift-local psql -U admin -d customer360 \
  -c "SELECT COUNT(*) FROM customer360.dim_customer;"
```

Tear down when done:

```bash
make down
```

---

## 5. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `docker: Cannot connect to the Docker daemon` | Start Docker Desktop, then re-run `make up`. |
| Port **5439** or **4566** already in use | Stop the other process, or edit the ports in `infra/docker-compose.yml`. |
| Spark: `No FileSystem for scheme "s3a"` | Let the first run download the hadoop-aws jars (needs internet); re-run `make transform`. |
| `make bootstrap` can't find `aws` | Install AWS CLI, or the bucket is auto-created by `s3_ingest` on first `make pipeline`. |
| Pipeline runs but tables are empty | Confirm your CSVs are in `data/processed/` with the exact names in §3. |
| `pyspark` build error on install | See the setuptools note in §2. |
| Java errors / `JAVA_HOME` not set | Install Java 17 (§1) and ensure `java -version` works in the same shell. |

---

## 6. Switch to real AWS (optional)

No code changes — just point the config at real services:

1. In `.env`, **comment out `AWS_ENDPOINT_URL`** (so the SDK talks to real AWS) and set
   real `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION`.
2. Set `REDSHIFT_HOST` to your Redshift Serverless endpoint and `REDSHIFT_IAM_ROLE`
   to a role allowed to `COPY` from S3.
3. Run the same `make pipeline`.

**Cost tip:** S3 + Lambda are free-tier; use the Redshift Serverless trial credit and
**pause/delete** it after use; develop Glue with the `amazon/aws-glue-libs` Docker
image (or local Spark) and do at most one real Glue run. Disciplined, this is ~$0.

---

## 7. Definition of done (local)

- [ ] `make up` brings up both containers
- [ ] `make pipeline` completes all four stages with your data
- [ ] `make test` is green (ruff + 9 pytest)
- [ ] warehouse row counts match your source data
