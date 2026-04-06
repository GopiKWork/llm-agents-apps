"""
Web Scraper Tool - Strands module-based tool for fetching and extracting
content from web pages. Uses httpx + beautifulsoup4.
Results are cached locally for 24h to avoid redundant fetches.
"""

import hashlib
import json
import os
import time
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

try:
    from markdownify import markdownify as md
except ImportError:
    md = None

# ============================================================================
# Local cache
# ============================================================================

_CACHE_DIR = os.environ.get(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), ".web_cache"),
)
_CACHE_TTL = int(os.environ.get("WEB_CACHE_TTL", 86400))  # default 24h


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _get_cached(url: str) -> Optional[str]:
    path = os.path.join(_CACHE_DIR, _cache_key(url) + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            entry = json.load(f)
        if time.time() - entry.get("ts", 0) > _CACHE_TTL:
            return None
        return entry.get("text")
    except Exception:
        return None


def _set_cached(url: str, text: str) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = os.path.join(_CACHE_DIR, _cache_key(url) + ".json")
    with open(path, "w") as f:
        json.dump({"url": url, "ts": time.time(), "text": text[:50000]}, f)


def _save_markdown(url: str, html: str) -> None:
    """Save a markdown version of the page to cache/articles/ for direct reading."""
    articles_dir = os.path.join(_CACHE_DIR, "articles")
    os.makedirs(articles_dir, exist_ok=True)
    # Convert HTML to markdown
    if md:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup
        content = md(str(article), heading_style="ATX", strip=["img"])
    else:
        content = _extract_text(html, 15000)
    # Clean up excessive whitespace
    lines = [l.rstrip() for l in content.splitlines()]
    cleaned = "\n".join(l for i, l in enumerate(lines)
                        if l.strip() or (i > 0 and lines[i-1].strip()))
    # Save with URL as header
    key = _cache_key(url)[:12]
    slug = url.split("//")[-1].replace("/", "_").replace("?", "_")[:80]
    fname = f"{slug}_{key}.md"
    path = os.path.join(articles_dir, fname)
    with open(path, "w") as f:
        f.write(f"<!-- source: {url} -->\n\n")
        f.write(cleaned[:20000])
    return path


# ============================================================================
# Scraping helpers
# ============================================================================

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ResearchBot/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch(url: str, timeout: int = 15) -> str:
    cached = _get_cached(url)
    if cached is not None:
        return cached
    resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    text = resp.text
    _set_cached(url, text)
    # Also save a markdown version for direct reading
    try:
        _save_markdown(url, text)
    except Exception:
        pass
    return text


def _extract_text(html: str, max_chars: int = 15000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)[:max_chars]


def _extract_links(html: str, base_url: str = "") -> list:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(strip=True)
        if href.startswith("/") and base_url:
            href = base_url.rstrip("/") + href
        if href.startswith("http") and title:
            links.append({"url": href, "title": title[:200]})
    return links[:50]


def _extract_article(html: str, max_chars: int = 15000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("main") or soup.find("div", class_="post-content")
    if article:
        for tag in article(["script", "style", "nav"]):
            tag.decompose()
        text = article.get_text(separator="\n", strip=True)
    else:
        text = _extract_text(html, max_chars)
    return text[:max_chars]


def _parse_rss(xml_text: str, max_items: int = 20) -> list:
    """Parse RSS/Atom feed XML and return list of entries."""
    try:
        soup = BeautifulSoup(xml_text, "xml")
    except Exception:
        soup = BeautifulSoup(xml_text, "html.parser")
    entries = []
    # RSS 2.0 format
    for item in soup.find_all("item")[:max_items]:
        title = item.find("title")
        link = item.find("link")
        pub_date = item.find("pubDate") or item.find("pubdate")
        desc = item.find("description")
        entry = {
            "title": title.get_text(strip=True) if title else "",
            "url": link.get_text(strip=True) if link else "",
            "date": pub_date.get_text(strip=True) if pub_date else "",
            "summary": "",
        }
        if desc:
            desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
            entry["summary"] = desc_soup.get_text(separator=" ", strip=True)[:500]
        if entry["title"] and entry["url"]:
            entries.append(entry)
    # Atom format fallback
    if not entries:
        for item in soup.find_all("entry")[:max_items]:
            title = item.find("title")
            link = item.find("link")
            pub_date = item.find("published") or item.find("updated")
            summary = item.find("summary") or item.find("content")
            entry = {
                "title": title.get_text(strip=True) if title else "",
                "url": link.get("href", "") if link else "",
                "date": pub_date.get_text(strip=True) if pub_date else "",
                "summary": "",
            }
            if summary:
                s_soup = BeautifulSoup(summary.get_text(), "html.parser")
                entry["summary"] = s_soup.get_text(separator=" ", strip=True)[:500]
            if entry["title"] and entry["url"]:
                entries.append(entry)
    return entries


def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "web_scraper_tool",
    "description": (
        "Web scraper tool for fetching and extracting content from URLs.\n"
        "Results are cached locally for 24h to avoid redundant fetches.\n\n"
        "Actions:\n"
        "- fetch_url: Fetch raw HTML from a URL\n"
        "- extract_text: Fetch URL and extract clean text content\n"
        "- extract_article: Fetch URL and extract article/main content\n"
        "- extract_links: Fetch URL and extract all links\n"
        "- extract_rss: Fetch an RSS/Atom feed and return article entries with titles, URLs, dates, summaries. "
        "Works with Substack (append /feed to the URL), WordPress, and any standard RSS/Atom feed.\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["fetch_url", "extract_text", "extract_article", "extract_links", "extract_rss"],
                },
                "url": {"type": "string", "description": "URL to fetch (for RSS, use the feed URL e.g. https://example.substack.com/feed)"},
                "max_chars": {"type": "integer", "description": "Max characters to return (default: 15000)"},
                "max_items": {"type": "integer", "description": "Max RSS items to return (default: 20)"},
            },
            "required": ["action", "url"],
        }
    },
}


