"""
Hacker News Tool - Strands module-based tool for fetching stories and
searching HN via the Firebase API and Algolia HN Search API.
No authentication required. Results cached for 1 hour.
"""

import hashlib
import json
import os
import time
from typing import Any, List, Optional

import httpx

# ============================================================================
# Cache
# ============================================================================

_CACHE_DIR = os.environ.get(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), ".hn_cache"),
)
_CACHE_TTL = int(os.environ.get("HN_CACHE_TTL", 3600))  # default 1h


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
# HN API helpers
# ============================================================================

HN_API = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_API = "https://hn.algolia.com/api/v1"
_TIMEOUT = 10


def _hn_get(path: str) -> Any:
    resp = httpx.get(f"{HN_API}/{path}", timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _algolia_search(query: str, tags: str = "story", hits: int = 10) -> List[dict]:
    params = {"query": query, "tags": tags, "hitsPerPage": hits}
    resp = httpx.get(f"{ALGOLIA_API}/search", params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def _fetch_item(item_id: int) -> dict:
    return _hn_get(f"item/{item_id}.json")


def _fetch_story_ids(category: str, limit: int = 20) -> List[int]:
    ids = _hn_get(f"{category}.json")
    return ids[:limit] if ids else []


def _format_story(item: dict) -> str:
    title = item.get("title", "N/A")
    url = item.get("url", "")
    score = item.get("score", 0)
    by = item.get("by", "unknown")
    comments = item.get("descendants", 0)
    hn_url = f"https://news.ycombinator.com/item?id={item.get('id', '')}"
    return f"- [{title}]({url or hn_url}) ({score} pts, {comments} comments, by {by})"


def _format_algolia_hit(hit: dict) -> str:
    title = hit.get("title", "N/A")
    url = hit.get("url", "")
    points = hit.get("points", 0)
    author = hit.get("author", "unknown")
    comments = hit.get("num_comments", 0)
    oid = hit.get("objectID", "")
    hn_url = f"https://news.ycombinator.com/item?id={oid}"
    return f"- [{title}]({url or hn_url}) ({points} pts, {comments} comments, by {author})"


def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# Action handlers
# ============================================================================

def _get_stories(inp, tid):
    category = inp.get("category", "top")
    valid = {"top": "topstories", "new": "newstories", "best": "beststories"}
    endpoint = valid.get(category)
    if not endpoint:
        return _error(tid, f"Error: category must be one of {list(valid.keys())}")
    limit = min(inp.get("limit", 15), 30)
    cache_k = f"hn_{category}_{limit}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    ids = _fetch_story_ids(endpoint, limit)
    stories = []
    for sid in ids:
        try:
            item = _fetch_item(sid)
            if item:
                stories.append(_format_story(item))
        except Exception:
            continue
    result = f"Hacker News {category} stories ({len(stories)}):\n\n" + "\n".join(stories)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _search_stories(inp, tid):
    query = inp.get("query")
    if not query:
        return _error(tid, "Error: query is required")
    limit = min(inp.get("limit", 10), 30)
    cache_k = f"hn_search_{query}_{limit}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    hits = _algolia_search(query, hits=limit)
    if not hits:
        return _ok(tid, f"No results found for '{query}'")
    lines = [_format_algolia_hit(h) for h in hits]
    result = f"HN search results for '{query}' ({len(lines)}):\n\n" + "\n".join(lines)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _get_story_details(inp, tid):
    story_id = inp.get("story_id")
    if not story_id:
        return _error(tid, "Error: story_id is required")
    item = _fetch_item(int(story_id))
    if not item:
        return _error(tid, f"Error: story {story_id} not found")
    lines = [_format_story(item), ""]
    if item.get("text"):
        lines.append(f"Text: {item['text'][:3000]}")
        lines.append("")
    kid_ids = item.get("kids", [])[:10]
    if kid_ids:
        lines.append("Top comments:")
        for cid in kid_ids:
            try:
                comment = _fetch_item(cid)
                if comment and comment.get("text"):
                    by = comment.get("by", "anon")
                    lines.append(f"  [{by}]: {comment['text'][:500]}")
            except Exception:
                continue
    return _ok(tid, "\n".join(lines))


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "hackernews_tool",
    "description": (
        "Hacker News tool for fetching stories and searching HN.\n"
        "No authentication required. Results cached for 1 hour.\n\n"
        "Actions:\n"
        "- get_stories: Get top/new/best stories from HN\n"
        "- search_stories: Search HN via Algolia\n"
        "- get_story_details: Get story details and top comments\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["get_stories", "search_stories", "get_story_details"],
                },
                "category": {"type": "string", "description": "Story category: top, new, best (default: top)"},
                "query": {"type": "string", "description": "Search query (for search_stories)"},
                "story_id": {"type": "integer", "description": "HN story ID (for get_story_details)"},
                "limit": {"type": "integer", "description": "Max results (default: 15, max: 30)"},
            },
            "required": ["action"],
        }
    },
}

_ACTIONS = {
    "get_stories": _get_stories,
    "search_stories": _search_stories,
    "get_story_details": _get_story_details,
}


def hackernews_tool(tool: dict, **kwargs: Any) -> dict:
    """Hacker News tool: fetch stories and search HN."""
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
