"""Load and expose named pipeline definitions from pipelines.json.

pipelines.json lives at the project root (next to pyproject.toml / requirements.txt).
Each pipeline defines its own RSS feeds, Google News queries, and labelling.

Schema per pipeline entry:
    slug            str   — machine identifier, used as `domain` tag on candidates
    label           str   — human display name
    industry        str   — maps to a vi_engine/skills/industries/*.md file
    enabled         bool  — skip if false
    include_hn      bool  — pull Hacker News top stories for this pipeline
    include_ai_blogs bool — pull AI company / lab RSS blogs for this pipeline
    rss_feeds       list  — pipeline-specific RSS feed URLs
    google_news_queries list — pipeline-specific Google News search terms
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PIPELINES_FILE = _PROJECT_ROOT / "pipelines.json"


def load_pipelines() -> list[dict[str, Any]]:
    """Return all pipeline definitions. Returns empty list if file missing."""
    if not _PIPELINES_FILE.exists():
        return []
    with open(_PIPELINES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pipelines", [])


def enabled_pipelines() -> list[dict[str, Any]]:
    """Return only the pipelines with enabled=true."""
    return [p for p in load_pipelines() if p.get("enabled", True)]


def pipeline_labels() -> dict[str, str]:
    """Return {slug: label} for all loaded pipelines."""
    return {p["slug"]: p["label"] for p in load_pipelines()}
