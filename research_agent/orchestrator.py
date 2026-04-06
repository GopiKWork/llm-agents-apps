"""
Research Orchestrator - runs agents sequentially as a pipeline.
Web researcher -> Arxiv researcher -> Insight agent.
Each agent's output is piped as input to the next.
Saves output to research_agent/outputs/ and ingests previous outputs
into faiss before each run for deduplication.
"""

import glob
import os
from datetime import datetime

from research_agent.web_researcher import create_web_researcher
from research_agent.arxiv_researcher import create_arxiv_researcher
from research_agent.insight_agent import create_insight_agent, SESSION_ID
from research_agent.config import default_model_for, DEFAULT_PROVIDER

_OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")

# Default cache location for all tools when run via research_agent
os.environ.setdefault(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "cache"),
)


def _build_model(provider: str = None, model_id: str = None):
    """Build model based on provider selection."""
    provider = provider or DEFAULT_PROVIDER
    model_id = model_id or default_model_for(provider)
    if provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(
            host="http://localhost:11434",
            model_id=model_id,
        )
    from strands.models import BedrockModel
    return BedrockModel(model_id=model_id)


def _ingest_previous_outputs():
    """Load all previous output files into faiss for dedup comparison."""
    from tools.faiss_tool import faiss_tool as _faiss

    if not os.path.isdir(_OUTPUTS_DIR):
        return 0

    files = sorted(glob.glob(os.path.join(_OUTPUTS_DIR, "*.md")))
    if not files:
        return 0

    ingested = 0
    for fpath in files:
        result = _faiss({
            "toolUseId": "ingest-prev",
            "input": {
                "action": "store_file",
                "session_id": SESSION_ID,
                "filepath": fpath,
            },
        })
        if result.get("status") == "success":
            ingested += 1
    return ingested


def _save_output(text: str) -> str:
    """Save research output to a timestamped markdown file. Returns the path."""
    os.makedirs(_OUTPUTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_OUTPUTS_DIR, f"research_{ts}.md")
    with open(path, "w") as f:
        f.write(text)
    return path


def _extract_text(result) -> str:
    """Extract text from an Agent result."""
    if hasattr(result, "message"):
        msg = result.message
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        if content and isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                elif hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return "\n".join(parts)
    if hasattr(result, "text"):
        return result.text
    return str(result)


