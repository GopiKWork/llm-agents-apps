#!/usr/bin/env python3
"""
Refresh the article cache with ONLY recent content.
Uses RSS feeds where available, extract_links as fallback.
Only fetches articles published in the last N days.
"""

import sys
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

warnings.filterwarnings("ignore")

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

os.environ.setdefault("RESEARCH_CACHE_DIR", os.path.join(os.path.dirname(__file__), "cache"))

from tools.web_scraper_tool import web_scraper_tool

MAX_AGE_DAYS = 14
CUTOFF = datetime.now() - timedelta(days=MAX_AGE_DAYS)
MAX_ARTICLES_PER_SOURCE = 3


def _call(action, **params):
    r = web_scraper_tool({"toolUseId": "refresh", "input": {"action": action, **params}})
    if r["status"] == "success":
        return r["content"][0]["text"]
    return None


def _parse_date(date_str):
    """Try to parse an RSS date string."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        pass
    # Try ISO format
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(date_str[:19], fmt)
        except Exception:
            continue
    return None


def _parse_rss_entries(text):
    """Parse the extract_rss output into (title, url, date) tuples."""
    entries = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("- ["):
            try:
                title = line.split("[")[1].split("]")[0]
                url = line.split("(")[1].split(")")[0]
                date_str = ""
                # Date might be in parentheses after the URL
                rest = line.split(")")
                if len(rest) > 1:
                    paren = rest[1].strip()
                    if paren.startswith("(") and paren.endswith(")"):
                        date_str = paren[1:-1]
                dt = _parse_date(date_str)
                entries.append((title, url, dt))
            except (IndexError, ValueError):
                pass
        i += 1
    return entries


# Sources with RSS feeds
RSS_SOURCES = [
    "https://magazine.sebastianraschka.com/feed",
    "https://cameronrwolfe.substack.com/feed",
    "https://www.latent.space/feed",
    "https://www.interconnects.ai/feed",
    "https://thegradient.pub/feed",
    "https://simonwillison.net/atom/everything/",
    "https://karpathy.github.io/feed.xml",
    "https://lilianweng.github.io/index.xml",
    "https://blog.research.google/feeds/posts/default",
    "https://www.amazon.science/index.rss",
    "https://engineering.fb.com/feed/",
]

# Sources without RSS — use extract_links
LINK_SOURCES = [
    "https://www.anthropic.com/research",
    "https://ai.meta.com/blog/",
    "https://openai.com/research",
    "https://deepmind.google/discover/blog/",
]


def refresh_rss_sources():
    """Fetch recent articles from RSS feeds."""
    total = 0
    for feed_url in RSS_SOURCES:
        name = feed_url.split("//")[1].split("/")[0]
        print(f"  RSS: {name}...", end=" ", flush=True)
        text = _call("extract_rss", url=feed_url, max_items=10)
        if not text or "No RSS entries" in text:
            print("no entries")
            continue
        entries = _parse_rss_entries(text)
        fetched = 0
        for title, url, dt in entries:
            if dt and dt < CUTOFF:
                continue
            if fetched >= MAX_ARTICLES_PER_SOURCE:
                break
            result = _call("extract_article", url=url, max_chars=10000)
            if result and len(result) > 200:
                fetched += 1
                total += 1
        print(f"{fetched} articles")
    return total


def refresh_link_sources():
    """Fetch recent articles from non-RSS sources using extract_links."""
    total = 0
    for blog_url in LINK_SOURCES:
        name = blog_url.split("//")[1].split("/")[0]
        print(f"  Links: {name}...", end=" ", flush=True)
        text = _call("extract_links", url=blog_url)
        if not text or "No links" in text:
            print("no links")
            continue
        fetched = 0
        for line in text.splitlines():
            if fetched >= MAX_ARTICLES_PER_SOURCE:
                break
            if not line.strip().startswith("- ["):
                continue
            try:
                url = line.split("(")[1].split(")")[0]
            except (IndexError, ValueError):
                continue
            if not url.startswith("http"):
                continue
            # Skip non-article links (about pages, tags, etc.)
            if any(skip in url for skip in ["/tag/", "/about", "/team", "/careers", "#"]):
                continue
            result = _call("extract_article", url=url, max_chars=10000)
            if result and len(result) > 500:
                fetched += 1
                total += 1
        print(f"{fetched} articles")
    return total


def main():
    print(f"Refreshing article cache (last {MAX_AGE_DAYS} days, max {MAX_ARTICLES_PER_SOURCE} per source)")
    print(f"Cutoff: {CUTOFF.strftime('%Y-%m-%d')}\n")

    rss_count = refresh_rss_sources()
    link_count = refresh_link_sources()

    articles_dir = os.path.join(os.environ["RESEARCH_CACHE_DIR"], "articles")
    total_files = len([f for f in os.listdir(articles_dir) if f.endswith(".md")]) if os.path.isdir(articles_dir) else 0

    print(f"\nDone: {rss_count} from RSS, {link_count} from links")
    print(f"Total articles in cache: {total_files}")


if __name__ == "__main__":
    main()
