"""Clean article text via Jina Reader → Markdown, with direct HTML fallback."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

from vi_engine.config import JINA_READER_BASE


# ─── Content-cleaning regexes ──────────────────────────────────────────────

# Always-junk URL schemes
_CONTACT_SCHEME_RE = re.compile(r"\[.*?\]\((?:mailto:|tel:)", re.I)

# Standalone email addresses (generic — any x@y.z pattern)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Phone numbers (generic — US and international formats)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s][0-9]{3}[-.\s][0-9]{4}(?!\w)"
)

# Markdown link extractor
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

# List markers: "1." / "2." / "*" / "-" / "•"
_LIST_MARKER_RE = re.compile(r"(?:^|\s)(?:\d+\.|[-*•])\s+")


def _is_junk_line(line: str) -> bool:
    """Return True if the line is contact info, navigation noise, or a bare link list.

    Uses purely structural rules — no hardcoded domains. Works on any URL or platform.
    """
    stripped = line.strip()
    if not stripped:
        return True

    # mailto: / tel: links are always junk regardless of domain
    if _CONTACT_SCHEME_RE.search(stripped):
        return True

    # Any standalone email address
    if _EMAIL_RE.search(stripped):
        return True

    # Any phone number
    if _PHONE_RE.search(stripped):
        return True

    # ── Structural link analysis ─────────────────────────────────────────────
    links = _MARKDOWN_LINK_RE.findall(stripped)

    if not links:
        return False

    # Keep only anchor text; strip list markers → what's left is the actual prose
    prose = _MARKDOWN_LINK_RE.sub(r"\1", stripped)          # keep anchor text
    prose = _LIST_MARKER_RE.sub(" ", prose).strip()         # remove 1. / * / - markers
    prose = re.sub(r"\s{2,}", " ", prose)

    # A line that is ONLY link(s) with no prose is junk — regardless of URL
    # Single link: prose == anchor text alone; if that's short it's a nav item
    if len(links) == 1:
        anchor = links[0][0].strip()
        # The prose after stripping the link is just the anchor text itself.
        # If the whole line reduces to just the anchor text and it's short → junk
        non_anchor_prose = prose.replace(anchor, "").strip()
        if not non_anchor_prose and len(anchor) < 40:
            return True

    # Multiple links: nav menus, contact blocks, social link lists
    if len(links) >= 2:
        # Almost no readable prose left after stripping link markup
        if len(prose) < 50:
            return True
        # High markup density (URL chars dominate the line)
        url_chars = sum(len(url) for _, url in links)
        if url_chars / max(len(stripped), 1) > 0.4:
            return True

    return False


def _clean_snippet(text: str, max_chars: int = 600) -> str:
    """Filter junk lines and return a clean snippet up to max_chars."""
    lines: list[str] = []
    total = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _is_junk_line(stripped):
            continue
        # Skip short lines that look like navigation items or labels
        if len(stripped) < 35:
            continue
        lines.append(stripped)
        total += len(stripped) + 1
        if total >= max_chars:
            break
    snippet = " ".join(lines).strip()
    # Strip all markdown formatting → pure plain text
    snippet = re.sub(r"#{1,6}\s*", "", snippet)                    # headings
    snippet = _MARKDOWN_LINK_RE.sub(r"\1", snippet)                # links → anchor text only
    snippet = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", snippet)   # images → alt text
    snippet = re.sub(r"\*\*([^*]+)\*\*", r"\1", snippet)          # **bold**
    snippet = re.sub(r"__([^_]+)__", r"\1", snippet)              # __bold__
    snippet = re.sub(r"\*([^*]+)\*", r"\1", snippet)              # *italic*
    snippet = re.sub(r"_([^_]+)_", r"\1", snippet)                # _italic_
    snippet = re.sub(r"~~([^~]+)~~", r"\1", snippet)              # ~~strikethrough~~
    snippet = re.sub(r"`[^`]+`", "", snippet)                     # `inline code`
    snippet = re.sub(r"\s{2,}", " ", snippet)
    return snippet[:max_chars].strip()


# ─── Direct HTML text extractor (no external API) ─────────────────────────

class _TextExtractor(HTMLParser):
    """Strip HTML to plain text, skipping scripts/styles/nav/ads."""

    _SKIP_TAGS = frozenset({
        "script", "style", "noscript", "svg", "path", "nav", "header",
        "footer", "aside", "iframe", "form", "button", "select", "option",
        "figcaption",
    })

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def _html_to_text(html: str) -> str:
    """Convert raw HTML to plain text, stripping scripts/styles/nav."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    raw = parser.get_text()
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def fetch_text_direct(url: str, max_chars: int = 600) -> str:
    """Fetch a page directly and extract plain text. No Jina, no LLM."""
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        r = client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; VIEngine/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        if r.status_code != 200:
            return ""
    return _clean_snippet(_html_to_text(r.text), max_chars)


def fetch_markdown(url: str) -> str:
    """Return markdown from r.jina.ai for a public URL."""
    jina_url = f"{JINA_READER_BASE}/{url}"
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        r = client.get(jina_url, headers={"Accept": "text/markdown"})
        r.raise_for_status()
    return r.text


def fetch_snippet(url: str, max_chars: int = 600) -> str:
    """Fetch a short preview: try Jina first, fall back to direct HTML scrape."""
    jina_url = f"{JINA_READER_BASE}/{url}"
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            r = client.get(jina_url, headers={"Accept": "text/markdown"})
            if r.status_code != 200:
                raise ValueError(f"Jina returned {r.status_code}")
    except Exception:
        return fetch_text_direct(url, max_chars)

    text = r.text.strip()

    # Strip Jina metadata header
    skip_prefixes = ("Title:", "URL:", "Markdown Content:", "Published Time:", "Source:", "URL Source:")
    lines: list[str] = []
    past_header = False
    for line in text.splitlines():
        stripped = line.strip()
        if not past_header:
            if not stripped or any(stripped.startswith(p) for p in skip_prefixes):
                continue
            if stripped.startswith(("[![", "![", "---")):
                continue
            if stripped.startswith("#"):
                past_header = True
                continue
            past_header = True
        if not stripped:
            continue
        if stripped.startswith(("[![", "![", "---", "#")):
            continue
        lines.append(stripped)

    return _clean_snippet("\n".join(lines), max_chars)
