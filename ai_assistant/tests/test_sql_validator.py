"""
FinSight 360 AI Analytics Assistant
SQL Validator Security Tests

Tests that the SQL validator correctly:
  - Allows valid SELECT queries
  - Blocks dangerous SQL (DROP, DELETE, UPDATE, INSERT, ALTER, etc.)
  - Blocks SQL injection patterns
  - Rejects unauthorized tables
  - Auto-appends LIMIT when missing
  - Caps excessive LIMIT values
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from ai_assistant.sql_validator import validate_sql, MAX_RESULT_ROWS, DEFAULT_LIMIT


class TestAllowedQueries:
    """Test that valid SELECT queries pass validation."""

    def test_simple_select(self):
        sql = "SELECT * FROM customer360.dim_customer LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"

    def test_select_with_where(self):
        sql = "SELECT customer_id, age FROM customer360.dim_customer WHERE age > 30 LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"

    def test_select_with_join(self):
        sql = (
            "SELECT dc.customer_id, cp.predicted_clv_12m "
            "FROM customer360.dim_customer dc "
            "JOIN customer360.clv_predictions cp ON dc.customer_id = cp.customer_id "
            "LIMIT 10"
        )
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"

    def test_select_with_group_by(self):
        sql = (
            "SELECT behavioral_segment, COUNT(*) FROM customer360.ml_customer_segments "
            "GROUP BY behavioral_segment LIMIT 10"
        )
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"

    def test_with_cte(self):
        sql = (
            "WITH high_risk AS ("
            "  SELECT customer_id FROM customer360.ml_churn_predictions "
            "  WHERE churn_risk_tier = 'High Risk'"
            ") SELECT COUNT(*) FROM high_risk LIMIT 10"
        )
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"

    def test_select_with_aggregate(self):
        sql = "SELECT AVG(churn_probability) FROM customer360.ml_churn_predictions LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid, f"Should be valid: {result.error}"


class TestBlockedStatements:
    """Test that dangerous SQL statements are rejected."""

    def test_drop_table(self):
        sql = "DROP TABLE customer360.dim_customer"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "DROP" in result.error

    def test_delete(self):
        sql = "DELETE FROM customer360.dim_customer WHERE customer_id = 1"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "DELETE" in result.error

    def test_update(self):
        sql = "UPDATE customer360.dim_customer SET age = 25 WHERE customer_id = 1"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "UPDATE" in result.error

    def test_insert(self):
        sql = "INSERT INTO customer360.dim_customer (customer_id) VALUES (99999)"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "INSERT" in result.error

    def test_alter(self):
        sql = "ALTER TABLE customer360.dim_customer ADD COLUMN hacked TEXT"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "ALTER" in result.error

    def test_truncate(self):
        sql = "TRUNCATE customer360.dim_customer"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "TRUNCATE" in result.error

    def test_create_table(self):
        sql = "CREATE TABLE customer360.evil_table (id INT)"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "CREATE" in result.error

    def test_grant(self):
        sql = "GRANT ALL ON customer360.dim_customer TO evil_user"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "GRANT" in result.error

    def test_revoke(self):
        sql = "REVOKE SELECT ON customer360.dim_customer FROM postgres"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "REVOKE" in result.error


class TestInjectionPrevention:
    """Test that SQL injection patterns are blocked."""

    def test_comment_injection(self):
        sql = "SELECT * FROM customer360.dim_customer -- DROP TABLE dim_customer"
        result = validate_sql(sql)
        # Should pass but with comment stripped
        assert result.is_valid
        assert "DROP" not in result.sanitized_sql

    def test_block_comment_injection(self):
        sql = "SELECT * FROM customer360.dim_customer /* DROP TABLE dim_customer */"
        result = validate_sql(sql)
        assert result.is_valid
        assert "DROP" not in result.sanitized_sql

    def test_multi_statement(self):
        sql = "SELECT 1; DROP TABLE customer360.dim_customer"
        result = validate_sql(sql)
        assert not result.is_valid

    def test_select_into(self):
        """SELECT followed by dangerous keyword in the payload."""
        sql = "SELECT * FROM customer360.dim_customer; DELETE FROM customer360.dim_customer"
        result = validate_sql(sql)
        assert not result.is_valid

    def test_empty_query(self):
        result = validate_sql("")
        assert not result.is_valid

    def test_only_comments(self):
        sql = "-- just a comment\n/* another comment */"
        result = validate_sql(sql)
        assert not result.is_valid


class TestUnauthorizedTables:
    """Test that queries to unauthorized tables are rejected."""

    def test_pg_catalog(self):
        sql = "SELECT * FROM pg_catalog.pg_tables LIMIT 10"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "not allowed" in result.error.lower()

    def test_information_schema(self):
        sql = "SELECT * FROM information_schema.tables LIMIT 10"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "not allowed" in result.error.lower()

    def test_unknown_table(self):
        sql = "SELECT * FROM customer360.secret_table LIMIT 10"
        result = validate_sql(sql)
        assert not result.is_valid
        assert "not in the allowed" in result.error.lower()


class TestLimitEnforcement:
    """Test that LIMIT is enforced on queries."""

    def test_auto_append_limit(self):
        sql = "SELECT * FROM customer360.dim_customer"
        result = validate_sql(sql)
        assert result.is_valid
        assert f"LIMIT {DEFAULT_LIMIT}" in result.sanitized_sql
        assert result.warnings is not None
        assert any("LIMIT" in w for w in result.warnings)

    def test_existing_limit_preserved(self):
        sql = "SELECT * FROM customer360.dim_customer LIMIT 5"
        result = validate_sql(sql)
        assert result.is_valid
        assert "LIMIT 5" in result.sanitized_sql

    def test_excessive_limit_capped(self):
        sql = f"SELECT * FROM customer360.dim_customer LIMIT {MAX_RESULT_ROWS + 1000}"
        result = validate_sql(sql)
        assert result.is_valid
        assert f"LIMIT {MAX_RESULT_ROWS}" in result.sanitized_sql


class TestEdgeCases:
    """Test edge cases."""

    def test_whitespace_only(self):
        result = validate_sql("   \n\t  ")
        assert not result.is_valid

    def test_none_input(self):
        result = validate_sql(None)
        assert not result.is_valid

    def test_very_long_query(self):
        sql = "SELECT " + ", ".join([f"col_{i}" for i in range(50)]) + " FROM customer360.dim_customer LIMIT 10"
        result = validate_sql(sql)
        assert result.is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
