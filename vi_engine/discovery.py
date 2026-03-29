"""Fetch candidate URLs from configured sources (RSS, APIs — extend per domain)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Iterable

import httpx


def urls_from_rss(feed_url: str, limit: int = 20) -> list[str]:
    """Parse RSS/Atom-ish feed and return entry links (best-effort)."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(feed_url)
        r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    urls: list[str] = []

    if root.tag.endswith("feed"):  # Atom
        for entry in root.findall("atom:entry", ns):
            link = entry.find("atom:link[@rel='alternate']", ns)
            if link is None:
                link = entry.find("atom:link", ns)
            if link is not None and link.get("href"):
                urls.append(link.get("href", "").strip())
    else:  # RSS 2.0
        for item in root.iter("item"):
            link_el = item.find("link")
            if link_el is not None and link_el.text:
                urls.append(link_el.text.strip())

    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def items_from_rss(feed_url: str, limit: int = 20) -> list[dict[str, Any]]:
    """Parse RSS/Atom feeds and return normalized item metadata."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(feed_url)
        r.raise_for_status()
    root = ET.fromstring(r.content)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, Any]] = []

    def add_one(
        *,
        title: str,
        link: str,
        pub_date: str | None,
        description: str | None,
        guid: str | None,
    ) -> None:
        key_link = (link or "").strip()
        if not key_link:
            return
        items.append(
            {
                "title": (title or "").strip(),
                "link": key_link,
                "pubDate": (pub_date or "").strip() if pub_date else "",
                "description": (description or "").strip() if description else "",
                "guid": (guid or "").strip() if guid else "",
            }
        )

    if root.tag.endswith("feed"):  # Atom
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = title_el.text if title_el is not None else ""

            link_el = entry.find("atom:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "").strip() if link_el is not None else ""

            pub_date = entry.findtext("atom:published", default=None, namespaces=ns)
            if not pub_date:
                pub_date = entry.findtext("atom:updated", default=None, namespaces=ns)
            description = entry.findtext("atom:summary", default=None, namespaces=ns) or entry.findtext(
                "atom:content", default=None, namespaces=ns
            )
            guid = entry.findtext("atom:id", default=None, namespaces=ns)

            add_one(
                title=title,
                link=link,
                pub_date=pub_date,
                description=description,
                guid=guid,
            )
            if len(items) >= limit:
                break
    else:  # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate")
            description = item.findtext("description")
            guid = item.findtext("guid")

            add_one(
                title=title,
                link=link,
                pub_date=pub_date,
                description=description,
                guid=guid,
            )
            if len(items) >= limit:
                break

    # Dedupe by link (best-effort)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        k = (it.get("link") or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
        if len(out) >= limit:
            break
    return out


def discover_all(feed_urls: Iterable[str], per_feed_limit: int = 10) -> list[str]:
    """Collect URLs from multiple feeds."""
    all_urls: list[str] = []
    for feed in feed_urls:
        try:
            all_urls.extend(urls_from_rss(feed, limit=per_feed_limit))
        except Exception:
            continue
    return all_urls


def discover_items_from_rss(feed_urls: Iterable[str], per_feed_limit: int = 10) -> list[dict[str, Any]]:
    """Collect item metadata from multiple RSS feeds."""
    all_items: list[dict[str, Any]] = []
    for feed in feed_urls:
        try:
            all_items.extend(items_from_rss(feed, limit=per_feed_limit))
        except Exception:
            continue
    return all_items
