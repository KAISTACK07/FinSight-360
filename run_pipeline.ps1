python -m src.etl.data_ingestion
if ($LASTEXITCODE -ne 0) { exit 1 }
python -m src.etl.warehouse_loader
if ($LASTEXITCODE -ne 0) { exit 1 }
python -m src.ml.churn_model
if ($LASTEXITCODE -ne 0) { exit 1 }
python -m src.ml.segmentation_model
if ($LASTEXITCODE -ne 0) { exit 1 }
python -m src.etl.business_validation
if ($LASTEXITCODE -ne 0) { exit 1 }
