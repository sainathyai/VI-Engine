"""Tests for state.py database operations."""

import pytest
from pathlib import Path
from vi_engine.state import (
    init_db,
    add_candidate,
    list_candidates,
    get_candidate,
    set_candidate_status,
    set_candidate_tags,
    set_candidate_summary,
    candidate_counts,
    candidate_filter_options,
    create_newsletter,
    get_newsletter,
    list_newsletters,
    set_newsletter_status,
    set_newsletter_skills,
    add_publish_target,
    list_publish_targets,
    set_publish_target_status,
)
from tests.conftest import make_candidate


class TestInitDb:
    def test_creates_all_tables(self, tmp_db: Path):
        import sqlite3
        with sqlite3.connect(tmp_db) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "candidates" in tables
        assert "newsletters" in tables
        assert "newsletter_items" in tables
        assert "publish_targets" in tables
        assert "seen_urls" in tables

    def test_idempotent_double_init(self, tmp_db: Path):
        """Calling init_db twice should not raise or corrupt data."""
        init_db(tmp_db)
        init_db(tmp_db)


class TestCandidates:
    def test_add_and_retrieve_candidate(self, tmp_db: Path):
        cid = make_candidate(tmp_db, title="Test Article")
        c = get_candidate(tmp_db, candidate_id=cid)
        assert c is not None
        assert c["title"] == "Test Article"
        assert c["status"] == "discovered"

    def test_add_candidate_deduplicates_by_key(self, tmp_db: Path):
        url = "https://example.com/article"
        make_candidate(tmp_db, url=url, title="First")
        make_candidate(tmp_db, url=url, title="Second")  # same URL = same key
        results = list_candidates(tmp_db, status="discovered", limit=100)
        assert sum(1 for c in results if c["url"] == url) == 1

    def test_list_candidates_by_status(self, tmp_db: Path):
        make_candidate(tmp_db, title="Discovered 1", url="https://a.com/1")
        make_candidate(tmp_db, title="Discovered 2", url="https://a.com/2")
        results = list_candidates(tmp_db, status="discovered")
        assert len(results) == 2

    def test_list_candidates_filter_by_category(self, tmp_db: Path):
        cid1 = make_candidate(tmp_db, title="Energy Article", url="https://a.com/energy")
        cid2 = make_candidate(tmp_db, title="Tech Article", url="https://a.com/tech")
        set_candidate_tags(tmp_db, candidate_id=cid1, category="Oil & Gas", content_type="Analysis")
        set_candidate_tags(tmp_db, candidate_id=cid2, category="Technology", content_type="News")

        energy = list_candidates(tmp_db, status="discovered", category="Oil & Gas")
        assert len(energy) == 1
        assert energy[0]["title"] == "Energy Article"

    def test_list_candidates_filter_by_source(self, tmp_db: Path):
        make_candidate(tmp_db, title="HN Article", url="https://a.com/hn", source="hacker_news")
        make_candidate(tmp_db, title="Tech Article", url="https://a.com/tech", source="tech_news")

        hn_results = list_candidates(tmp_db, status="discovered", source="hacker_news")
        assert len(hn_results) == 1
        assert hn_results[0]["title"] == "HN Article"

    def test_list_candidates_sort_by_score(self, tmp_db: Path):
        make_candidate(tmp_db, title="Low Score", url="https://a.com/low", score=10)
        make_candidate(tmp_db, title="High Score", url="https://a.com/high", score=500)
        results = list_candidates(tmp_db, status="discovered", sort_by="score")
        assert results[0]["title"] == "High Score"

    def test_list_candidates_sort_by_title(self, tmp_db: Path):
        make_candidate(tmp_db, title="Zebra Article", url="https://a.com/z")
        make_candidate(tmp_db, title="Alpha Article", url="https://a.com/a")
        results = list_candidates(tmp_db, status="discovered", sort_by="title")
        assert results[0]["title"] == "Alpha Article"

    def test_set_candidate_status(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        set_candidate_status(tmp_db, candidate_id=cid, status="approved", note="Looks good")
        c = get_candidate(tmp_db, candidate_id=cid)
        assert c["status"] == "approved"

    def test_candidate_counts(self, tmp_db: Path):
        make_candidate(tmp_db, url="https://a.com/1")
        make_candidate(tmp_db, url="https://a.com/2")
        cid3 = make_candidate(tmp_db, url="https://a.com/3")
        set_candidate_status(tmp_db, candidate_id=cid3, status="approved")
        counts = candidate_counts(tmp_db)
        assert counts.get("discovered", 0) == 2
        assert counts.get("approved", 0) == 1

    def test_candidate_filter_options(self, tmp_db: Path):
        cid1 = make_candidate(tmp_db, url="https://a.com/1", source="hacker_news")
        cid2 = make_candidate(tmp_db, url="https://a.com/2", source="tech_news")
        set_candidate_tags(tmp_db, candidate_id=cid1, category="AI & Machine Learning", content_type="News")
        set_candidate_tags(tmp_db, candidate_id=cid2, category="Fintech & Crypto", content_type="Analysis")

        opts = candidate_filter_options(tmp_db)
        assert "AI & Machine Learning" in opts["categories"]
        assert "Fintech & Crypto" in opts["categories"]
        assert "hacker_news" in opts["sources"]
        assert "tech_news" in opts["sources"]


class TestNewsletters:
    def test_create_and_retrieve_newsletter(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        nl_id = create_newsletter(tmp_db, title="Test Newsletter", body="# Hello\n\nBody text.", candidate_ids=[cid])
        nl = get_newsletter(tmp_db, newsletter_id=nl_id)
        assert nl is not None
        assert nl["title"] == "Test Newsletter"
        assert nl["status"] == "draft"
        assert nl["voice"] == ""
        assert nl["industry"] == ""

    def test_set_newsletter_skills(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        nl_id = create_newsletter(tmp_db, title="Test", body="Body", candidate_ids=[cid])
        set_newsletter_skills(tmp_db, newsletter_id=nl_id, voice="skeptical_analyst", industry="oil_gas_energy")
        nl = get_newsletter(tmp_db, newsletter_id=nl_id)
        assert nl["voice"] == "skeptical_analyst"
        assert nl["industry"] == "oil_gas_energy"

    def test_set_newsletter_status_to_published(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        nl_id = create_newsletter(tmp_db, title="Test", body="Body", candidate_ids=[cid])
        set_newsletter_status(tmp_db, newsletter_id=nl_id, status="published")
        nl = get_newsletter(tmp_db, newsletter_id=nl_id)
        assert nl["status"] == "published"
        assert nl["published_at"] is not None

    def test_list_newsletters(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        create_newsletter(tmp_db, title="NL 1", body="Body 1", candidate_ids=[cid])
        create_newsletter(tmp_db, title="NL 2", body="Body 2", candidate_ids=[cid])
        nls = list_newsletters(tmp_db)
        assert len(nls) == 2

    def test_publish_targets_lifecycle(self, tmp_db: Path):
        cid = make_candidate(tmp_db)
        nl_id = create_newsletter(tmp_db, title="Test", body="Body", candidate_ids=[cid])
        add_publish_target(tmp_db, newsletter_id=nl_id, platform="ghost")
        add_publish_target(tmp_db, newsletter_id=nl_id, platform="linkedin")

        targets = list_publish_targets(tmp_db, newsletter_id=nl_id)
        assert len(targets) == 2
        assert {t["platform"] for t in targets} == {"ghost", "linkedin"}
        assert all(t["status"] == "pending" for t in targets)

        # Publish the ghost target
        ghost_id = next(t["id"] for t in targets if t["platform"] == "ghost")
        set_publish_target_status(tmp_db, target_id=ghost_id, status="published", publish_url="https://myblog.ghost.io/p/test")
        targets = list_publish_targets(tmp_db, newsletter_id=nl_id)
        ghost = next(t for t in targets if t["platform"] == "ghost")
        assert ghost["status"] == "published"
        assert ghost["publish_url"] == "https://myblog.ghost.io/p/test"
