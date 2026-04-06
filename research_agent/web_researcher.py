"""
Web Researcher Agent - reads web_research/*.md configs at runtime,
scrapes blogs/reddit/HN using tools from the tools/ folder.
"""

import os
import glob
from strands import Agent
from tools import web_scraper_tool, hackernews_tool, reddit_tool


def _load_research_configs() -> str:
    """Load all markdown config files from web_research/ folder."""
    config_dir = os.path.join(os.path.dirname(__file__), "web_research")
    configs = []
    for md_path in sorted(glob.glob(os.path.join(config_dir, "*.md"))):
        name = os.path.basename(md_path)
        with open(md_path) as f:
            content = f.read()
        configs.append(f"=== {name} ===\n{content}")
    return "\n\n".join(configs)


SYSTEM_PROMPT = """You are a web research agent. You MUST call tools to gather information. Do NOT describe what you would do. Actually call the tools.

Tools available:
- web_scraper_tool: actions: extract_rss, extract_links, extract_article, extract_text, fetch_url
- hackernews_tool: actions: get_stories, search_stories, get_story_details
- reddit_tool: actions: search_subreddit, get_top_posts, get_post_comments

Research configs:
{configs}

EXECUTION PLAN - follow this exactly by calling tools:

1. SUBSTACKS: For Substack URLs (substack.com, magazine.sebastianraschka.com, latent.space, etc.):
   a) Call web_scraper_tool action="extract_rss" url=<substack_url> max_items=5
      This returns article titles, URLs, dates, and summaries from the RSS feed.
   b) For the top 3 most recent articles, call web_scraper_tool action="extract_article" url=<article_url>
   c) Write a 3-5 sentence summary of each article's key technical contribution

2. BLOGS: For non-Substack blog URLs (engineering blogs, github.io blogs):
   a) Call web_scraper_tool action="extract_links" url=<blog_url>
   b) From the returned links, pick up to 3 recent articles
   c) Call web_scraper_tool action="extract_article" url=<article_url> for each
   d) Write a 3-5 sentence summary of each article's key technical contribution

3. HACKER NEWS: Call hackernews_tool action="get_stories" category="top" limit=10
   Then call hackernews_tool action="get_story_details" for the top 3 AI/ML related stories

4. REDDIT (if credentials available): Call reddit_tool action="get_top_posts" for MachineLearning and LocalLLaMA subreddits

After gathering all data, compile your findings as a DETAILED summary. For each article or post include:
- The title and URL
- A 3-5 sentence summary of the actual content (not just the title)
- The key technical claim or finding

IMPORTANT: Start calling tools immediately. Do not write plans or describe what you will do.
When done, output your full detailed findings. Do NOT try to call handoff_to_agent."""


def create_web_researcher(model) -> Agent:
    """Create the web researcher agent with loaded configs."""
    configs = _load_research_configs()
    prompt = SYSTEM_PROMPT.format(configs=configs)
    return Agent(
        name="web_researcher",
        model=model,
        system_prompt=prompt,
        tools=[web_scraper_tool, hackernews_tool, reddit_tool],
    )
