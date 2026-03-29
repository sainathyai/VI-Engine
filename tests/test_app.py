"""End-to-end dashboard endpoint tests with mocked external calls."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_candidate


# ── Home page ──────────────────────────────────────────────────────────────

class TestHomePage:
    def test_home_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "VI Engine" in resp.text

    def test_home_shows_stats(self, client: TestClient, tmp_db: Path):
        make_candidate(tmp_db, url="https://a.com/1")
        make_candidate(tmp_db, url="https://a.com/2")
        resp = client.get("/")
        assert resp.status_code == 200


# ── Topics ─────────────────────────────────────────────────────────────────

class TestTopics:
    def test_topics_page_renders(self, client: TestClient):
        resp = client.get("/topics")
        assert resp.status_code == 200

    def test_topics_shows_candidates(self, client: TestClient, tmp_db: Path):
        make_candidate(tmp_db, title="Energy Market Signals")
        resp = client.get("/topics")
        assert "Energy Market Signals" in resp.text

    def test_topics_filter_by_status(self, client: TestClient, tmp_db: Path):
        resp = client.get("/topics?status=approved")
        assert resp.status_code == 200
        assert "Approved" in resp.text or "approved" in resp.text.lower()

    def test_topics_filter_by_source(self, client: TestClient, tmp_db: Path):
        make_candidate(tmp_db, title="HN Story", url="https://a.com/hn", source="hacker_news")
        make_candidate(tmp_db, title="Tech News Story", url="https://a.com/tech", source="tech_news")
        resp = client.get("/topics?source=hacker_news")
        assert resp.status_code == 200
        assert "HN Story" in resp.text
        assert "Tech News Story" not in resp.text

    def test_topics_sort_by_score(self, client: TestClient, tmp_db: Path):
        make_candidate(tmp_db, title="Low Score Article", url="https://a.com/low", score=1)
        make_candidate(tmp_db, title="High Score Article", url="https://a.com/high", score=999)
        resp = client.get("/topics?sort_by=score")
        assert resp.status_code == 200
        # High score should appear before low score in the HTML
        assert resp.text.index("High Score Article") < resp.text.index("Low Score Article")

    def test_approve_single_topic(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        resp = client.post(f"/topics/{cid}/approve", follow_redirects=False)
        assert resp.status_code == 303

        from vi_engine.state import get_candidate
        c = get_candidate(tmp_db, candidate_id=cid)
        assert c["status"] == "approved"

    def test_discard_single_topic(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        resp = client.post(f"/topics/{cid}/discard", follow_redirects=False)
        assert resp.status_code == 303

        from vi_engine.state import get_candidate
        c = get_candidate(tmp_db, candidate_id=cid)
        assert c["status"] == "discarded"

    def test_bulk_approve(self, client: TestClient, tmp_db: Path):
        cid1 = make_candidate(tmp_db, url="https://a.com/1")
        cid2 = make_candidate(tmp_db, url="https://a.com/2")
        resp = client.post("/topics/approve", data={"candidate_ids": f"{cid1},{cid2}"}, follow_redirects=False)
        assert resp.status_code == 303

        from vi_engine.state import get_candidate
        assert get_candidate(tmp_db, candidate_id=cid1)["status"] == "approved"
        assert get_candidate(tmp_db, candidate_id=cid2)["status"] == "approved"


# ── Snippet API ────────────────────────────────────────────────────────────

class TestSnippetAPI:
    def test_snippet_returns_clean_content(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        resp = client.post(f"/api/topics/{cid}/snippet")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "description" in data
        # Mock returns a clean string — no contact info
        assert "mailto:" not in data["description"]

    def test_snippet_unknown_candidate(self, client: TestClient):
        resp = client.post("/api/topics/99999/snippet")
        assert resp.status_code == 404

    def test_enrich_returns_summary(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        resp = client.post(f"/api/topics/{cid}/enrich")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "summary" in data

    def test_enrich_unknown_candidate(self, client: TestClient):
        resp = client.post("/api/topics/99999/enrich")
        assert resp.status_code == 404


# ── Generate ───────────────────────────────────────────────────────────────

class TestGenerate:
    def test_generate_page_renders(self, client: TestClient):
        resp = client.get("/generate")
        assert resp.status_code == 200

    def test_summarize_approved_candidate(self, client: TestClient, tmp_db: Path):
        from vi_engine.state import set_candidate_status
        cid = make_candidate(tmp_db)
        set_candidate_status(tmp_db, candidate_id=cid, status="approved")

        resp = client.post(
            "/generate/summarize",
            data={"candidate_ids": str(cid)},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        from vi_engine.state import get_candidate
        c = get_candidate(tmp_db, candidate_id=cid)
        assert c["status"] == "summarized"

    def test_compile_newsletter(self, client: TestClient, tmp_db: Path):
        from vi_engine.state import set_candidate_status, set_candidate_output
        cid = make_candidate(tmp_db)
        set_candidate_status(tmp_db, candidate_id=cid, status="summarized")
        # Create a fake output file
        out_path = tmp_db.parent / "posts" / "test_article.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# Test\n\nContent.", encoding="utf-8")
        set_candidate_output(tmp_db, candidate_id=cid, output_path=str(out_path), status="summarized")

        resp = client.post(
            "/generate/newsletter",
            data={"candidate_ids": str(cid), "title": "Test Newsletter March 2026"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        from vi_engine.state import list_newsletters
        nls = list_newsletters(tmp_db)
        assert len(nls) == 1
        assert "Test Newsletter March 2026" in nls[0]["title"]


# ── Newsletters ────────────────────────────────────────────────────────────

class TestNewsletters:
    def test_newsletters_list_renders(self, client: TestClient):
        resp = client.get("/newsletters")
        assert resp.status_code == 200

    def test_newsletter_detail_renders(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="March Edition", body="# Hello", candidate_ids=[cid])
        resp = client.get(f"/newsletters/{nl_id}")
        assert resp.status_code == 200
        assert "March Edition" in resp.text

    def test_newsletter_detail_shows_voice_selectors(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="Voice Test", body="# Body", candidate_ids=[cid])
        resp = client.get(f"/newsletters/{nl_id}")
        assert "Skeptical Analyst" in resp.text or "skeptical_analyst" in resp.text

    def test_set_newsletter_skills(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter, get_newsletter
        nl_id = create_newsletter(tmp_db, title="Skills Test", body="# Body", candidate_ids=[cid])

        resp = client.post(
            f"/newsletters/{nl_id}/skills",
            data={"voice": "contrarian", "industry": "oil_gas_energy"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        nl = get_newsletter(tmp_db, newsletter_id=nl_id)
        assert nl["voice"] == "contrarian"
        assert nl["industry"] == "oil_gas_energy"

    def test_select_publish_platforms(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter, list_publish_targets
        nl_id = create_newsletter(tmp_db, title="Publish Test", body="# Body", candidate_ids=[cid])

        resp = client.post(
            f"/newsletters/{nl_id}/publish",
            data={"platforms": "ghost,linkedin"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        targets = list_publish_targets(tmp_db, newsletter_id=nl_id)
        platforms = {t["platform"] for t in targets}
        assert "ghost" in platforms
        assert "linkedin" in platforms

    def test_approve_publish_with_no_configured_publishers(self, client: TestClient, tmp_db: Path):
        """When no publishers are configured, targets get 'skipped' status."""
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter, set_newsletter_status, add_publish_target, list_publish_targets
        nl_id = create_newsletter(tmp_db, title="Publish Test", body="# Body", candidate_ids=[cid])
        add_publish_target(tmp_db, newsletter_id=nl_id, platform="ghost")
        set_newsletter_status(tmp_db, newsletter_id=nl_id, status="queued")

        # No GHOST_ADMIN_URL set → publisher returns None → status becomes 'skipped'
        with patch("vi_engine.dashboard.app.get_publisher", return_value=None):
            resp = client.post(f"/newsletters/{nl_id}/approve-publish", follow_redirects=False)
        assert resp.status_code == 303

        from vi_engine.state import get_newsletter
        nl = get_newsletter(tmp_db, newsletter_id=nl_id)
        assert nl["status"] == "published"

        targets = list_publish_targets(tmp_db, newsletter_id=nl_id)
        assert targets[0]["status"] == "skipped"

    def test_approve_publish_with_mock_ghost_publisher(self, client: TestClient, tmp_db: Path):
        """When Ghost publisher is configured, it gets called and URL is recorded."""
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter, set_newsletter_status, add_publish_target, list_publish_targets
        nl_id = create_newsletter(tmp_db, title="Ghost Publish Test", body="# Body", candidate_ids=[cid])
        add_publish_target(tmp_db, newsletter_id=nl_id, platform="ghost")
        set_newsletter_status(tmp_db, newsletter_id=nl_id, status="queued")

        mock_publisher = MagicMock()
        mock_publisher.publish.return_value = "https://myblog.ghost.io/p/ghost-publish-test"

        with patch("vi_engine.dashboard.app.get_publisher", return_value=mock_publisher):
            resp = client.post(f"/newsletters/{nl_id}/approve-publish", follow_redirects=False)
        assert resp.status_code == 303

        targets = list_publish_targets(tmp_db, newsletter_id=nl_id)
        assert targets[0]["status"] == "published"
        assert "ghost.io" in targets[0]["publish_url"]


# ── Platform preview API ────────────────────────────────────────────────────

class TestPlatformPreview:
    def test_blog_preview(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="Preview Test", body="# Test Body\n\nContent.", candidate_ids=[cid])

        resp = client.post(f"/api/newsletters/{nl_id}/preview/blog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "content" in data
        assert data["platform"] == "blog"

    def test_linkedin_preview(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="LinkedIn Test", body="# Body", candidate_ids=[cid])

        resp = client.post(f"/api/newsletters/{nl_id}/preview/linkedin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["platform"] == "linkedin"

    def test_twitter_preview(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="Twitter Test", body="# Body", candidate_ids=[cid])

        resp = client.post(f"/api/newsletters/{nl_id}/preview/twitter")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_invalid_platform_returns_400(self, client: TestClient, tmp_db: Path):
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter
        nl_id = create_newsletter(tmp_db, title="Bad Platform", body="# Body", candidate_ids=[cid])

        resp = client.post(f"/api/newsletters/{nl_id}/preview/myspace")
        assert resp.status_code == 400

    def test_unknown_newsletter_returns_404(self, client: TestClient):
        resp = client.post("/api/newsletters/99999/preview/blog")
        assert resp.status_code == 404

    def test_preview_uses_voice_and_industry(self, client: TestClient, tmp_db: Path):
        """Verify skills settings are passed through to generate_platform_content."""
        cid = make_candidate(tmp_db)
        from vi_engine.state import create_newsletter, set_newsletter_skills
        nl_id = create_newsletter(tmp_db, title="Skills Test", body="# Body", candidate_ids=[cid])
        set_newsletter_skills(tmp_db, newsletter_id=nl_id, voice="skeptical_analyst", industry="oil_gas_energy")

        with patch("vi_engine.dashboard.app.generate_platform_content") as mock_gen:
            mock_gen.return_value = "Mock generated content"
            resp = client.post(f"/api/newsletters/{nl_id}/preview/blog")

        assert resp.status_code == 200
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["voice"] == "skeptical_analyst"
        assert call_kwargs["industry"] == "oil_gas_energy"
        assert call_kwargs["platform"] == "blog"


# ── Scheduler trigger ───────────────────────────────────────────────────────

class TestSchedulerTrigger:
    def test_trigger_without_secret_set_accepts_all(self, client: TestClient):
        """When SCHEDULER_SECRET is empty, any request is accepted."""
        with patch("vi_engine.dashboard.app.SCHEDULER_SECRET", ""):
            with patch("vi_engine.collect_candidates.collect") as mock_collect:
                resp = client.post("/run/collect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_trigger_with_correct_secret(self, client: TestClient):
        with patch("vi_engine.dashboard.app.SCHEDULER_SECRET", "my-secret"):
            with patch("vi_engine.collect_candidates.collect"):
                resp = client.post(
                    "/run/collect",
                    headers={"X-Scheduler-Secret": "my-secret"},
                )
        assert resp.status_code == 200

    def test_trigger_with_wrong_secret_returns_403(self, client: TestClient):
        with patch("vi_engine.dashboard.app.SCHEDULER_SECRET", "correct-secret"):
            resp = client.post(
                "/run/collect",
                headers={"X-Scheduler-Secret": "wrong-secret"},
            )
        assert resp.status_code == 403
