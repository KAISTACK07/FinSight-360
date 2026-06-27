# Data Quality Report
## Customer Finance 360° Intelligence Platform

**Generated**: 2026-06-27T00:09:43.626926

## Summary

| Metric | Value |
|---|---|
| **Data Quality Score** | **100.0%** |
| Total Checks | 51 |
| Passed | 51 |
| Failed | 0 |
| Warnings | 0 |

## Detailed Results

| Table | Check | Status | Detail |
|---|---|---|---|
| dim_customer | table_exists | ✅ PASS | Table exists |
| dim_product | table_exists | ✅ PASS | Table exists |
| dim_campaign | table_exists | ✅ PASS | Table exists |
| dim_date | table_exists | ✅ PASS | Table exists |
| fact_transactions | table_exists | ✅ PASS | Table exists |
| fact_service_logs | table_exists | ✅ PASS | Table exists |
| fact_campaign_responses | table_exists | ✅ PASS | Table exists |
| dim_customer | row_count | ✅ PASS | 10,127 rows (min: 10,000) |
| dim_product | row_count | ✅ PASS | 12 rows (min: 10) |
| dim_campaign | row_count | ✅ PASS | 5 rows (min: 5) |
| dim_date | row_count | ✅ PASS | 2,192 rows (min: 2,000) |
| fact_transactions | row_count | ✅ PASS | 656,824 rows (min: 100,000) |
| fact_service_logs | row_count | ✅ PASS | 25,293 rows (min: 5,000) |
| fact_campaign_responses | row_count | ✅ PASS | 14,142 rows (min: 1,000) |
| dim_customer | pk_unique | ✅ PASS | No duplicate customer_id |
| dim_product | pk_unique | ✅ PASS | No duplicate product_id |
| dim_campaign | pk_unique | ✅ PASS | No duplicate campaign_id |
| dim_date | pk_unique | ✅ PASS | No duplicate date_key |
| dim_customer | null_customer_id | ✅ PASS | No NULLs |
| dim_customer | null_customer_status | ✅ PASS | No NULLs |
| dim_customer | null_age | ✅ PASS | No NULLs |
| dim_customer | null_gender | ✅ PASS | No NULLs |
| dim_customer | null_income_bracket | ✅ PASS | No NULLs |
| dim_customer | null_card_category | ✅ PASS | No NULLs |
| dim_customer | null_credit_limit | ✅ PASS | No NULLs |
| dim_customer | null_total_trans_amt_12m | ✅ PASS | No NULLs |
| fact_transactions | null_customer_id | ✅ PASS | No NULLs |
| fact_transactions | null_amount | ✅ PASS | No NULLs |
| fact_transactions | null_transaction_date | ✅ PASS | No NULLs |
| fact_transactions | null_merchant_category | ✅ PASS | No NULLs |
| fact_service_logs | null_customer_id | ✅ PASS | No NULLs |
| fact_service_logs | null_complaint_date | ✅ PASS | No NULLs |
| fact_service_logs | null_complaint_category | ✅ PASS | No NULLs |
| fact_service_logs | null_priority | ✅ PASS | No NULLs |
| fact_campaign_responses | null_campaign_id | ✅ PASS | No NULLs |
| fact_campaign_responses | null_customer_id | ✅ PASS | No NULLs |
| fact_campaign_responses | null_was_contacted | ✅ PASS | No NULLs |
| fact_transactions | fk_customer_id | ✅ PASS | All customer_id reference valid dim_customer |
| fact_transactions | fk_product_id | ✅ PASS | All product_id reference valid dim_product |
| fact_transactions | fk_date_key | ✅ PASS | All date_key reference valid dim_date |
| fact_service_logs | fk_customer_id | ✅ PASS | All customer_id reference valid dim_customer |
| fact_service_logs | fk_date_key | ✅ PASS | All date_key reference valid dim_date |
| fact_campaign_responses | fk_customer_id | ✅ PASS | All customer_id reference valid dim_customer |
| fact_campaign_responses | fk_campaign_id | ✅ PASS | All campaign_id reference valid dim_campaign |
| fact_campaign_responses | fk_date_key | ✅ PASS | All date_key reference valid dim_date |
| dim_customer | age_range | ✅ PASS | 0 customers outside 18-100 age range |
| fact_service_logs | csat_range | ✅ PASS | 0 records with CSAT outside 1-5 |
| fact_transactions | positive_amounts | ✅ PASS | 0 transactions with zero/negative amount |
| dim_customer | valid_status | ✅ PASS | 0 invalid customer_status values |
| fact_campaign_responses | funnel_logic | ✅ PASS | 0 records with broken funnel sequence |
| fact_transactions | no_future_dates | ✅ PASS | 0 transactions with future dates |

## Interpretation

✅ Data quality is acceptable. Proceed with analytics.

## Corrective Actions

No corrective actions required.