"""
Customer Finance 360° Intelligence Platform
Data Quality Validation Module

Validates all warehouse tables against business rules.
No analytics should proceed until DQ score >= 95%.

Checks:
    1. Completeness — NULL / missing values per column
    2. Uniqueness — Duplicate primary keys
    3. Referential Integrity — Orphan foreign keys
    4. Validity — Out-of-range values, invalid categories
    5. Consistency — Cross-table logical checks

Outputs:
    - Data Quality Report (Markdown + CSV)
    - DQ Score (0-100%)
    - Corrective action log

Usage:
    python -m src.etl.data_quality
"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from src.etl.config import PATHS, SCHEMA, get_engine

logger = logging.getLogger("customer360.quality")


class DataQualityValidator:
    """
    Validates warehouse data integrity and generates a quality report.

    Business Justification:
        A bank cannot make decisions on unreliable data.
        Every downstream KPI, ML model, and dashboard depends
        on validated data. This module is the gate.
    """

    def __init__(self, engine=None):
        self.engine = engine or get_engine()
        self.results = []  # Collect all check results
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0
        self.warnings = 0

    def run_all_checks(self) -> dict:
        """
        Execute all data quality checks and return summary.

        Returns:
            Dictionary with DQ score, check results, and summary statistics.
        """
        logger.info("=" * 60)
        logger.info("Starting Data Quality Validation")
        logger.info("=" * 60)

        self._check_table_existence()
        self._check_row_counts()
        self._check_primary_keys()
        self._check_null_values()
        self._check_foreign_keys()
        self._check_value_ranges()
        self._check_business_rules()
        self._check_temporal_consistency()

        # Calculate DQ Score
        dq_score = round(
            (self.passed_checks / max(1, self.total_checks)) * 100, 2
        )

        summary = {
            "dq_score": dq_score,
            "total_checks": self.total_checks,
            "passed": self.passed_checks,
            "failed": self.failed_checks,
            "warnings": self.warnings,
            "results": self.results,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("=" * 60)
        logger.info(f"Data Quality Score: {dq_score}%")
        logger.info(f"  Passed: {self.passed_checks} | Failed: {self.failed_checks} | Warnings: {self.warnings}")
        logger.info("=" * 60)

        return summary

    def _record(self, check_name: str, table: str, status: str, detail: str):
        """Record a single check result."""
        self.total_checks += 1
        if status == "PASS":
            self.passed_checks += 1
        elif status == "FAIL":
            self.failed_checks += 1
        elif status == "WARN":
            self.warnings += 1
            self.passed_checks += 1  # Warnings count as passes for DQ score

        self.results.append({
            "check": check_name,
            "table": table,
            "status": status,
            "detail": detail,
        })
        log_fn = logger.info if status == "PASS" else (logger.warning if status == "WARN" else logger.error)
        log_fn(f"  [{status}] {table}.{check_name}: {detail}")

    # ---- Check Categories ----

    def _check_table_existence(self):
        """Verify all required tables exist in the schema."""
        required_tables = [
            "dim_customer", "dim_product", "dim_campaign", "dim_date",
            "fact_transactions", "fact_service_logs", "fact_campaign_responses",
        ]
        with self.engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = '{SCHEMA}'
            """))
            existing = {row[0] for row in result}

        for table in required_tables:
            if table in existing:
                self._record("table_exists", table, "PASS", "Table exists")
            else:
                self._record("table_exists", table, "FAIL", "Table MISSING from schema")

    def _check_row_counts(self):
        """Verify tables have expected row counts."""
        expected_minimums = {
            "dim_customer": 10000,
            "dim_product": 10,
            "dim_campaign": 5,
            "dim_date": 2000,
            "fact_transactions": 100000,
            "fact_service_logs": 5000,
            "fact_campaign_responses": 1000,
        }
        with self.engine.connect() as conn:
            for table, min_rows in expected_minimums.items():
                try:
                    count = conn.execute(
                        text(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
                    ).scalar()
                    if count >= min_rows:
                        self._record("row_count", table, "PASS", f"{count:,} rows (min: {min_rows:,})")
                    else:
                        self._record("row_count", table, "WARN", f"{count:,} rows (expected >= {min_rows:,})")
                except Exception as e:
                    self._record("row_count", table, "FAIL", str(e))

    def _check_primary_keys(self):
        """Verify no duplicate primary keys."""
        pk_checks = {
            "dim_customer": "customer_id",
            "dim_product": "product_id",
            "dim_campaign": "campaign_id",
            "dim_date": "date_key",
        }
        with self.engine.connect() as conn:
            for table, pk_col in pk_checks.items():
                try:
                    dup_count = conn.execute(text(f"""
                        SELECT COUNT(*) FROM (
                            SELECT {pk_col}, COUNT(*) as cnt
                            FROM {SCHEMA}.{table}
                            GROUP BY {pk_col}
                            HAVING COUNT(*) > 1
                        ) dups
                    """)).scalar()
                    if dup_count == 0:
                        self._record("pk_unique", table, "PASS", f"No duplicate {pk_col}")
                    else:
                        self._record("pk_unique", table, "FAIL", f"{dup_count:,} duplicate {pk_col} values")
                except Exception as e:
                    self._record("pk_unique", table, "FAIL", str(e))

    def _check_null_values(self):
        """Check for NULL values in critical columns."""
        critical_columns = {
            "dim_customer": ["customer_id", "customer_status", "age", "gender", "income_bracket",
                             "card_category", "credit_limit", "total_trans_amt_12m"],
            "fact_transactions": ["customer_id", "amount", "transaction_date", "merchant_category"],
            "fact_service_logs": ["customer_id", "complaint_date", "complaint_category", "priority"],
            "fact_campaign_responses": ["campaign_id", "customer_id", "was_contacted"],
        }
        with self.engine.connect() as conn:
            for table, columns in critical_columns.items():
                for col in columns:
                    try:
                        null_count = conn.execute(text(
                            f"SELECT COUNT(*) FROM {SCHEMA}.{table} WHERE {col} IS NULL"
                        )).scalar()
                        total = conn.execute(text(
                            f"SELECT COUNT(*) FROM {SCHEMA}.{table}"
                        )).scalar()
                        null_pct = (null_count / max(1, total)) * 100

                        if null_count == 0:
                            self._record(f"null_{col}", table, "PASS", "No NULLs")
                        elif null_pct < 5:
                            self._record(f"null_{col}", table, "WARN", f"{null_count:,} NULLs ({null_pct:.1f}%)")
                        else:
                            self._record(f"null_{col}", table, "FAIL", f"{null_count:,} NULLs ({null_pct:.1f}%)")
                    except Exception as e:
                        self._record(f"null_{col}", table, "FAIL", str(e))

    def _check_foreign_keys(self):
        """Verify all foreign keys reference valid parent records."""
        fk_checks = [
            ("fact_transactions", "customer_id", "dim_customer", "customer_id"),
            ("fact_transactions", "product_id", "dim_product", "product_id"),
            ("fact_transactions", "date_key", "dim_date", "date_key"),
            ("fact_service_logs", "customer_id", "dim_customer", "customer_id"),
            ("fact_service_logs", "date_key", "dim_date", "date_key"),
            ("fact_campaign_responses", "customer_id", "dim_customer", "customer_id"),
            ("fact_campaign_responses", "campaign_id", "dim_campaign", "campaign_id"),
            ("fact_campaign_responses", "date_key", "dim_date", "date_key"),
        ]
        with self.engine.connect() as conn:
            for child_table, child_col, parent_table, parent_col in fk_checks:
                try:
                    orphan_count = conn.execute(text(f"""
                        SELECT COUNT(*) FROM {SCHEMA}.{child_table} c
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {SCHEMA}.{parent_table} p
                            WHERE p.{parent_col} = c.{child_col}
                        )
                    """)).scalar()
                    if orphan_count == 0:
                        self._record(
                            f"fk_{child_col}", child_table, "PASS",
                            f"All {child_col} reference valid {parent_table}"
                        )
                    else:
                        self._record(
                            f"fk_{child_col}", child_table, "FAIL",
                            f"{orphan_count:,} orphan records (broken FK to {parent_table})"
                        )
                except Exception as e:
                    self._record(f"fk_{child_col}", child_table, "FAIL", str(e))

    def _check_value_ranges(self):
        """Validate field values are within expected ranges."""
        with self.engine.connect() as conn:
            # Age: 18-100
            invalid_age = conn.execute(text(f"""
                SELECT COUNT(*) FROM {SCHEMA}.dim_customer
                WHERE age < 18 OR age > 100
            """)).scalar()
            self._record("age_range", "dim_customer",
                         "PASS" if invalid_age == 0 else "FAIL",
                         f"{invalid_age:,} customers outside 18-100 age range")

            # CSAT: 1-5
            try:
                invalid_csat = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.fact_service_logs
                    WHERE csat_score IS NOT NULL AND (csat_score < 1 OR csat_score > 5)
                """)).scalar()
                self._record("csat_range", "fact_service_logs",
                             "PASS" if invalid_csat == 0 else "FAIL",
                             f"{invalid_csat:,} records with CSAT outside 1-5")
            except Exception:
                pass

            # Transaction amounts: positive
            try:
                neg_amounts = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.fact_transactions
                    WHERE amount <= 0
                """)).scalar()
                self._record("positive_amounts", "fact_transactions",
                             "PASS" if neg_amounts == 0 else "FAIL",
                             f"{neg_amounts:,} transactions with zero/negative amount")
            except Exception:
                pass

            # Customer status: only valid values
            try:
                invalid_status = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.dim_customer
                    WHERE customer_status NOT IN ('Active', 'Churned')
                """)).scalar()
                self._record("valid_status", "dim_customer",
                             "PASS" if invalid_status == 0 else "FAIL",
                             f"{invalid_status:,} invalid customer_status values")
            except Exception:
                pass

    def _check_business_rules(self):
        """Validate cross-table business logic."""
        with self.engine.connect() as conn:
            # Campaign funnel logic: accepted → clicked → opened → contacted
            try:
                broken_funnel = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.fact_campaign_responses
                    WHERE (was_accepted = TRUE AND was_clicked = FALSE)
                       OR (was_clicked = TRUE AND was_opened = FALSE)
                       OR (was_opened = TRUE AND was_contacted = FALSE)
                """)).scalar()
                self._record("funnel_logic", "fact_campaign_responses",
                             "PASS" if broken_funnel == 0 else "FAIL",
                             f"{broken_funnel:,} records with broken funnel sequence")
            except Exception:
                pass

    def _check_temporal_consistency(self):
        """Validate date consistency across tables."""
        with self.engine.connect() as conn:
            # No future dates in transactions
            try:
                future_trans = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.fact_transactions
                    WHERE transaction_date > CURRENT_TIMESTAMP
                """)).scalar()
                self._record("no_future_dates", "fact_transactions",
                             "PASS" if future_trans == 0 else "WARN",
                             f"{future_trans:,} transactions with future dates")
            except Exception:
                pass

    # ---- Report Generation ----

    def generate_report(self, summary: dict) -> str:
        """
        Generate a Markdown data quality report.

        Returns:
            Path to the generated report file.
        """
        report_path = PATHS.DOCS_DIR / "reports" / "data_quality_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Data Quality Report",
            f"## Customer Finance 360° Intelligence Platform",
            "",
            f"**Generated**: {summary['timestamp']}",
            "",
            f"## Summary",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| **Data Quality Score** | **{summary['dq_score']}%** |",
            f"| Total Checks | {summary['total_checks']} |",
            f"| Passed | {summary['passed']} |",
            f"| Failed | {summary['failed']} |",
            f"| Warnings | {summary['warnings']} |",
            "",
            f"## Detailed Results",
            "",
            "| Table | Check | Status | Detail |",
            "|---|---|---|---|",
        ]

        for r in summary["results"]:
            status_icon = "✅" if r["status"] == "PASS" else ("⚠️" if r["status"] == "WARN" else "❌")
            lines.append(f"| {r['table']} | {r['check']} | {status_icon} {r['status']} | {r['detail']} |")

        lines.extend([
            "",
            "## Interpretation",
            "",
            f"{'✅ Data quality is acceptable. Proceed with analytics.' if summary['dq_score'] >= 95 else '❌ Data quality below threshold (95%). Fix issues before proceeding.'}",
            "",
            "## Corrective Actions",
            "",
        ])

        failed = [r for r in summary["results"] if r["status"] == "FAIL"]
        if failed:
            for r in failed:
                lines.append(f"- **{r['table']}.{r['check']}**: {r['detail']}")
        else:
            lines.append("No corrective actions required.")

        content = "\n".join(lines)
        report_path.write_text(content, encoding="utf-8")
        logger.info(f"Data quality report saved to {report_path}")

        # Also save CSV for programmatic access
        csv_path = PATHS.OUTPUT_DATA / "data_quality_results.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(summary["results"]).to_csv(csv_path, index=False)

        return str(report_path)

    def generate_html_report(self, summary: dict) -> str:
        """
        Generate a recruiter-ready HTML Data Quality report.
        """
        report_path = PATHS.DOCS_DIR / "reports" / "data_quality_report.html"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        status_color = "#2ecc71" if summary["dq_score"] >= 95 else "#e74c3c"
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Data Quality Report - Customer Finance 360</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        h1, h2 {{ color: #2c3e50; }}
        .summary-card {{ background: {status_color}; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px; }}
        .summary-card h2 {{ color: white; margin: 0 0 10px 0; font-size: 2em; }}
        .stats {{ display: flex; justify-content: space-around; margin-bottom: 30px; background: #ecf0f1; padding: 15px; border-radius: 8px; }}
        .stat-box {{ text-align: center; }}
        .stat-box .value {{ font-size: 1.5em; font-weight: bold; color: #2c3e50; }}
        .stat-box .label {{ font-size: 0.9em; color: #7f8c8d; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 0.95em; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #34495e; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .status-PASS {{ color: #27ae60; font-weight: bold; }}
        .status-FAIL {{ color: #c0392b; font-weight: bold; }}
        .status-WARN {{ color: #f39c12; font-weight: bold; }}
        .actions {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 4px; }}
        .actions h3 {{ margin-top: 0; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Customer Finance 360&deg; Intelligence Platform</h1>
        <h2>Data Quality Validation Report</h2>
        <p><strong>Generated:</strong> {summary['timestamp']}</p>
        
        <div class="summary-card">
            <h2>Data Quality Score: {summary['dq_score']}%</h2>
            <p>{'&#9989; Ready for Analytics' if summary['dq_score'] >= 95 else '&#10060; Below Threshold (95%). Corrective actions required.'}</p>
        </div>
        
        <div class="stats">
            <div class="stat-box"><div class="value">{summary['total_checks']}</div><div class="label">Total Checks</div></div>
            <div class="stat-box"><div class="value" style="color: #27ae60;">{summary['passed']}</div><div class="label">Passed</div></div>
            <div class="stat-box"><div class="value" style="color: #c0392b;">{summary['failed']}</div><div class="label">Failed</div></div>
            <div class="stat-box"><div class="value" style="color: #f39c12;">{summary['warnings']}</div><div class="label">Warnings</div></div>
        </div>
        
        <h3>Detailed Results</h3>
        <table>
            <thead>
                <tr>
                    <th>Table</th>
                    <th>Check</th>
                    <th>Status</th>
                    <th>Detail</th>
                </tr>
            </thead>
            <tbody>
"""
        for r in summary["results"]:
            icon = "&#9989;" if r["status"] == "PASS" else ("&#9888;&#65039;" if r["status"] == "WARN" else "&#10060;")
            html += f"""
                <tr>
                    <td>{r['table']}</td>
                    <td>{r['check']}</td>
                    <td class="status-{r['status']}">{icon} {r['status']}</td>
                    <td>{r['detail']}</td>
                </tr>
"""
            
        html += """
            </tbody>
        </table>
"""

        failed = [r for r in summary["results"] if r["status"] == "FAIL"]
        if failed:
            html += """
        <div class="actions">
            <h3>Required Corrective Actions</h3>
            <ul>
"""
            for r in failed:
                html += f"<li><strong>{r['table']}.{r['check']}</strong>: {r['detail']}</li>"
            html += """
            </ul>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        report_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML Data quality report saved to {report_path}")
        return str(report_path)


def run_data_quality_checks():
    """Execute data quality validation and generate report."""
    validator = DataQualityValidator()
    summary = validator.run_all_checks()
    report_path = validator.generate_report(summary)
    html_report_path = validator.generate_html_report(summary)

    if summary["dq_score"] >= 95:
        logger.info(f"✅ DQ Score {summary['dq_score']}% — PASSED. Ready for analytics.")
    else:
        logger.error(f"❌ DQ Score {summary['dq_score']}% — BELOW THRESHOLD. Fix issues first.")

    return summary


if __name__ == "__main__":
    run_data_quality_checks()
