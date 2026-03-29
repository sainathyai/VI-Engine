"""Phase 1 runner: discover → Jina → filter → synthesize → write outputs/*.md"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from vi_engine.config import (
    DOMAIN_TAG,
    GOOGLE_NEWS_BASE_RSS,
    GOOGLE_NEWS_CEID,
    GOOGLE_NEWS_GL,
    GOOGLE_NEWS_HL,
    GOOGLE_NEWS_QUERIES,
    GOOGLE_NEWS_TIME_WINDOW,
    OUTPUT_DIR,
    STATE_DB,
)
from vi_engine.discovery import discover_all
from vi_engine.extract import fetch_markdown
from vi_engine.llm import filter_keep_or_discard, get_client, synthesize_article
from vi_engine.state import already_seen, init_db, mark_seen
from vi_engine.sources.google_news import google_news_items

# Phase 1: SEC feed(s) provide actual article pages we can extract with Jina.
# Google News is used for trend headlines (title/source/pubDate), not full text.
DEFAULT_FEEDS: list[str] = ["https://www.sec.gov/news/pressreleases.rss"]


def _slug(s: str, max_len: int = 60) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len] or "article"


def _google_stub(item: dict[str, str], *, domain: str) -> str:
    title = (item.get("title") or "").strip()
    source_url = (item.get("source_url") or "").strip()
    pub_date = (item.get("pubDate") or "").strip()
    description = (item.get("description") or "").strip()
    # The model will base the brief on headline metadata (limited content by design).
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Domain tag: {domain}",
            f"Source: {source_url or 'unknown'}",
            f"Published: {pub_date or 'unknown'}",
            "",
            "Google News RSS description:",
            description or "(no description provided)",
            "",
        ]
    )


def run_once(feed_urls: list[str] | None = None, max_articles: int = 5) -> None:
    init_db(STATE_DB)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feeds = feed_urls or DEFAULT_FEEDS
    urls = discover_all(feeds)
    client = get_client()
    written = 0

    for url in urls:
        if written >= max_articles:
            break
        if already_seen(STATE_DB, url):
            continue
        try:
            md = fetch_markdown(url)
        except Exception:
            continue
        if not filter_keep_or_discard(client, md):
            mark_seen(STATE_DB, url)
            continue
        article = synthesize_article(client, url, md)
        first_line = article.splitlines()[0] if article else "untitled"
        title = first_line.lstrip("# ").strip() or "untitled"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        fname = f"{ts}-{_slug(title)}.md"
        out_path = OUTPUT_DIR / fname
        header = f"<!-- domain:{DOMAIN_TAG} source:{url} -->\n\n"
        out_path.write_text(header + article, encoding="utf-8")
        mark_seen(STATE_DB, url)
        written += 1

    # Add headline-driven trend briefs from Google News until we hit the cap.
    if written < max_articles:
        for query in GOOGLE_NEWS_QUERIES:
            if written >= max_articles:
                break
            items = google_news_items(
                query,
                time_window=GOOGLE_NEWS_TIME_WINDOW,
                limit=max(5, max_articles * 2),
                base_rss=GOOGLE_NEWS_BASE_RSS,
                hl=GOOGLE_NEWS_HL,
                gl=GOOGLE_NEWS_GL,
                ceid=GOOGLE_NEWS_CEID,
            )
            for item in items:
                if written >= max_articles:
                    break

                key = (item.get("guid") or item.get("link") or item.get("title") or "").strip()
                if not key:
                    continue
                if already_seen(STATE_DB, key):
                    continue

                stub = _google_stub(item, domain=DOMAIN_TAG)
                if not filter_keep_or_discard(client, stub):
                    mark_seen(STATE_DB, key)
                    continue

                source_url = (item.get("link") or item.get("source_url") or "google-news").strip()
                article = synthesize_article(client, source_url, stub)
                first_line = article.splitlines()[0] if article else "untitled"
                title = first_line.lstrip("# ").strip() or "untitled"
                ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                fname = f"{ts}-{_slug(title)}.md"
                out_path = OUTPUT_DIR / fname
                header = f"<!-- domain:{DOMAIN_TAG} source:{source_url} query:{query} -->\n\n"
                out_path.write_text(header + article, encoding="utf-8")
                mark_seen(STATE_DB, key)
                written += 1


if __name__ == "__main__":
    run_once()
