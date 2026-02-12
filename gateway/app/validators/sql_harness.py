"""SQL test harness validator for seller-generated SQL.

Validates that SQL queries produced by the seller run correctly
against predefined sample databases and produce expected results.

Usage:
    result = validate_sql_harness(
        response_data={"sql_query": "SELECT COUNT(*) FROM employees"},
        harness_id="employee_db_v1",
    )
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

HARNESS_DIR = Path(__file__).parent / "harnesses"

_harness_cache: dict[str, dict] = {}


def _load_harness(harness_id: str) -> dict:
    """Load a test harness definition by ID."""
    if harness_id in _harness_cache:
        return _harness_cache[harness_id]

    harness_path = HARNESS_DIR / f"{harness_id}.json"
    if not harness_path.exists():
        raise ValueError(f"Unknown harness_id: {harness_id}")

    with open(harness_path) as f:
        harness = json.load(f)

    _harness_cache[harness_id] = harness
    return harness


def _setup_db(setup_sql: list[str]) -> sqlite3.Connection:
    """Create an in-memory SQLite DB and run setup statements."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    for stmt in setup_sql:
        cursor.execute(stmt)
    conn.commit()
    return conn


def _run_query(conn: sqlite3.Connection, sql: str) -> list[list]:
    """Execute a SQL query and return results as list of lists."""
    cursor = conn.cursor()
    cursor.execute(sql)
    return [list(row) for row in cursor.fetchall()]


def _compare_results(actual: list[list], expected: list[list], ordered: bool) -> bool:
    """Compare actual vs expected query results."""
    if not ordered:
        return sorted([tuple(r) for r in actual]) == sorted([tuple(r) for r in expected])
    return actual == expected


def validate_sql_harness(
    response_data: Any,
    harness_id: str,
) -> dict[str, Any]:
    """Validate seller-generated SQL against a test harness.

    The response_data should contain a SQL query in the field specified
    by the harness definition (default: "sql_query").

    Returns:
        {
            "type": "sql_harness",
            "harness_id": str,
            "pass": bool,
            "details": str | None,
            "tests_passed": int,
            "tests_total": int,
        }
    """
    try:
        harness = _load_harness(harness_id)
    except ValueError as e:
        return {
            "type": "sql_harness",
            "harness_id": harness_id,
            "pass": False,
            "details": str(e),
            "tests_passed": 0,
            "tests_total": 0,
        }

    # Extract SQL from response
    sql_field = harness.get("sql_field", "sql_query")
    if not isinstance(response_data, dict):
        return {
            "type": "sql_harness",
            "harness_id": harness_id,
            "pass": False,
            "details": "Response is not a dict",
            "tests_passed": 0,
            "tests_total": len(harness.get("test_cases", [])),
        }

    seller_sql = response_data.get(sql_field)
    if not seller_sql or not isinstance(seller_sql, str):
        return {
            "type": "sql_harness",
            "harness_id": harness_id,
            "pass": False,
            "details": f"Missing or invalid SQL in field '{sql_field}'",
            "tests_passed": 0,
            "tests_total": len(harness.get("test_cases", [])),
        }

    test_cases = harness.get("test_cases", [])
    if not test_cases:
        return {
            "type": "sql_harness",
            "harness_id": harness_id,
            "pass": True,
            "details": "No test cases defined",
            "tests_passed": 0,
            "tests_total": 0,
        }

    # Run tests
    setup_sql = harness.get("setup_sql", [])
    tests_passed = 0
    failures: list[str] = []

    for i, tc in enumerate(test_cases):
        tc_name = tc.get("name", f"test_{i}")
        expected = tc.get("expected_rows", [])
        ordered = tc.get("ordered", False)

        try:
            conn = _setup_db(setup_sql)
            actual = _run_query(conn, seller_sql)
            conn.close()

            if _compare_results(actual, expected, ordered):
                tests_passed += 1
            else:
                failures.append(
                    f"{tc_name}: expected {expected}, got {actual}"
                )
        except Exception as e:
            failures.append(f"{tc_name}: SQL error: {e}")

    all_pass = tests_passed == len(test_cases)
    return {
        "type": "sql_harness",
        "harness_id": harness_id,
        "pass": all_pass,
        "details": "; ".join(failures) if failures else None,
        "tests_passed": tests_passed,
        "tests_total": len(test_cases),
    }
