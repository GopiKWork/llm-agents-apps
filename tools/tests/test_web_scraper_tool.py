"""Tests for web_scraper_tool."""

import pytest
from tools.web_scraper_tool import web_scraper_tool


def _call(action, **params):
    return web_scraper_tool({"toolUseId": "test-id", "input": {"action": action, **params}})


def test_extract_text():
    r = _call("extract_text", url="https://example.com")
    assert r["status"] == "success"
    assert "Example Domain" in r["content"][0]["text"]


def test_extract_article():
    r = _call("extract_article", url="https://example.com")
    assert r["status"] == "success"


def test_extract_links():
    r = _call("extract_links", url="https://example.com")
    assert r["status"] == "success"


def test_fetch_url():
    r = _call("fetch_url", url="https://example.com", max_chars=500)
    assert r["status"] == "success"
    assert "<html" in r["content"][0]["text"].lower()


def test_cached_response():
    r1 = _call("extract_text", url="https://example.com")
    r2 = _call("extract_text", url="https://example.com")
    assert r1["content"][0]["text"] == r2["content"][0]["text"]


def test_missing_action():
    r = web_scraper_tool({"toolUseId": "t", "input": {"url": "https://example.com"}})
    assert r["status"] == "error"


def test_missing_url():
    r = _call("extract_text")
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus", url="https://example.com")
    assert r["status"] == "error"


def test_bad_url():
    r = _call("extract_text", url="https://thisdomaindoesnotexist99999.com")
    assert r["status"] == "error"
