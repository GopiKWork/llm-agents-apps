"""Tests for reddit_tool."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from tools.reddit_tool import reddit_tool, _format_post


def _call(action, **params):
    return reddit_tool({"toolUseId": "test-id", "input": {"action": action, **params}})


def _mock_post(title="Test Post", score=200, num_comments=50, author="testuser",
               url="https://example.com", permalink="/r/test/comments/abc/test_post/",
               selftext=""):
    p = MagicMock()
    p.title = title
    p.score = score
    p.num_comments = num_comments
    p.author = author
    p.url = url
    p.permalink = permalink
    p.selftext = selftext
    return p


def _mock_comment(body="Great post", author_name="commenter", score=10):
    c = MagicMock()
    c.body = body
    c.score = score
    c.author = MagicMock()
    c.author.name = author_name
    return c


# --- Format helper ---

def test_format_post():
    post = _mock_post()
    result = _format_post(post)
    assert "Test Post" in result
    assert "200" in result
    assert "testuser" in result


def test_format_post_with_selftext():
    post = _mock_post(selftext="Some body text here")
    result = _format_post(post)
    assert "Some body text" in result


# --- search_subreddit ---

@patch("tools.reddit_tool._get_cached", return_value=None)
@patch("tools.reddit_tool._set_cached")
@patch("tools.reddit_tool._get_reddit")
def test_search_subreddit(mock_reddit, mock_set, mock_get):
    sub = MagicMock()
    sub.search.return_value = [_mock_post()]
    mock_reddit.return_value.subreddit.return_value = sub
    r = _call("search_subreddit", subreddit="MachineLearning", query="transformers")
    assert r["status"] == "success"
    assert "Test Post" in r["content"][0]["text"]


def test_search_subreddit_missing_subreddit():
    r = _call("search_subreddit", query="test")
    assert r["status"] == "error"


def test_search_subreddit_missing_query():
    r = _call("search_subreddit", subreddit="test")
    assert r["status"] == "error"


@patch("tools.reddit_tool._get_cached", return_value="cached reddit")
def test_search_subreddit_cached(mock_get):
    r = _call("search_subreddit", subreddit="test", query="test")
    assert r["status"] == "success"
    assert r["content"][0]["text"] == "cached reddit"


@patch("tools.reddit_tool._get_cached", return_value=None)
@patch("tools.reddit_tool._set_cached")
@patch("tools.reddit_tool._get_reddit")
def test_search_subreddit_no_results(mock_reddit, mock_set, mock_get):
    sub = MagicMock()
    sub.search.return_value = []
    mock_reddit.return_value.subreddit.return_value = sub
    r = _call("search_subreddit", subreddit="test", query="xyznotfound")
    assert r["status"] == "success"
    assert "No results" in r["content"][0]["text"]


# --- get_top_posts ---

@patch("tools.reddit_tool._get_cached", return_value=None)
@patch("tools.reddit_tool._set_cached")
@patch("tools.reddit_tool._get_reddit")
def test_get_top_posts(mock_reddit, mock_set, mock_get):
    sub = MagicMock()
    sub.top.return_value = [_mock_post(title="Top Post")]
    mock_reddit.return_value.subreddit.return_value = sub
    r = _call("get_top_posts", subreddit="MachineLearning")
    assert r["status"] == "success"
    assert "Top Post" in r["content"][0]["text"]


def test_get_top_posts_missing_subreddit():
    r = _call("get_top_posts")
    assert r["status"] == "error"


# --- get_post_comments ---

@patch("tools.reddit_tool._get_reddit")
def test_get_post_comments(mock_reddit):
    submission = MagicMock()
    submission.title = "Test Post"
    submission.comments = MagicMock()
    submission.comments.replace_more = MagicMock()
    submission.comments.__iter__ = MagicMock(return_value=iter([_mock_comment()]))
    mock_reddit.return_value.submission.return_value = submission
    r = _call("get_post_comments", post_id="abc123", limit=5)
    assert r["status"] == "success"
    assert "Great post" in r["content"][0]["text"]


def test_get_post_comments_missing_id():
    r = _call("get_post_comments")
    assert r["status"] == "error"


# --- Error cases ---

def test_missing_action():
    r = reddit_tool({"toolUseId": "t", "input": {}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"
