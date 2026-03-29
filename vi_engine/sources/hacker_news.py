"""Hacker News discovery using official Firebase endpoints (no API key)."""

from __future__ import annotations

from typing import Any

import httpx

from vi_engine.config import HN_ITEM_URL, HN_TOP_STORIES_URL


def hn_top_story_ids(limit: int = 30) -> list[int]:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(HN_TOP_STORIES_URL)
        r.raise_for_status()
    ids = r.json()
    return [int(x) for x in ids[:limit]]


def hn_item(item_id: int) -> dict[str, Any] | None:
    url = HN_ITEM_URL.format(id=item_id)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        if r.status_code != 200:
            return None
        r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        return None
    return data


def hacker_news_top_items(limit: int = 20) -> list[dict[str, Any]]:
    ids = hn_top_story_ids(limit=limit)
    items: list[dict[str, Any]] = []
    for i in ids:
        try:
            data = hn_item(i)
        except Exception:
            continue
        if not data:
            continue
        title = (data.get("title") or "").strip()
        url = (data.get("url") or "").strip()
        ts = data.get("time")
        pub_date = str(ts) if ts is not None else ""
        score = int(data.get("score") or 0)
        comments = int(data.get("descendants") or 0)
        items.append(
            {
                "title": title,
                "url": url,
                "pubDate": pub_date,
                "description": (data.get("text") or "")[:500],
                "guid": f"hn:{i}",
                "source_url": url,
                "query": None,
                "score": score,
                "comments": comments,
            }
        )
        if len(items) >= limit:
            break
    return items

