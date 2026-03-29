"""Google News RSS search helper.

This avoids scraping: we consume Google News RSS search output to get
latest headline metadata (title/source/pubDate). Jina may not be able to
fetch Google News result pages, so Phase 1 can still synthesize trend
briefs from the headline metadata.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote_plus

import httpx


DEFAULT_BASE_RSS = "https://news.google.com/rss/search"
DEFAULT_HL = "en-US"
DEFAULT_GL = "US"
DEFAULT_CEID = "US:en"


def google_news_rss_url(
    query: str,
    *,
    time_window: str = "7d",
    base_rss: str = DEFAULT_BASE_RSS,
    hl: str = DEFAULT_HL,
    gl: str = DEFAULT_GL,
    ceid: str = DEFAULT_CEID,
) -> str:
    """Build a Google News RSS search URL for the given query.

    `query` can include Google News operators (e.g. `intitle:`, `when:`).
    We append a `when:<time_window>` window to focus on latest trends.
    """
    q_raw = f"{query} when:{time_window}"
    q = quote_plus(q_raw)
    return f"{base_rss}?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def _strip_html(s: str) -> str:
    # Lightweight HTML tag removal for RSS descriptions.
    return re.sub(r"<[^>]+>", " ", s or "", flags=re.MULTILINE).replace("&nbsp;", " ")


def google_news_items_from_rss(
    rss_url: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return latest Google News items from a RSS search URL."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(rss_url)
        r.raise_for_status()
    root = ET.fromstring(r.content)

    items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = _strip_html(item.findtext("description") or "").strip()

        source_el = item.find("source")
        source_url = None
        if source_el is not None:
            source_url = source_el.attrib.get("url")

        items.append(
            {
                "title": title,
                "link": link,
                "guid": guid,
                "pubDate": pub_date,
                "description": description,
                "source_url": source_url,
            }
        )
        if len(items) >= limit:
            break
    return items


def google_news_items(
    query: str,
    *,
    time_window: str = "7d",
    limit: int = 20,
    base_rss: str = DEFAULT_BASE_RSS,
    hl: str = DEFAULT_HL,
    gl: str = DEFAULT_GL,
    ceid: str = DEFAULT_CEID,
) -> list[dict[str, Any]]:
    """Convenience wrapper: build RSS URL and return items."""
    rss_url = google_news_rss_url(
        query,
        time_window=time_window,
        base_rss=base_rss,
        hl=hl,
        gl=gl,
        ceid=ceid,
    )
    return google_news_items_from_rss(rss_url, limit=limit)

