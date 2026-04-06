"""Tests for arxiv_tool."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from tools.arxiv_tool import arxiv_tool, _format_paper


def _call(action, **params):
    return arxiv_tool({"toolUseId": "test-id", "input": {"action": action, **params}})


def _mock_paper(title="Test Paper", authors=None, published=None,
                categories=None, summary="A test abstract.", entry_id="http://arxiv.org/abs/2301.00001",
                pdf_url="http://arxiv.org/pdf/2301.00001"):
    p = MagicMock()
    p.title = title
    a1 = MagicMock()
    a1.name = "Author One"
    p.authors = authors or [a1]
    p.published = published or datetime(2023, 1, 1)
    p.categories = categories or ["cs.AI"]
    p.summary = summary
    p.entry_id = entry_id
    p.pdf_url = pdf_url
    return p


# --- Format helper ---

def test_format_paper():
    paper = _mock_paper()
    result = _format_paper(paper)
    assert "Test Paper" in result
    assert "Author One" in result
    assert "cs.AI" in result


def test_format_paper_many_authors():
    authors = [MagicMock(name=f"Author {i}") for i in range(8)]
    for i, a in enumerate(authors):
        a.name = f"Author {i}"
    paper = _mock_paper(authors=authors)
    result = _format_paper(paper)
    assert "+3 more" in result


# --- search_papers ---

@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool._search")
def test_search_papers(mock_search, mock_set, mock_get):
    mock_search.return_value = [_mock_paper()]
    r = _call("search_papers", query="transformers")
    assert r["status"] == "success"
    assert "Test Paper" in r["content"][0]["text"]


def test_search_papers_missing_query():
    r = _call("search_papers")
    assert r["status"] == "error"


@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool._search", return_value=[])
def test_search_papers_no_results(mock_search, mock_set, mock_get):
    r = _call("search_papers", query="xyznotfound999")
    assert r["status"] == "success"
    assert "No papers" in r["content"][0]["text"]


@patch("tools.arxiv_tool._get_cached", return_value="cached papers")
def test_search_papers_cached(mock_get):
    r = _call("search_papers", query="transformers")
    assert r["status"] == "success"
    assert r["content"][0]["text"] == "cached papers"


# --- get_recent_papers ---

@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool._search")
def test_get_recent_papers(mock_search, mock_set, mock_get):
    mock_search.return_value = [_mock_paper(title="Recent Paper")]
    r = _call("get_recent_papers", categories=["cs.AI"])
    assert r["status"] == "success"
    assert "Recent Paper" in r["content"][0]["text"]


@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool._search", return_value=[])
def test_get_recent_papers_empty(mock_search, mock_set, mock_get):
    r = _call("get_recent_papers")
    assert r["status"] == "success"
    assert "No recent" in r["content"][0]["text"]


# --- get_paper_details ---

@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool.arxiv.Client")
@patch("tools.arxiv_tool.arxiv.Search")
def test_get_paper_details(mock_search_cls, mock_client_cls, mock_set, mock_get):
    mock_client = MagicMock()
    mock_client.results.return_value = [_mock_paper(title="Detail Paper")]
    mock_client_cls.return_value = mock_client
    r = _call("get_paper_details", paper_id="2301.00001")
    assert r["status"] == "success"
    assert "Detail Paper" in r["content"][0]["text"]


def test_get_paper_details_missing_id():
    r = _call("get_paper_details")
    assert r["status"] == "error"


@patch("tools.arxiv_tool._get_cached", return_value=None)
@patch("tools.arxiv_tool._set_cached")
@patch("tools.arxiv_tool.arxiv.Client")
@patch("tools.arxiv_tool.arxiv.Search")
def test_get_paper_details_not_found(mock_search_cls, mock_client_cls, mock_set, mock_get):
    mock_client = MagicMock()
    mock_client.results.return_value = []
    mock_client_cls.return_value = mock_client
    r = _call("get_paper_details", paper_id="0000.00000")
    assert r["status"] == "error"


# --- Error cases ---

def test_missing_action():
    r = arxiv_tool({"toolUseId": "t", "input": {}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"
