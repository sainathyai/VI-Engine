"""Central settings — adjust domain, models, and paths here."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
STATE_DB = PROJECT_ROOT / "state.sqlite3"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Narrow default: one provider, two roles (filter vs synthesis)
FILTER_MODEL = os.environ.get("ANTHROPIC_FILTER_MODEL", "claude-3-5-haiku-20241022")
SYNTHESIS_MODEL = os.environ.get("ANTHROPIC_SYNTHESIS_MODEL", "claude-3-5-sonnet-20241022")

JINA_READER_BASE = "https://r.jina.ai"

# Primary newsletter lock-down domain (Phase 0)
# Used in prompts and for tagging candidates/posts.
DOMAIN_TAG = os.environ.get("VI_DOMAIN_TAG", "tech-fintech-newsletter")

# Phase 1 (latest trends): Google News RSS search queries (comma-separated).
# Example operator usage inside a query: `intitle:` and `when:`.
GOOGLE_NEWS_BASE_RSS = os.environ.get(
    "GOOGLE_NEWS_BASE_RSS", "https://news.google.com/rss/search"
)
GOOGLE_NEWS_TIME_WINDOW = os.environ.get("GOOGLE_NEWS_TIME_WINDOW", "7d")
GOOGLE_NEWS_HL = os.environ.get("GOOGLE_NEWS_HL", "en-US")
GOOGLE_NEWS_GL = os.environ.get("GOOGLE_NEWS_GL", "US")
GOOGLE_NEWS_CEID = os.environ.get("GOOGLE_NEWS_CEID", "US:en")
ENABLE_GOOGLE_NEWS = os.environ.get("ENABLE_GOOGLE_NEWS", "1").strip() == "1"
GOOGLE_NEWS_QUERIES = [
    q.strip()
    for q in os.environ.get(
        "GOOGLE_NEWS_QUERIES",
        # Default niche: fintech/compliance + tech/AI release/regulatory signals.
        "fintech regulation,AML compliance,payment systems regulation,financial fraud prevention,crypto compliance,LLM release,AI tools,AI regulation,cybersecurity",
    ).split(",")
    if q.strip()
]

# Phase 1 — Tech sources for newsletter discovery
HN_TOP_STORIES_URL = os.environ.get(
    "HN_TOP_STORIES_URL",
    "https://hacker-news.firebaseio.com/v0/topstories.json",
)
HN_ITEM_URL = os.environ.get(
    "HN_ITEM_URL",
    "https://hacker-news.firebaseio.com/v0/item/{id}.json",
)

# AI company + lab blogs (no keys needed).
AI_COMPANY_RSS_FEEDS = [
    os.environ.get("OPENAI_RSS_URL", "https://openai.com/news/rss.xml"),
    os.environ.get("DEEP_MIND_RSS_URL", "https://deepmind.google/blog/rss.xml"),
    os.environ.get("HF_RSS_URL", "https://huggingface.co/blog/feed.xml"),
    "https://blog.google/technology/ai/rss/",
    "https://blogs.nvidia.com/feed/",
    "https://github.blog/feed/",
]

# Broad tech news RSS feeds.
TECH_NEWS_RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.technologyreview.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://hackernoon.com/feed",
    "https://aws.amazon.com/blogs/aws/feed/",
]

# How many stories to pull from Hacker News per collection run.
HN_COLLECT_LIMIT = int(os.environ.get("HN_COLLECT_LIMIT", "30"))

# Newsletter output paths
NEWSLETTER_DIR = OUTPUT_DIR / "substack"
SUBSTACK_DRAFTS_DIR = NEWSLETTER_DIR / "drafts"
SUBSTACK_POSTS_DIR = NEWSLETTER_DIR / "posts"

# Defaults for local dashboard review
DEFAULT_COLLECT_LIMIT = int(os.environ.get("COLLECT_LIMIT", "50"))
DEFAULT_PAGE_SIZE = int(os.environ.get("DASHBOARD_PAGE_SIZE", "12"))

# Google Alerts (optional)
# Provide a comma-separated list of RSS feed URLs you created in the Google Alerts UI.
GOOGLE_ALERTS_RSS_FEEDS = [
    x.strip()
    for x in os.environ.get("GOOGLE_ALERTS_RSS_FEEDS", "").split(",")
    if x.strip()
]

# ── Publishing integrations ──────────────────────────────────────────────────

# Ghost CMS (Admin API v4+)
# Get key from: Ghost Admin → Integrations → Add custom integration
GHOST_ADMIN_URL = os.environ.get("GHOST_ADMIN_URL", "")         # e.g. https://myblog.ghost.io
GHOST_ADMIN_API_KEY = os.environ.get("GHOST_ADMIN_API_KEY", "") # format: key_id:hex_secret

# WordPress REST API (Application Passwords, WP 5.6+)
# Generate from: WP Admin → Users → Profile → Application Passwords
WORDPRESS_SITE_URL = os.environ.get("WORDPRESS_SITE_URL", "")        # e.g. https://myblog.com
WORDPRESS_USERNAME = os.environ.get("WORDPRESS_USERNAME", "")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD", "") # spaces in password are ok

# X (Twitter) API — OAuth 1.0a credentials
# Get from: developer.twitter.com → your app → Keys and Tokens
# Requires "Read and Write" permissions set in User Auth Settings
X_API_KEY             = os.environ.get("X_API_KEY", "")
X_API_SECRET          = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

# GCP Cloud Scheduler — shared secret to authenticate /run/collect trigger calls
# Set to any random string; pass as X-Scheduler-Secret header from Cloud Scheduler
SCHEDULER_SECRET = os.environ.get("SCHEDULER_SECRET", "")
