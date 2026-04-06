"""
Reddit Tool - Strands module-based tool for searching Reddit via PRAW.
Requires env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET.
REDDIT_USER_AGENT is optional (defaults to 'ResearchAgent/1.0').
Results cached for 1 hour.
"""

import hashlib
import json
import os
import time
from typing import Any, Optional

try:
    import praw
except ImportError:
    raise ImportError("`praw` not installed. Install with `pip install praw`.")

# ============================================================================
# Cache
# ============================================================================

_CACHE_DIR = os.environ.get(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), ".reddit_cache"),
)
_CACHE_TTL = int(os.environ.get("REDDIT_CACHE_TTL", 3600))  # default 1h


def _cache_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _get_cached(key: str) -> Optional[str]:
    path = os.path.join(_CACHE_DIR, _cache_key(key) + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            entry = json.load(f)
        if time.time() - entry.get("ts", 0) > _CACHE_TTL:
            return None
        return entry.get("data")
    except Exception:
        return None


def _set_cached(key: str, data: str) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = os.path.join(_CACHE_DIR, _cache_key(key) + ".json")
    with open(path, "w") as f:
        json.dump({"ts": time.time(), "data": data}, f)


# ============================================================================
# Reddit client
# ============================================================================

_reddit: Optional[praw.Reddit] = None


def _get_reddit() -> praw.Reddit:
    global _reddit
    if _reddit is None:
        client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        user_agent = os.environ.get("REDDIT_USER_AGENT", "ResearchAgent/1.0")
        if not client_id or not client_secret:
            raise ValueError(
                "Reddit API credentials required. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET env vars. Create app at https://www.reddit.com/prefs/apps/"
            )
        _reddit = praw.Reddit(
            client_id=client_id, client_secret=client_secret, user_agent=user_agent,
        )
    return _reddit


def _format_post(post) -> str:
    lines = [
        f"Title: {post.title}",
        f"Score: {post.score} | Comments: {post.num_comments} | Author: {post.author}",
        f"URL: {post.url}",
        f"Reddit: https://reddit.com{post.permalink}",
    ]
    if post.selftext:
        lines.append(f"Text: {post.selftext[:500]}")
    return "\n".join(lines)


def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# Action handlers
# ============================================================================

def _search_subreddit(inp, tid):
    subreddit_name = inp.get("subreddit")
    query = inp.get("query")
    if not subreddit_name:
        return _error(tid, "Error: subreddit is required")
    if not query:
        return _error(tid, "Error: query is required")
    limit = min(inp.get("limit", 10), 25)
    time_filter = inp.get("time_filter", "week")
    cache_k = f"reddit_search_{subreddit_name}_{query}_{limit}_{time_filter}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    reddit = _get_reddit()
    posts = list(reddit.subreddit(subreddit_name).search(query, limit=limit, time_filter=time_filter, sort="relevance"))
    if not posts:
        return _ok(tid, f"No results in r/{subreddit_name} for '{query}'")
    formatted = [_format_post(p) for p in posts]
    result = f"r/{subreddit_name} search '{query}' ({len(formatted)} posts):\n\n" + "\n\n---\n\n".join(formatted)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _get_top_posts(inp, tid):
    subreddit_name = inp.get("subreddit")
    if not subreddit_name:
        return _error(tid, "Error: subreddit is required")
    limit = min(inp.get("limit", 10), 25)
    time_filter = inp.get("time_filter", "week")
    cache_k = f"reddit_top_{subreddit_name}_{limit}_{time_filter}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    reddit = _get_reddit()
    posts = list(reddit.subreddit(subreddit_name).top(limit=limit, time_filter=time_filter))
    if not posts:
        return _ok(tid, f"No top posts in r/{subreddit_name}")
    formatted = [_format_post(p) for p in posts]
    result = f"r/{subreddit_name} top posts ({time_filter}, {len(formatted)}):\n\n" + "\n\n---\n\n".join(formatted)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _get_post_comments(inp, tid):
    post_url = inp.get("post_url")
    post_id = inp.get("post_id")
    if not post_url and not post_id:
        return _error(tid, "Error: post_url or post_id is required")
    limit = min(inp.get("limit", 10), 20)
    reddit = _get_reddit()
    submission = reddit.submission(url=post_url) if post_url else reddit.submission(id=post_id)
    submission.comment_sort = "best"
    submission.comments.replace_more(limit=0)
    comments = list(submission.comments)[:limit]
    lines = [f"Comments on: {submission.title}", ""]
    for c in comments:
        author = c.author.name if c.author else "deleted"
        lines.append(f"[{author}] (score: {c.score}): {c.body[:400]}")
        lines.append("")
    return _ok(tid, "\n".join(lines))


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "reddit_tool",
    "description": (
        "Reddit tool for searching subreddits and fetching posts.\n"
        "Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.\n\n"
        "Actions:\n"
        "- search_subreddit: Search a subreddit by query\n"
        "- get_top_posts: Get top posts from a subreddit\n"
        "- get_post_comments: Get comments on a post\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["search_subreddit", "get_top_posts", "get_post_comments"],
                },
                "subreddit": {"type": "string", "description": "Subreddit name (without r/)"},
                "query": {"type": "string", "description": "Search query"},
                "post_url": {"type": "string", "description": "Full Reddit post URL"},
                "post_id": {"type": "string", "description": "Reddit post ID"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"},
                "time_filter": {"type": "string", "description": "Time: hour, day, week, month, year, all (default: week)"},
            },
            "required": ["action"],
        }
    },
}

_ACTIONS = {
    "search_subreddit": _search_subreddit,
    "get_top_posts": _get_top_posts,
    "get_post_comments": _get_post_comments,
}


def reddit_tool(tool: dict, **kwargs: Any) -> dict:
    """Reddit tool: search subreddits and fetch posts."""
    try:
        tid = tool.get("toolUseId", "default-id")
        inp = tool.get("input", {})
        action = inp.get("action")
        if not action:
            return _error(tid, "Error: action is required")
        handler = _ACTIONS.get(action)
        if not handler:
            return _error(tid, f"Error: Unknown action '{action}'")
        return handler(inp, tid)
    except Exception as e:
        return _error(tool.get("toolUseId", "default-id"), f"Error: {str(e)}")
