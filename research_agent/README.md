# Research Agent

A multi-agent research system that monitors AI/ML blogs, Hacker News, Reddit, arxiv, and Substacks, then produces narrative synthesis reports connecting findings across sources.

Built on [Strands Agents SDK](https://strandsagents.com/) with custom tools.

## How It Works

1. **Gather**: Scrape blogs, RSS feeds, HN, Reddit, and arxiv for recent articles
2. **Cache**: Store scraped content as markdown files locally (avoids re-fetching)
3. **Synthesize**: An insight agent reads all cached articles and writes a narrative report connecting themes across sources
4. **Persist**: Reports saved to `outputs/` with timestamps; previous reports ingested into FAISS for dedup

The system supports two model providers:
- **Ollama** (default): Local inference with `qwen3.5:0.8b` (configurable in `config.py`)
- **Bedrock**: Amazon Bedrock with Claude Sonnet (recommended for higher quality output)

## Architecture

```
research_agent/
    config.py              # Single source of truth for model defaults
    orchestrator.py        # Sequential pipeline: web_researcher -> arxiv_researcher -> insight_agent
    web_researcher.py      # Scrapes blogs/HN/Reddit using web_research/*.md configs
    arxiv_researcher.py    # Searches arxiv for recent papers
    insight_agent.py       # Synthesizes findings into narrative report
    cli.py                 # CLI with interactive, daemon, poll-once, and cached-only modes
    app.py                 # Streamlit UI
    refresh_cache.py       # Rebuild article cache from RSS feeds and blog scraping
    requirements.txt
    web_research/          # Config files specifying which sources to monitor
        engineering_blogs.md
        github_io_blogs.md
        hackernews.md
        reddit.md
        substacks.md
    cache/articles/        # Cached article content as markdown (auto-generated)
    outputs/               # Generated research reports (auto-generated)

tools/                     # Shared tool modules (used by both research_agent and analysis_agents)
    web_scraper_tool.py    # Fetch/extract/RSS from URLs, 24h cache, markdownify conversion
    hackernews_tool.py     # HN stories via Firebase + Algolia APIs
    arxiv_tool.py          # Arxiv paper search via arxiv library
    reddit_tool.py         # Reddit via PRAW (needs REDDIT_CLIENT_ID/SECRET env vars)
    faiss_tool.py          # FAISS vector store for document storage and semantic search
    tests/                 # Unit tests for all tools
```

## Setup

### Prerequisites

- Python 3.11+
- Ollama running locally (for default provider), or AWS credentials for Bedrock
- Reddit API credentials (optional, for Reddit scraping)

### Install

```bash
python3.11 -m venv research_agent/.venv
research_agent/.venv/bin/pip install -r research_agent/requirements.txt
```

### Pull Ollama model (if using local inference)

```bash
ollama pull qwen3.5:0.8b
```

## Usage

### Quick start: refresh cache and generate report

```bash
# Step 1: Fetch recent articles from all configured sources
research_agent/.venv/bin/python research_agent/refresh_cache.py

# Step 2: Generate narrative report from cached articles (no network calls)
research_agent/.venv/bin/python research_agent/cli.py --cached-only
```

### CLI modes

```bash
# Interactive: type research tasks manually
research_agent/.venv/bin/python research_agent/cli.py

# Cached-only: synthesize from already-cached articles (fast, no fetching)
research_agent/.venv/bin/python research_agent/cli.py --cached-only

# Poll once: check for new articles, synthesize if threshold met
research_agent/.venv/bin/python research_agent/cli.py --poll-once --threshold 5

# Daemon: background loop polling every 30min
research_agent/.venv/bin/python research_agent/cli.py --daemon

# Custom settings
research_agent/.venv/bin/python research_agent/cli.py --daemon --interval 3600 --threshold 10

# Use Bedrock instead of Ollama (recommended for quality)
research_agent/.venv/bin/python research_agent/cli.py --cached-only --provider bedrock
```

### Streamlit UI

```bash
research_agent/.venv/bin/streamlit run research_agent/app.py
```

### Refresh article cache

```bash
# Fetches recent articles (last 14 days) from all RSS feeds and blogs
research_agent/.venv/bin/python research_agent/refresh_cache.py
```

This uses RSS feeds for Substacks and blogs that support it, and `extract_links` for others. Articles are saved as markdown in `cache/articles/`.

## Tools

| Tool | Description | Cache TTL |
|------|-------------|-----------|
| `web_scraper_tool` | Fetch URLs, extract text/article/links, parse RSS feeds | 24h |
| `hackernews_tool` | HN top/new/best stories, search, story details | 2h |
| `arxiv_tool` | Search papers, get recent papers, paper details | 12h |
| `reddit_tool` | Search subreddits, top posts, comments | 2h |
| `faiss_tool` | Store documents, semantic search (for dedup across runs) | N/A |

All cache TTLs are configurable via environment variables (`WEB_CACHE_TTL`, `HN_CACHE_TTL`, `ARXIV_CACHE_TTL`, `REDDIT_CACHE_TTL`).

## Web Research Configs

The `web_research/` folder contains markdown files that configure which sources to monitor. Each file lists URLs and instructions for the web researcher agent. Add or edit these to customize sources.

Current configs:
- `engineering_blogs.md` - Anthropic, Meta AI, Amazon Science, Microsoft Research, Google AI, OpenAI, DeepMind
- `github_io_blogs.md` - Karpathy, Lilian Weng, Colah, Jay Alammar, Sebastian Raschka, Ruder, Tim Dettmers
- `substacks.md` - The Gradient, Sebastian Raschka, Cameron Wolfe, Interconnects, Simon Willison, Latent Space, SemiAnalysis
- `hackernews.md` - AI/ML topic searches on HN
- `reddit.md` - MachineLearning, LocalLLaMA, MLOps, and other subreddits

## Running Tests

```bash
research_agent/.venv/bin/python -m pytest tools/tests/ -v
```

## Configuration

All model defaults are in `research_agent/config.py`:

```python
DEFAULT_PROVIDER = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen3.5:0.8b"
DEFAULT_BEDROCK_MODEL = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

Change the model in one place and it applies everywhere (CLI, Streamlit, orchestrator).

## Output Quality

Model choice significantly affects output quality:
- `qwen3.5:0.8b` (Ollama): Produces rough thematic summaries, limited source attribution
- Claude Sonnet (Bedrock): Produces detailed narrative essays with specific source citations, cross-source connections, contrarian analysis, and actionable recommendations
