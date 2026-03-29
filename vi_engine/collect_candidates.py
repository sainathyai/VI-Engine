"""Phase 1 collection: discover candidates into SQLite (no LLM calls).

Iterates all enabled pipelines defined in pipelines.json and tags each
candidate with the pipeline slug so they can be filtered in the dashboard.
Falls back to legacy single-pipeline behaviour when pipelines.json is absent.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from vi_engine.config import (
    AI_COMPANY_RSS_FEEDS,
    DEFAULT_COLLECT_LIMIT,
    DOMAIN_TAG,
    ENABLE_GOOGLE_NEWS,
    GOOGLE_NEWS_BASE_RSS,
    GOOGLE_NEWS_CEID,
    GOOGLE_NEWS_GL,
    GOOGLE_NEWS_HL,
    GOOGLE_NEWS_TIME_WINDOW,
    HN_COLLECT_LIMIT,
    HN_TOP_STORIES_URL,
    OUTPUT_DIR,
    STATE_DB,
    TECH_NEWS_RSS_FEEDS,
    GOOGLE_ALERTS_RSS_FEEDS,
)
from vi_engine.discovery import discover_items_from_rss
from vi_engine.sources.google_news import google_news_items
from vi_engine.sources.hacker_news import hacker_news_top_items
from vi_engine.categorize import classify_by_keywords
from vi_engine.pipeline_config import enabled_pipelines
from vi_engine.state import add_candidate, init_db, set_candidate_tags


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _add_item(
    *,
    domain: str,
    key: str,
    source: str,
    title: str,
    url: str,
    source_url: str,
    pub_date: str,
    description: str,
    query: str | None = None,
    score: int = 0,
    comments: int = 0,
) -> None:
    cat, ctype = classify_by_keywords(title, description)
    add_candidate(
        STATE_DB,
        key=key,
        domain=domain,
        source=source,
        title=title,
        url=url,
        source_url=source_url,
        pub_date=pub_date,
        description=description,
        query=query,
        score=score,
        comments=comments,
    )
    if cat or ctype:
        import sqlite3
        with sqlite3.connect(STATE_DB) as conn:
            row = conn.execute("SELECT id FROM candidates WHERE key = ?", (key,)).fetchone()
            if row:
                set_candidate_tags(STATE_DB, candidate_id=row[0], category=cat, content_type=ctype)


def _collect_pipeline(pipeline: dict, args: argparse.Namespace) -> int:
    """Run collection for a single pipeline. Returns count of items processed."""
    slug = pipeline["slug"]
    label = pipeline["label"]
    rss_limit = max(1, args.rss_limit)
    added = 0

    print(f"\n  [{label}]")

    # ── Hacker News ────────────────────────────────────────────────────────
    if pipeline.get("include_hn", False):
        print(f"    Fetching Hacker News top {HN_COLLECT_LIMIT}...")
        for item in hacker_news_top_items(limit=HN_COLLECT_LIMIT):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            dedupe_key = (item.get("guid") or "").strip() or url
            _add_item(
                domain=slug,
                key=f"hn|{slug}|{dedupe_key}",
                source="hacker_news",
                title=item.get("title") or "",
                url=url,
                source_url=url,
                pub_date=item.get("pubDate") or "",
                description=item.get("description") or "",
                score=int(item.get("score") or 0),
                comments=int(item.get("comments") or 0),
            )
            added += 1

    # ── AI company / lab blogs ─────────────────────────────────────────────
    if pipeline.get("include_ai_blogs", False):
        print(f"    Fetching {len(AI_COMPANY_RSS_FEEDS)} AI company blogs...")
        for feed_url in AI_COMPANY_RSS_FEEDS:
            items = discover_items_from_rss([feed_url], per_feed_limit=rss_limit)
            for it in items:
                link = (it.get("link") or "").strip()
                if not link:
                    continue
                key = (it.get("guid") or "").strip() or link
                _add_item(
                    domain=slug,
                    key=f"rss|{slug}|{feed_url}|{key}",
                    source="ai_company_rss",
                    title=it.get("title") or "",
                    url=link,
                    source_url=feed_url,
                    pub_date=it.get("pubDate") or "",
                    description=it.get("description") or "",
                )
                added += 1

    # ── Pipeline-specific RSS feeds ────────────────────────────────────────
    pipeline_feeds = pipeline.get("rss_feeds", [])
    if pipeline_feeds:
        print(f"    Fetching {len(pipeline_feeds)} pipeline RSS feeds...")
        for feed_url in pipeline_feeds:
            try:
                items = discover_items_from_rss([feed_url], per_feed_limit=rss_limit)
            except Exception:
                continue
            for it in items:
                link = (it.get("link") or "").strip()
                if not link:
                    continue
                key = (it.get("guid") or "").strip() or link
                _add_item(
                    domain=slug,
                    key=f"feed|{slug}|{feed_url}|{key}",
                    source="pipeline_rss",
                    title=it.get("title") or "",
                    url=link,
                    source_url=feed_url,
                    pub_date=it.get("pubDate") or "",
                    description=it.get("description") or "",
                )
                added += 1

    # ── Google Alerts RSS (global, not pipeline-specific) ──────────────────
    for feed_url in GOOGLE_ALERTS_RSS_FEEDS:
        items = discover_items_from_rss([feed_url], per_feed_limit=rss_limit)
        for it in items:
            link = (it.get("link") or "").strip()
            if not link:
                continue
            key = (it.get("guid") or "").strip() or link
            _add_item(
                domain=slug,
                key=f"google_alerts|{slug}|{feed_url}|{key}",
                source="google_alerts_rss",
                title=it.get("title") or "",
                url=link,
                source_url=feed_url,
                pub_date=it.get("pubDate") or "",
                description=it.get("description") or "",
            )
            added += 1

    # ── Pipeline-specific Google News queries ──────────────────────────────
    queries = pipeline.get("google_news_queries", [])
    if ENABLE_GOOGLE_NEWS and queries:
        print(f"    Running {len(queries)} Google News queries...")
        for query in queries:
            items = google_news_items(
                query,
                time_window=GOOGLE_NEWS_TIME_WINDOW,
                limit=max(5, args.gnews_limit),
                base_rss=GOOGLE_NEWS_BASE_RSS,
                hl=GOOGLE_NEWS_HL,
                gl=GOOGLE_NEWS_GL,
                ceid=GOOGLE_NEWS_CEID,
            )
            for item in items:
                pub = (item.get("source_url") or "").strip()
                fetch_url = pub or (item.get("link") or "").strip()
                if not fetch_url:
                    continue
                key = (item.get("guid") or item.get("link") or item.get("title") or "").strip()
                if not key:
                    continue
                _add_item(
                    domain=slug,
                    key=f"gnews|{slug}|{key}",
                    source="google_news",
                    title=item.get("title") or "",
                    url=fetch_url,
                    source_url=pub or fetch_url,
                    pub_date=item.get("pubDate") or "",
                    description=item.get("description") or "",
                    query=query,
                )
                added += 1

    print(f"    → {added} items processed for [{label}]")
    return added


def _collect_legacy(args: argparse.Namespace) -> None:
    """Fallback: original single-pipeline collection when no pipelines.json found."""
    print("  No pipelines.json found — running legacy single-pipeline collection...")
    rss_limit = max(1, args.rss_limit)
    domain = DOMAIN_TAG

    # HN
    print(f"  Fetching Hacker News top {HN_COLLECT_LIMIT}...")
    for item in hacker_news_top_items(limit=HN_COLLECT_LIMIT):
        url = (item.get("url") or "").strip()
        if not url:
            continue
        dedupe_key = (item.get("guid") or "").strip() or url
        _add_item(domain=domain, key=f"hn|{dedupe_key}", source="hacker_news",
                  title=item.get("title") or "", url=url, source_url=url,
                  pub_date=item.get("pubDate") or "", description=item.get("description") or "",
                  score=int(item.get("score") or 0), comments=int(item.get("comments") or 0))

    # AI blogs
    print(f"  Fetching {len(AI_COMPANY_RSS_FEEDS)} AI company feeds...")
    for feed_url in AI_COMPANY_RSS_FEEDS:
        for it in discover_items_from_rss([feed_url], per_feed_limit=rss_limit):
            link = (it.get("link") or "").strip()
            if not link:
                continue
            key = (it.get("guid") or "").strip() or link
            _add_item(domain=domain, key=f"rss|{feed_url}|{key}", source="ai_company_rss",
                      title=it.get("title") or "", url=link, source_url=feed_url,
                      pub_date=it.get("pubDate") or "", description=it.get("description") or "")

    # Tech news
    print(f"  Fetching {len(TECH_NEWS_RSS_FEEDS)} tech news feeds...")
    for feed_url in TECH_NEWS_RSS_FEEDS:
        try:
            items = discover_items_from_rss([feed_url], per_feed_limit=rss_limit)
        except Exception:
            continue
        for it in items:
            link = (it.get("link") or "").strip()
            if not link:
                continue
            key = (it.get("guid") or "").strip() or link
            _add_item(domain=domain, key=f"tech|{feed_url}|{key}", source="tech_news",
                      title=it.get("title") or "", url=link, source_url=feed_url,
                      pub_date=it.get("pubDate") or "", description=it.get("description") or "")


def collect(args: argparse.Namespace) -> None:
    init_db(STATE_DB)
    pipelines = enabled_pipelines()
    if pipelines:
        print(f"  Running {len(pipelines)} pipeline(s)...")
        for pipeline in pipelines:
            _collect_pipeline(pipeline, args)
    else:
        _collect_legacy(args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Phase 1 candidates (no LLM calls).")
    parser.add_argument("--limit", type=int, default=DEFAULT_COLLECT_LIMIT)
    parser.add_argument("--rss-limit", type=int, default=max(5, DEFAULT_COLLECT_LIMIT // 5))
    parser.add_argument("--gnews-limit", type=int, default=max(10, DEFAULT_COLLECT_LIMIT // 2))
    args = parser.parse_args()

    collect(args)
    print(f"\n[{_now_stamp()}] Collection complete. Run the dashboard to review.")


if __name__ == "__main__":
    main()
