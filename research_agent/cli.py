#!/usr/bin/env python3
"""
Research Agent CLI - lightweight background polling loop.

Periodically checks for new articles from configured sources.
Only triggers a full synthesis when enough new articles accumulate.

Default: Ollama (see config.py for model defaults)

Usage:
    python research_agent/cli.py                    # interactive one-shot
    python research_agent/cli.py --daemon           # background polling
    python research_agent/cli.py --daemon --interval 1800 --threshold 10
    python research_agent/cli.py --provider bedrock # use Bedrock instead
"""

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure workspace root is importable
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Set cache dir before importing tools
os.environ.setdefault(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "cache"),
)
# Suppress OpenTelemetry noise
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

# Use longer cache TTLs for the CLI daemon — avoid re-fetching
# content that was already downloaded in a recent poll cycle.
# These match the poll interval so cached data stays valid between cycles.
os.environ.setdefault("WEB_CACHE_TTL", "86400")    # 24h
os.environ.setdefault("HN_CACHE_TTL", "7200")      # 2h
os.environ.setdefault("ARXIV_CACHE_TTL", "43200")  # 12h
os.environ.setdefault("REDDIT_CACHE_TTL", "7200")  # 2h

from tools.web_scraper_tool import web_scraper_tool
from tools.hackernews_tool import hackernews_tool
from tools.arxiv_tool import arxiv_tool
from research_agent.config import DEFAULT_PROVIDER, default_model_for

# ---------------------------------------------------------------------------
# Seen-articles tracker (persisted to disk)
# ---------------------------------------------------------------------------

_SEEN_FILE = os.path.join(os.path.dirname(__file__), ".seen_articles.json")
_PENDING_FILE = os.path.join(os.path.dirname(__file__), ".pending_articles.json")


