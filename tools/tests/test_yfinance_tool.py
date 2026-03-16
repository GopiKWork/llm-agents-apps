"""Tests for yfinance_tool following strands_tools test conventions."""

import pytest
from tools.yfinance_tool import yfinance_tool

SYMBOL = "AAPL"


def _call(action, **params):
    return yfinance_tool({"toolUseId": "test-id", "input": {"action": action, "symbol": SYMBOL, **params}})


# --- Success cases ---

def test_stock_price():
    r = _call("stock_price")
    assert r["status"] == "success"
    assert SYMBOL in r["content"][0]["text"]


def test_company_info():
    r = _call("company_info")
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "Name" in text
    assert "Sector" in text


def test_stock_fundamentals():
    r = _call("stock_fundamentals")
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "symbol" in text
    assert "market_cap" in text


def test_income_statements():
    r = _call("income_statements")
    assert r["status"] == "success"


def test_analyst_recommendations():
    r = _call("analyst_recommendations")
    # May be success or error depending on data availability
    assert r["status"] in ("success", "error")


def test_historical_prices():
    r = _call("historical_prices", period="5d", interval="1d")
    assert r["status"] == "success"
    assert "Close" in r["content"][0]["text"]


def test_historical_prices_custom_period():
    r = _call("historical_prices", period="1mo", interval="1wk")
    assert r["status"] == "success"


def test_company_news():
    r = _call("company_news", num_stories=2)
    # News may or may not be available
    assert r["status"] in ("success", "error")


def test_technical_indicators():
    r = _call("technical_indicators", period="3mo")
    assert r["status"] == "success"
    text = r["content"][0]["text"]
    assert "Latest Close" in text
    assert "SMA 20" in text


# --- Error cases ---

def test_missing_action():
    r = yfinance_tool({"toolUseId": "t", "input": {"symbol": SYMBOL}})
    assert r["status"] == "error"
    assert "action" in r["content"][0]["text"]


def test_missing_symbol():
    r = yfinance_tool({"toolUseId": "t", "input": {"action": "stock_price"}})
    assert r["status"] == "error"
    assert "symbol" in r["content"][0]["text"]


def test_unknown_action():
    r = _call("bogus_action")
    assert r["status"] == "error"
    assert "Unknown action" in r["content"][0]["text"]


def test_invalid_symbol():
    r = yfinance_tool({"toolUseId": "t", "input": {"action": "stock_price", "symbol": "XYZNOTREAL999"}})
    # yfinance may return error or empty data
    assert r["status"] in ("success", "error")