def _load_cached_articles(max_chars: int = 30000) -> str:
    """Read recent markdown articles from cache/articles/.

    Filters out articles that don't mention the current year (stale content).
    Groups by domain, sorts by file mod time (newest first),
    round-robins across groups so no single source dominates.
    Skips files under 500 bytes. Caps each article at 5000 chars.
    """
    cache_dir = os.environ.get("RESEARCH_CACHE_DIR", os.path.join(os.path.dirname(__file__), "cache"))
    articles_dir = os.path.join(cache_dir, "articles")
    if not os.path.isdir(articles_dir):
        return ""

    current_year = str(datetime.now().year)

    # Group files by domain
    groups = {}
    for fname in os.listdir(articles_dir):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(articles_dir, fname)
        if os.path.getsize(fpath) < 500:
            continue
        # Quick recency check — skip if current year not mentioned
        with open(fpath) as f:
            head = f.read(2000)
        if current_year not in head:
            continue
        domain = fname.split("_")[0]
        mtime = os.path.getmtime(fpath)
        groups.setdefault(domain, []).append((mtime, fpath))

    if not groups:
        return ""

    # Sort each group by mtime descending (newest first)
    for domain in groups:
        groups[domain].sort(key=lambda x: x[0], reverse=True)

    # Round-robin: 1 article per source first, then second pass if budget remains.
    # Cap each article to max_per_article chars so all sources fit.
    num_sources = len(groups)
    max_per_article = min(3000, max_chars // max(num_sources, 1))
    parts = []
    total = 0
    max_per_source = 1
    idx = 0
    domains = sorted(groups.keys())
    while total < max_chars and max_per_source <= 2:
        added_any = False
        for domain in domains:
            items = groups[domain]
            if idx >= len(items):
                continue
            _, fpath = items[idx]
            with open(fpath) as f:
                content = f.read()
            content = content[:max_per_article]
            parts.append(content)
            total += len(content)
            added_any = True
            if total >= max_chars:
                break
        idx += 1
        if not added_any:
            max_per_source += 1
            if idx >= max_per_source:
                break

    return "\n\n---\n\n".join(parts)


def run_research(task: str, provider: str = None, model_id: str = None) -> str:
    """Run the 3-agent pipeline sequentially and return the final narrative.

    Steps:
    1. Web researcher calls tools (results get cached as markdown in cache/articles/)
    2. Arxiv researcher calls tools (results returned as text)
    3. Insight agent gets the cached article markdown + arxiv text and writes narrative
    """
    prev_count = _ingest_previous_outputs()
    model = _build_model(provider, model_id)

    # Step 1: Web researcher gathers blog/HN/Reddit content
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Step 1/3: Web researcher gathering content...")
    web_agent = create_web_researcher(model)
    web_result = web_agent(task)
    web_text = _extract_text(web_result)
    # Also load the cached markdown articles the tools saved
    cached_articles = _load_cached_articles(20000)
    print(f"[{ts}] Web researcher done (agent: {len(web_text)} chars, cached articles: {len(cached_articles)} chars)")

    # Step 2: Arxiv researcher searches papers
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Step 2/3: Arxiv researcher searching papers...")
    arxiv_agent = create_arxiv_researcher(model)
    # Give arxiv agent a brief context, not the full web dump
    arxiv_prompt = (
        f"Search arxiv for recent AI/ML papers related to this task: {task}\n"
        f"Web research found topics including: {web_text[:2000]}"
    )
    arxiv_result = arxiv_agent(arxiv_prompt)
    arxiv_text = _extract_text(arxiv_result)
    print(f"[{ts}] Arxiv researcher done ({len(arxiv_text)} chars)")

    # Step 3: Insight agent gets ACTUAL cached content + arxiv findings
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Step 3/3: Insight agent writing narrative synthesis...")
    insight = create_insight_agent(model)

    # Build the insight prompt with real content from cache
    source_material = []
    if cached_articles:
        source_material.append(f"## Scraped Articles (from blogs, HN, Reddit)\n\n{cached_articles[:15000]}")
    if web_text:
        source_material.append(f"## Web Researcher Summary\n\n{web_text[:5000]}")
    if arxiv_text:
        source_material.append(f"## Arxiv Paper Findings\n\n{arxiv_text[:10000]}")

    insight_prompt = (
        "Below is source material gathered from web scraping and arxiv searches. "
        "Write a detailed narrative synthesis connecting these findings. "
        "Follow your system prompt instructions for the narrative format.\n\n"
        + "\n\n".join(source_material)
        + f"\n\nOriginal research task: {task}"
    )
    insight_result = insight(insight_prompt)
    insight_text = _extract_text(insight_result)
    print(f"[{ts}] Insight agent done ({len(insight_text)} chars)")

    # Combine: narrative first, raw findings as appendix
    sections = [insight_text]
    if cached_articles:
        sections.append("\n\n---\n## Appendix: Cached Article Content\n")
        sections.append(cached_articles[:15000])
    if arxiv_text:
        sections.append("\n\n---\n## Appendix: Arxiv Research Raw Findings\n")
        sections.append(arxiv_text[:15000])

    full_text = "\n".join(sections)

    out_path = _save_output(full_text)
    full_text += f"\n\n---\nSaved to: {out_path}"
    if prev_count:
        full_text += f"\n{prev_count} previous output(s) ingested for dedup comparison."

    return full_text


def run_cached_only(provider: str = None, model_id: str = None) -> str:
    """Skip fetching. Read cached markdown articles and run insight agent directly."""
    prev_count = _ingest_previous_outputs()
    model = _build_model(provider, model_id)

    cached_articles = _load_cached_articles(30000)
    if not cached_articles:
        return "No cached articles found in cache/articles/. Run a fetch first."

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Running insight agent on {len(cached_articles)} chars of cached content...")

    insight = create_insight_agent(model)
    insight_prompt = (
        "Below are articles and research content already gathered from blogs, "
        "Hacker News, Reddit, and arxiv. Write a detailed narrative synthesis "
        "connecting these findings. Follow your system prompt instructions "
        "for the narrative format.\n\n"
        f"{cached_articles}\n\n"
        "Produce a comprehensive research narrative with cross-source insights."
    )
    insight_result = insight(insight_prompt)
    insight_text = _extract_text(insight_result)
    print(f"[{ts}] Insight agent done ({len(insight_text)} chars)")

    sections = [insight_text]
    sections.append("\n\n---\n## Appendix: Source Articles\n")
    sections.append(cached_articles[:15000])

    full_text = "\n".join(sections)
    out_path = _save_output(full_text)
    full_text += f"\n\n---\nSaved to: {out_path}"
    if prev_count:
        full_text += f"\n{prev_count} previous output(s) ingested for dedup comparison."

    return full_text
