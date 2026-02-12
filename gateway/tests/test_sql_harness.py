"""Tests for SQL test harness validator."""

from gateway.app.validators.sql_harness import validate_sql_harness


# ── Pass Cases ──────────────────────────────────────────────────────────────


def test_count_query_passes():
    """A correct COUNT(*) query passes the total_count test case."""
    result = validate_sql_harness(
        {"sql_query": "SELECT COUNT(*) FROM employees"},
        "employee_db_v1",
    )
    assert result["type"] == "sql_harness"
    assert result["harness_id"] == "employee_db_v1"
    # Only the total_count test case will pass (engineering_count and avg_salary won't)
    assert result["tests_passed"] >= 1
    assert result["tests_total"] == 3


def test_engineering_count_query():
    result = validate_sql_harness(
        {"sql_query": "SELECT COUNT(*) FROM employees WHERE department = 'Engineering'"},
        "employee_db_v1",
    )
    assert result["tests_passed"] >= 1


def test_avg_salary_query():
    result = validate_sql_harness(
        {"sql_query": "SELECT AVG(salary) FROM employees"},
        "employee_db_v1",
    )
    assert result["tests_passed"] >= 1


# ── Fail Cases ──────────────────────────────────────────────────────────────


def test_bad_sql_fails():
    """Invalid SQL returns failure with error details."""
    result = validate_sql_harness(
        {"sql_query": "SELECT * FROM nonexistent_table"},
        "employee_db_v1",
    )
    assert result["pass"] is False
    assert result["tests_passed"] == 0
    assert "SQL error" in result["details"]


def test_missing_sql_field_fails():
    """Missing sql_query field returns failure."""
    result = validate_sql_harness(
        {"other_field": "SELECT 1"},
        "employee_db_v1",
    )
    assert result["pass"] is False
    assert "Missing or invalid SQL" in result["details"]


def test_non_dict_response_fails():
    result = validate_sql_harness("not a dict", "employee_db_v1")
    assert result["pass"] is False
    assert "not a dict" in result["details"]


def test_unknown_harness_fails():
    result = validate_sql_harness({"sql_query": "SELECT 1"}, "nonexistent_harness")
    assert result["pass"] is False
    assert "Unknown harness_id" in result["details"]


# ── Determinism ──────────────────────────────────────────────────────────────


def test_deterministic():
    """Same input always produces same output."""
    data = {"sql_query": "SELECT COUNT(*) FROM employees"}
    r1 = validate_sql_harness(data, "employee_db_v1")
    r2 = validate_sql_harness(data, "employee_db_v1")
    assert r1 == r2


# ── Result Structure ─────────────────────────────────────────────────────────


def test_result_structure():
    result = validate_sql_harness(
        {"sql_query": "SELECT COUNT(*) FROM employees"},
        "employee_db_v1",
    )
    assert "type" in result
    assert "harness_id" in result
    assert "pass" in result
    assert "details" in result
    assert "tests_passed" in result
    assert "tests_total" in result


def test_empty_sql_fails():
    result = validate_sql_harness({"sql_query": ""}, "employee_db_v1")
    assert result["pass"] is False