def _load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _article_id(url_or_title):
    return hashlib.sha256(url_or_title.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Polling: check sources for new content
# ---------------------------------------------------------------------------

def _call_tool(tool_fn, action, **params):
    """Call a tool and return the text content or None on error."""
    result = tool_fn({"toolUseId": "cli", "input": {"action": action, **params}})
    if result.get("status") == "success":
        return result["content"][0]["text"]
    return None


def _check_hackernews(seen):
    """Check HN top stories, return list of new articles."""
    new_articles = []
    text = _call_tool(hackernews_tool, "get_stories", category="top", limit=15)
    if not text:
        return new_articles
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- ["):
            continue
        # Extract title and url from markdown link
        try:
            title = line.split("[")[1].split("]")[0]
            url = line.split("(")[1].split(")")[0]
        except (IndexError, ValueError):
            continue
        aid = _article_id(url)
        if aid not in seen:
            new_articles.append({"id": aid, "source": "hackernews", "title": title, "url": url})
    return new_articles


def _check_arxiv(seen):
    """Check recent arxiv papers, return list of new ones."""
    new_articles = []
    text = _call_tool(arxiv_tool, "get_recent_papers",
                      categories=["cs.AI", "cs.LG", "cs.CL"], max_results=10)
    if not text:
        return new_articles
    # Parse paper blocks separated by ---
    for block in text.split("---"):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        title = url = ""
        for l in lines:
            if l.startswith("Title:"):
                title = l[6:].strip()
            elif l.startswith("URL:"):
                url = l[4:].strip()
        if title and url:
            aid = _article_id(url)
            if aid not in seen:
                new_articles.append({"id": aid, "source": "arxiv", "title": title, "url": url})
    return new_articles


def _check_blogs(seen):
    """Check engineering blogs for new posts. Pre-fetches article content."""
    new_articles = []
    blog_urls = [
        "https://www.anthropic.com/research",
        "https://ai.meta.com/blog/",
        "https://www.amazon.science/blog",
        "https://openai.com/research",
        "https://blog.research.google/",
    ]
    for blog_url in blog_urls:
        text = _call_tool(web_scraper_tool, "extract_links", url=blog_url)
        if not text:
            continue
        count = 0
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("- ["):
                continue
            try:
                title = line.split("[")[1].split("]")[0]
                url = line.split("(")[1].split(")")[0]
            except (IndexError, ValueError):
                continue
            if not url.startswith("http"):
                continue
            aid = _article_id(url)
            if aid not in seen:
                # Pre-fetch article content into cache so synthesis doesn't need to
                _call_tool(web_scraper_tool, "extract_article", url=url, max_chars=8000)
                new_articles.append({"id": aid, "source": blog_url, "title": title, "url": url})
                count += 1
                if count >= 5:
                    break
    return new_articles


# ---------------------------------------------------------------------------
# Synthesis: run the swarm when threshold is met
# ---------------------------------------------------------------------------

def _run_synthesis(pending_articles, provider, model_id):
    """Run the full research swarm and save output."""
    from research_agent.orchestrator import run_research

    sources = {}
    for a in pending_articles:
        sources.setdefault(a["source"], []).append(a["title"])

    source_summary = []
    for src, titles in sources.items():
        source_summary.append(f"{src}: {len(titles)} new articles")
        for t in titles[:5]:
            source_summary.append(f"  - {t}")

    task = (
        "Analyze the latest research and news across AI/ML sources. "
        f"There are {len(pending_articles)} new articles since last check:\n"
        + "\n".join(source_summary)
        + "\n\nGather details on these and produce cross-source insights."
    )

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{ts}] Running synthesis on {len(pending_articles)} new articles...")
    result = run_research(task, provider=provider, model_id=model_id)
    print(f"[{ts}] Synthesis complete.")
    print(result[:2000])
    if len(result) > 2000:
        print(f"... ({len(result)} chars total, see outputs/ for full text)")
    return result


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

def _poll_once(seen, pending, threshold, provider, model_id):
    """Run one poll cycle. Returns updated (seen, pending, synthesized)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_all = []

    print(f"[{ts}] Checking HN...")
    new_all.extend(_check_hackernews(seen))

    print(f"[{ts}] Checking arxiv...")
    new_all.extend(_check_arxiv(seen))

    print(f"[{ts}] Checking blogs...")
    new_all.extend(_check_blogs(seen))

    if new_all:
        print(f"[{ts}] Found {len(new_all)} new articles")
        for a in new_all:
            seen[a["id"]] = {"title": a["title"], "source": a["source"], "ts": ts}
            pending.append(a)
        _save_json(_SEEN_FILE, seen)
        _save_json(_PENDING_FILE, pending)
    else:
        print(f"[{ts}] No new articles")

    synthesized = False
    if len(pending) >= threshold:
        _run_synthesis(pending, provider, model_id)
        pending.clear()
        _save_json(_PENDING_FILE, pending)
        synthesized = True

    return seen, pending, synthesized


def _daemon_loop(interval, threshold, provider, model_id):
    """Run the polling loop until interrupted."""
    seen = _load_json(_SEEN_FILE)
    pending = _load_json(_PENDING_FILE)
    if isinstance(pending, dict):
        pending = list(pending.values()) if pending else []

    print(f"Daemon started: interval={interval}s, threshold={threshold}, "
          f"provider={provider}, model={model_id}")
    print(f"Tracking {len(seen)} seen articles, {len(pending)} pending")
    print("Press Ctrl+C to stop.\n")

    running = True

    def _stop(sig, frame):
        nonlocal running
        running = False
        print("\nStopping...")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        try:
            seen, pending, _ = _poll_once(seen, pending, threshold, provider, model_id)
        except Exception as e:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"[{ts}] Error during poll: {e}")
        if running:
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Interactive one-shot mode
# ---------------------------------------------------------------------------

def _interactive(provider, model_id):
    """Run a single research task interactively."""
    from research_agent.orchestrator import run_research

    print(f"Research Agent CLI (provider={provider}, model={model_id})")
    print("Type your research task, or 'quit' to exit.\n")

    while True:
        try:
            task = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not task or task.lower() in ("quit", "exit", "q"):
            break
        try:
            result = run_research(task, provider=provider, model_id=model_id)
            print(result)
        except Exception as e:
            print(f"Error: {e}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Research Agent CLI")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER,
                        choices=["ollama", "bedrock"],
                        help=f"Model provider (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--model", default=None,
                        help="Model ID (default: from config.py)")
    parser.add_argument("--daemon", action="store_true",
                        help="Run as background polling daemon")
    parser.add_argument("--interval", type=int, default=1800,
                        help="Poll interval in seconds (default: 1800 = 30min)")
    parser.add_argument("--threshold", type=int, default=5,
                        help="New article count to trigger synthesis (default: 5)")
    parser.add_argument("--poll-once", action="store_true",
                        help="Run a single poll cycle and exit")
    parser.add_argument("--cached-only", action="store_true",
                        help="Skip fetching, synthesize from cached articles only")

    args = parser.parse_args()

    model_id = args.model or default_model_for(args.provider)

    if args.daemon:
        _daemon_loop(args.interval, args.threshold, args.provider, model_id)
    elif args.poll_once:
        seen = _load_json(_SEEN_FILE)
        pending = _load_json(_PENDING_FILE)
        if isinstance(pending, dict):
            pending = list(pending.values()) if pending else []
        _poll_once(seen, pending, args.threshold, args.provider, model_id)
    elif args.cached_only:
        from research_agent.orchestrator import run_cached_only
        result = run_cached_only(provider=args.provider, model_id=model_id)
        print(result)
    else:
        _interactive(args.provider, model_id)


if __name__ == "__main__":
    main()
