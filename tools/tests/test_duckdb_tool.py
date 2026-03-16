"""Tests for duckdb_tool following strands_tools test conventions."""

import os
import pytest
import openpyxl
from tools.duckdb_tool import duckdb_tool

TEST_FILE = "/tmp/test_duckdb_tool.xlsx"
SESSION = "pytest_duckdb"


def _call(action, **params):
    return duckdb_tool({"toolUseId": "test-id", "input": {"action": action, "session_id": SESSION, **params}})


@pytest.fixture(autouse=True, scope="module")
def setup_data():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Name", "Value"])
    ws.append(["A", 10])
    ws.append(["B", 20])
    ws.append(["C", 30])
    wb.save(TEST_FILE)
    _call("load_excel", filepath=TEST_FILE)
    yield
    for f in [TEST_FILE, f"/tmp/duckdb_{SESSION}.duckdb"]:
        if os.path.exists(f):
            os.remove(f)


def test_load_excel():
    r = _call("load_excel", filepath=TEST_FILE, table_name="reload_test")
    assert r["status"] == "success"
    assert "Loaded" in r["content"][0]["text"]


def test_show_tables():
    r = _call("show_tables")
    assert r["status"] == "success"
    assert "test_duckdb_tool" in r["content"][0]["text"]


def test_describe_table():
    r = _call("describe_table", table_name="test_duckdb_tool")
    assert r["status"] == "success"
    assert "Name" in r["content"][0]["text"]


def test_run_query():
    r = _call("run_query", query="SELECT * FROM test_duckdb_tool")
    assert r["status"] == "success"
    assert "A" in r["content"][0]["text"]


def test_get_sample():
    r = _call("get_sample", table_name="test_duckdb_tool", n=2)
    assert r["status"] == "success"


def test_get_summary():
    r = _call("get_summary", table_name="test_duckdb_tool")
    assert r["status"] == "success"
    assert "Rows:" in r["content"][0]["text"]


def test_get_stats():
    r = _call("get_stats", table_name="test_duckdb_tool", column_name="Value")
    assert r["status"] == "success"
    assert "Min:" in r["content"][0]["text"]


def test_filter():
    r = _call("filter", table_name="test_duckdb_tool", conditions="Value > 15")
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "B" in text and "C" in text


def test_aggregate():
    r = _call("aggregate", table_name="test_duckdb_tool", group_by="Name", aggregations="SUM(Value) as total")
    assert r["status"] == "success"


def test_export_csv():
    out = "/tmp/test_duckdb_export.csv"
    r = _call("export_csv", table_name="test_duckdb_tool", output_path=out)
    assert r["status"] == "success"
    assert os.path.exists(out)
    os.remove(out)


def test_missing_session():
    r = duckdb_tool({"toolUseId": "t", "input": {"action": "show_tables"}})
    assert r["status"] == "error"


def test_missing_action():
    r = duckdb_tool({"toolUseId": "t", "input": {"session_id": SESSION}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"


def test_missing_query():
    r = _call("run_query")
    assert r["status"] == "error"


def test_missing_table_name():
    r = _call("describe_table")
    assert r["status"] == "error"
