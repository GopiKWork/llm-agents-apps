"""
ArXiv Tool - Strands module-based tool for searching and fetching
academic papers from arxiv. Uses the arxiv Python library.
Results cached for 12 hours.
"""

import hashlib
import json
import os
import time
from typing import Any, List, Optional

try:
    import arxiv
except ImportError:
    raise ImportError("`arxiv` not installed. Install with `pip install arxiv`.")

# ============================================================================
# Cache
# ============================================================================

_CACHE_DIR = os.environ.get(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), ".arxiv_cache"),
)
_CACHE_TTL = int(os.environ.get("ARXIV_CACHE_TTL", 43200))  # default 12h


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
# Helpers
# ============================================================================

def _format_paper(result) -> str:
    title = result.title.replace("\n", " ")
    authors = ", ".join(a.name for a in result.authors[:5])
    if len(result.authors) > 5:
        authors += f" (+{len(result.authors) - 5} more)"
    published = result.published.strftime("%Y-%m-%d") if result.published else "N/A"
    categories = ", ".join(result.categories) if result.categories else "N/A"
    summary = result.summary.replace("\n", " ")[:500]
    return (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"Published: {published}\n"
        f"Categories: {categories}\n"
        f"URL: {result.entry_id}\n"
        f"PDF: {result.pdf_url}\n"
        f"Abstract: {summary}"
    )


def _search(query: str, max_results: int = 10, sort_by: str = "relevance",
            categories: Optional[List[str]] = None) -> List:
    sort_map = {
        "relevance": arxiv.SortCriterion.Relevance,
        "submitted": arxiv.SortCriterion.SubmittedDate,
        "updated": arxiv.SortCriterion.LastUpdatedDate,
    }
    criterion = sort_map.get(sort_by, arxiv.SortCriterion.Relevance)
    search_query = query
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        search_query = f"({query}) AND ({cat_filter})"
    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=criterion,
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client()
    return list(client.results(search))


def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# Action handlers
# ============================================================================

def _search_papers(inp, tid):
    query = inp.get("query")
    if not query:
        return _error(tid, "Error: query is required")
    max_results = min(inp.get("max_results", 10), 30)
    sort_by = inp.get("sort_by", "relevance")
    categories = inp.get("categories")
    cache_k = f"arxiv_search_{query}_{max_results}_{sort_by}_{categories}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    results = _search(query, max_results, sort_by, categories)
    if not results:
        return _ok(tid, f"No papers found for '{query}'")
    papers = [_format_paper(r) for r in results]
    result = f"ArXiv results for '{query}' ({len(papers)} papers):\n\n" + "\n\n---\n\n".join(papers)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _get_recent_papers(inp, tid):
    categories = inp.get("categories", ["cs.AI", "cs.LG", "cs.CL"])
    max_results = min(inp.get("max_results", 10), 30)
    cache_k = f"arxiv_recent_{'_'.join(categories)}_{max_results}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    results = _search(cat_query, max_results, "submitted")
    if not results:
        return _ok(tid, "No recent papers found")
    papers = [_format_paper(r) for r in results]
    result = f"Recent papers in {', '.join(categories)} ({len(papers)}):\n\n" + "\n\n---\n\n".join(papers)
    _set_cached(cache_k, result)
    return _ok(tid, result)


def _get_paper_details(inp, tid):
    paper_id = inp.get("paper_id")
    if not paper_id:
        return _error(tid, "Error: paper_id is required")
    cache_k = f"arxiv_paper_{paper_id}"
    cached = _get_cached(cache_k)
    if cached:
        return _ok(tid, cached)
    search = arxiv.Search(id_list=[paper_id])
    client = arxiv.Client()
    results = list(client.results(search))
    if not results:
        return _error(tid, f"Paper {paper_id} not found")
    result = _format_paper(results[0])
    _set_cached(cache_k, result)
    return _ok(tid, result)


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "arxiv_tool",
    "description": (
        "ArXiv paper search tool. Results cached for 12 hours.\n\n"
        "Actions:\n"
        "- search_papers: Search arxiv by query with optional category filter\n"
        "- get_recent_papers: Get most recent papers in given categories\n"
        "- get_paper_details: Get full details for a specific paper by ID\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["search_papers", "get_recent_papers", "get_paper_details"],
                },
                "query": {"type": "string", "description": "Search query"},
                "paper_id": {"type": "string", "description": "ArXiv paper ID (e.g. 2301.07041)"},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ArXiv categories e.g. cs.AI, cs.LG, cs.CL",
                },
                "max_results": {"type": "integer", "description": "Max results (default: 10, max: 30)"},
                "sort_by": {"type": "string", "description": "Sort: relevance, submitted, updated"},
            },
            "required": ["action"],
        }
    },
}

_ACTIONS = {
    "search_papers": _search_papers,
    "get_recent_papers": _get_recent_papers,
    "get_paper_details": _get_paper_details,
}


def arxiv_tool(tool: dict, **kwargs: Any) -> dict:
    """ArXiv tool: search and fetch academic papers."""
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