def _act_fetch_url(inp, tid):
    html = _fetch(inp["url"])
    return _ok(tid, html[:inp.get("max_chars", 15000)])


def _act_extract_text(inp, tid):
    html = _fetch(inp["url"])
    return _ok(tid, _extract_text(html, inp.get("max_chars", 15000)))


def _act_extract_article(inp, tid):
    html = _fetch(inp["url"])
    return _ok(tid, _extract_article(html, inp.get("max_chars", 15000)))


def _act_extract_links(inp, tid):
    html = _fetch(inp["url"])
    links = _extract_links(html, inp["url"])
    lines = [f"- [{l['title']}]({l['url']})" for l in links]
    return _ok(tid, "\n".join(lines) if lines else "No links found")


def _act_extract_rss(inp, tid):
    url = inp["url"]
    # Auto-append /feed for Substack-like URLs if not already a feed URL
    if not url.rstrip("/").endswith("/feed"):
        # Try appending /feed for known platforms
        if "substack.com" in url or any(s in url for s in [
            "magazine.sebastianraschka.com", "cameronrwolfe.substack",
            "thegradient.pub", "interconnects.ai", "latent.space",
            "semianalysis.com",
        ]):
            url = url.rstrip("/") + "/feed"
    # RSS feeds can be large — fetch without the 50k cache truncation
    cached = _get_cached(url)
    if cached is not None:
        xml_text = cached
    else:
        resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        xml_text = resp.text
        # Cache a larger portion for RSS feeds (up to 500k)
        os.makedirs(_CACHE_DIR, exist_ok=True)
        path = os.path.join(_CACHE_DIR, _cache_key(url) + ".json")
        with open(path, "w") as f:
            json.dump({"url": url, "ts": time.time(), "text": xml_text[:500000]}, f)
    max_items = inp.get("max_items", 20)
    entries = _parse_rss(xml_text, max_items)
    if not entries:
        return _ok(tid, "No RSS entries found. The URL may not be a valid RSS/Atom feed.")
    lines = []
    for e in entries:
        line = f"- [{e['title']}]({e['url']})"
        if e["date"]:
            line += f" ({e['date']})"
        lines.append(line)
        if e["summary"]:
            lines.append(f"  {e['summary'][:200]}")
    return _ok(tid, "\n".join(lines))


_ACTIONS = {
    "fetch_url": _act_fetch_url,
    "extract_text": _act_extract_text,
    "extract_article": _act_extract_article,
    "extract_links": _act_extract_links,
    "extract_rss": _act_extract_rss,
}


def web_scraper_tool(tool: dict, **kwargs: Any) -> dict:
    """Web scraper tool: fetch and extract content from URLs."""
    try:
        tid = tool.get("toolUseId", "default-id")
        inp = tool.get("input", {})
        action = inp.get("action")
        if not action:
            return _error(tid, "Error: action is required")
        url = inp.get("url")
        if not url:
            return _error(tid, "Error: url is required")
        handler = _ACTIONS.get(action)
        if not handler:
            return _error(tid, f"Error: Unknown action '{action}'")
        return handler(inp, tid)
    except httpx.HTTPStatusError as e:
        return _error(tool.get("toolUseId", "default-id"), f"HTTP error {e.response.status_code}: {e.request.url}")
    except Exception as e:
        return _error(tool.get("toolUseId", "default-id"), f"Error: {str(e)}")
