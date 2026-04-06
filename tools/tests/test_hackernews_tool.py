"""Tests for hackernews_tool."""

import pytest
from unittest.mock import patch, MagicMock
from tools.hackernews_tool import hackernews_tool, _format_story, _format_algolia_hit


def _call(action, **params):
    return hackernews_tool({"toolUseId": "test-id", "input": {"action": action, **params}})


# --- Mock data ---

def _mock_item(id=1, title="Test Story", url="https://example.com", score=100,
               by="testuser", descendants=50, text=None, kids=None):
    return {
        "id": id, "title": title, "url": url, "score": score,
        "by": by, "descendants": descendants, "text": text, "kids": kids or [],
    }


def _mock_algolia_hit(title="Test Hit", url="https://example.com", points=80,
                       author="hituser", num_comments=30, objectID="123"):
    return {
        "title": title, "url": url, "points": points,
        "author": author, "num_comments": num_comments, "objectID": objectID,
    }


# --- Format helpers ---

def test_format_story():
    item = _mock_item()
    result = _format_story(item)
    assert "Test Story" in result
    assert "100 pts" in result
    assert "testuser" in result


def test_format_algolia_hit():
    hit = _mock_algolia_hit()
    result = _format_algolia_hit(hit)
    assert "Test Hit" in result
    assert "80 pts" in result


# --- get_stories ---

@patch("tools.hackernews_tool._get_cached", return_value=None)
@patch("tools.hackernews_tool._set_cached")
@patch("tools.hackernews_tool._fetch_item")
@patch("tools.hackernews_tool._fetch_story_ids", return_value=[1, 2])
def test_get_stories(mock_ids, mock_item, mock_set, mock_get):
    mock_item.return_value = _mock_item()
    r = _call("get_stories", category="top", limit=2)
    assert r["status"] == "success"
    assert "Test Story" in r["content"][0]["text"]


@patch("tools.hackernews_tool._get_cached", return_value="cached result")
def test_get_stories_cached(mock_get):
    r = _call("get_stories", category="top")
    assert r["status"] == "success"
    assert r["content"][0]["text"] == "cached result"


def test_get_stories_invalid_category():
    r = _call("get_stories", category="invalid")
    assert r["status"] == "error"


# --- search_stories ---

@patch("tools.hackernews_tool._get_cached", return_value=None)
@patch("tools.hackernews_tool._set_cached")
@patch("tools.hackernews_tool._algolia_search")
def test_search_stories(mock_search, mock_set, mock_get):
    mock_search.return_value = [_mock_algolia_hit()]
    r = _call("search_stories", query="python")
    assert r["status"] == "success"
    assert "Test Hit" in r["content"][0]["text"]


def test_search_stories_missing_query():
    r = _call("search_stories")
    assert r["status"] == "error"


@patch("tools.hackernews_tool._get_cached", return_value=None)
@patch("tools.hackernews_tool._set_cached")
@patch("tools.hackernews_tool._algolia_search", return_value=[])
def test_search_stories_no_results(mock_search, mock_set, mock_get):
    r = _call("search_stories", query="xyznotfound999")
    assert r["status"] == "success"
    assert "No results" in r["content"][0]["text"]


# --- get_story_details ---

@patch("tools.hackernews_tool._fetch_item")
def test_get_story_details(mock_item):
    comment = _mock_item(id=10, by="commenter", text="Great post")
    story = _mock_item(text="Story body", kids=[10])
    mock_item.side_effect = [story, comment]
    r = _call("get_story_details", story_id=1)
    assert r["status"] == "success"
    assert "Test Story" in r["content"][0]["text"]
    assert "Great post" in r["content"][0]["text"]


def test_get_story_details_missing_id():
    r = _call("get_story_details")
    assert r["status"] == "error"


@patch("tools.hackernews_tool._fetch_item", return_value=None)
def test_get_story_details_not_found(mock_item):
    r = _call("get_story_details", story_id=999999)
    assert r["status"] == "error"


# --- Error cases ---

def test_missing_action():
    r = hackernews_tool({"toolUseId": "t", "input": {}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"
