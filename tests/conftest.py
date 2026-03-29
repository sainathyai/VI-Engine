"""Shared pytest fixtures for VI Engine tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Temp database fixture ──────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a fresh, initialised SQLite database."""
    from vi_engine.state import init_db
    db = tmp_path / "test_state.sqlite3"
    init_db(db)
    return db


# ── TestClient fixture with all external calls mocked ─────────────────────

@pytest.fixture
def client(tmp_db: Path):
    """FastAPI TestClient with:
    - SQLite DB redirected to tmp_db
    - Anthropic API calls mocked (never hit the real API)
    - HTTP fetch calls mocked (never hit real URLs)
    - Publisher calls mocked
    """
    with (
        patch("vi_engine.dashboard.app.STATE_DB", tmp_db),
        patch("vi_engine.dashboard.app.SUBSTACK_DRAFTS_DIR", tmp_db.parent / "drafts"),
        patch("vi_engine.dashboard.app.SUBSTACK_POSTS_DIR", tmp_db.parent / "posts"),
        patch("vi_engine.dashboard.app.NEWSLETTER_DIR", tmp_db.parent),
        patch("vi_engine.dashboard.app.get_client") as mock_llm_client,
        patch("vi_engine.dashboard.app.fetch_markdown") as mock_fetch_md,
        patch("vi_engine.dashboard.app.fetch_snippet") as mock_fetch_snippet,
    ):
        # Mock Anthropic client so no real API calls are made
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type="text", text="Mock AI response.")]
        mock_client.messages.create.return_value = mock_message
        mock_llm_client.return_value = mock_client

        # Mock fetch calls
        mock_fetch_md.return_value = "# Mock Article\n\nThis is mock content for testing."
        mock_fetch_snippet.return_value = "This is a clean snippet about industry news."

        # Import the app after patching so patched STATE_DB is used at import
        from vi_engine.dashboard.app import app
        from vi_engine.state import init_db
        init_db(tmp_db)
        (tmp_db.parent / "drafts").mkdir(parents=True, exist_ok=True)
        (tmp_db.parent / "posts").mkdir(parents=True, exist_ok=True)

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Sample candidate factory ───────────────────────────────────────────────

def make_candidate(db: Path, *, title: str = "Test Article", url: str = "https://example.com/test",
                   source: str = "hacker_news", status: str = "discovered", score: int = 100) -> int:
    """Insert a candidate and return its id."""
    import sqlite3
    from vi_engine.state import add_candidate
    add_candidate(
        db,
        key=f"test|{url}",
        domain="test-domain",
        source=source,
        title=title,
        url=url,
        source_url=url,
        pub_date="2026-03-27",
        description="A test article description.",
        score=score,
    )
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT id FROM candidates WHERE key = ?", (f"test|{url}",)).fetchone()
    return row[0]
