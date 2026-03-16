"""Tests for excel_tool following strands_tools test conventions."""

import os
import pytest
import openpyxl
from tools.excel_tool import excel_tool

TEST_FILE = "/tmp/test_excel_tool.xlsx"


def _call(action, **params):
    return excel_tool({"toolUseId": "test-id", "input": {"action": action, **params}})


@pytest.fixture(autouse=True)
def create_test_file():
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sales"
    ws1.append(["Month", "Revenue", "Expenses"])
    ws1.append(["January", 50000, 30000])
    ws1.append(["February", 55000, 32000])
    ws2 = wb.create_sheet("Products")
    ws2.append(["Name", "Price"])
    ws2.append(["Widget", 25.99])
    wb.save(TEST_FILE)
    yield
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)


def test_list_sheets():
    r = _call("list_sheets", filepath=TEST_FILE)
    assert r["status"] == "success"
    assert "Sales" in r["content"][0]["text"]
    assert "Products" in r["content"][0]["text"]


def test_get_info():
    r = _call("get_info", filepath=TEST_FILE)
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "Sales" in text and "Products" in text


def test_read_file():
    r = _call("read_file", filepath=TEST_FILE, sheet_name="Sales")
    assert r["status"] == "success"
    assert "January" in r["content"][0]["text"]


def test_read_cell():
    r = _call("read_cell", filepath=TEST_FILE, sheet_name="Sales", cell_ref="B2")
    assert r["status"] == "success"
    assert "50000" in r["content"][0]["text"]


def test_read_range():
    r = _call("read_range", filepath=TEST_FILE, sheet_name="Sales", start_cell="A1", end_cell="C2")
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "Month" in text and "January" in text


def test_extract_images_none():
    r = _call("extract_images", filepath=TEST_FILE, sheet_name="Sales")
    assert r["status"] == "success"
    assert "No images" in r["content"][0]["text"]


def test_list_charts_none():
    r = _call("list_charts", filepath=TEST_FILE, sheet_name="Sales")
    assert r["status"] == "success"
    assert "No charts" in r["content"][0]["text"]


def test_missing_action():
    r = excel_tool({"toolUseId": "t", "input": {}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"


def test_missing_filepath():
    r = _call("list_sheets")
    assert r["status"] == "error"


def test_bad_sheet_name():
    r = _call("read_file", filepath=TEST_FILE, sheet_name="NoSuchSheet")
    assert r["status"] == "error"
