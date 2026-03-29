"""Tests for content filtering in extract.py."""

import pytest
from vi_engine.extract import _is_junk_line, _clean_snippet, fetch_snippet
from unittest.mock import patch, MagicMock


# ── _is_junk_line ──────────────────────────────────────────────────────────

class TestIsJunkLine:
    def test_email_link_is_junk(self):
        assert _is_junk_line("[Email](mailto:jakelsaunders94@gmail.com)")

    def test_linkedin_link_is_junk(self):
        assert _is_junk_line("[LinkedIn](https://www.linkedin.com/in/jake-saunders-83617741/)")

    def test_github_link_is_junk(self):
        assert _is_junk_line("[JakeWritesCode](https://github.com/JakeWritesCode)")

    def test_twitter_link_is_junk(self):
        assert _is_junk_line("[Follow me](https://twitter.com/jake)")

    def test_standalone_email_is_junk(self):
        assert _is_junk_line("Contact us at hello@example.com for more info")

    def test_phone_number_is_junk(self):
        assert _is_junk_line("Call us at 555-867-5309 anytime")

    def test_bare_markdown_link_is_junk(self):
        assert _is_junk_line("[About me](https://blog.jakesaunders.dev/about/)")

    def test_nav_link_list_is_junk(self):
        # Multiple links with minimal surrounding text
        assert _is_junk_line("[Home](/) [About](/about) [Contact](/contact)")

    def test_real_content_not_junk(self):
        assert not _is_junk_line(
            "The EPA's new methane rule will cost independent Permian operators $40K per site annually."
        )

    def test_article_paragraph_not_junk(self):
        assert not _is_junk_line(
            "At serious risk of sounding like a heretic here, but the adoption of AI in drilling "
            "operations is lagging far behind vendor promises."
        )

    def test_empty_line_is_junk(self):
        assert _is_junk_line("")
        assert _is_junk_line("   ")

    def test_short_line_not_junk_via_is_junk(self):
        # _is_junk_line doesn't check length — that's done in _clean_snippet
        assert not _is_junk_line("Short but legit text here that is fine")

    def test_numbered_list_contact_links_are_junk(self):
        """Regression: 1. [Email](mailto:...) 2. [LinkedIn](...) style blocks."""
        assert _is_junk_line(
            "1. [Email](mailto:jakelsaunders94@gmail.com) 2. [JakeWritesCode](https://github.com/JakeWritesCode) "
            "3. [LinkedIn](https://www.linkedin.com/in/jake-saunders-83617741/)"
        )

    def test_bullet_nav_links_are_junk(self):
        """Regression: * [Apple](url) * [Store](url) * [Mac](url) nav bars."""
        assert _is_junk_line(
            "* [Apple](https://www.apple.com/) * * [Store](https://www.apple.com/us/shop/goto/store) "
            "* [Mac](https://www.apple.com/mac/) * [iPad](https://www.apple.com/ipad/) "
            "* [iPhone](https://www.apple.com/iphone/)"
        )

    def test_single_list_prefixed_link_is_junk(self):
        """1. [About me](url) — numbered list single link."""
        assert _is_junk_line("1. [About me](https://blog.jakesaunders.dev/about/)")


# ── _clean_snippet ─────────────────────────────────────────────────────────

class TestCleanSnippet:
    def test_strips_social_links(self):
        raw = """
[Email](mailto:test@example.com)
[LinkedIn](https://linkedin.com/in/someone)
At serious risk of sounding like a heretic here, but I'm kinda bored of talking about AI.
I get it, AI is incredible and it changes everything about how we work.
"""
        result = _clean_snippet(raw)
        assert "mailto:" not in result
        assert "linkedin.com" not in result
        assert "heretic" in result

    def test_strips_nav_menu(self):
        raw = """
[Home](/) [About](/about) [Contact](/contact) [Blog](/blog)
This article explores the latest developments in oil and gas exploration technology.
Operators in the Permian Basin are reporting significant efficiency gains from AI-assisted drilling.
"""
        result = _clean_snippet(raw)
        assert "[Home]" not in result
        assert "oil and gas" in result

    def test_respects_max_chars(self):
        long_text = "A" * 200 + " " + "B" * 200 + " " + "C" * 200 + " " + "D" * 200
        result = _clean_snippet(long_text, max_chars=300)
        assert len(result) <= 300

    def test_removes_email_addresses(self):
        raw = "Contact john.smith@company.com for details about the regulatory filing."
        result = _clean_snippet(raw)
        assert "@" not in result or len(result) == 0

    def test_keeps_clean_content(self):
        raw = (
            "The Federal Reserve's latest guidance on fintech partnerships signals a harder line "
            "on third-party risk. Banks that outsourced compliance functions to BaaS providers "
            "are now scrambling to bring those capabilities back in-house."
        )
        result = _clean_snippet(raw)
        assert "Federal Reserve" in result
        assert "BaaS" in result

    def test_converts_markdown_links_to_anchor_text(self):
        raw = (
            "According to [Reuters](https://reuters.com/article/energy), natural gas prices "
            "are expected to remain elevated through Q3 2026 due to supply constraints."
        )
        result = _clean_snippet(raw)
        # The URL should be stripped but the anchor text kept
        assert "reuters.com" not in result
        assert "natural gas" in result

    def test_empty_input(self):
        assert _clean_snippet("") == ""

    def test_only_junk_returns_empty(self):
        raw = """
[Email](mailto:a@b.com)
[Twitter](https://twitter.com/user)
short
"""
        result = _clean_snippet(raw)
        assert result == "" or len(result) < 10


# ── fetch_snippet with mocked Jina ─────────────────────────────────────────

class TestFetchSnippet:
    def test_filters_jina_header_lines(self):
        """Jina-style metadata headers should be stripped."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """Title: Test Article
URL Source: https://example.com/test
Published Time: 2026-03-27

# Test Article

[Email the author](mailto:author@example.com)
[LinkedIn](https://linkedin.com/in/author)

The oil and gas industry is undergoing a significant digital transformation.
Operators are deploying AI-assisted drilling systems that reduce costs by up to 15 percent.
"""
        with patch("vi_engine.extract.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = fetch_snippet("https://example.com/test")

        assert "mailto:" not in result
        assert "linkedin.com" not in result
        assert "oil and gas" in result

    def test_fallback_on_jina_error(self):
        """When Jina returns non-200, falls back to direct fetch."""
        mock_jina_response = MagicMock()
        mock_jina_response.status_code = 429  # rate limited

        mock_direct_response = MagicMock()
        mock_direct_response.status_code = 200
        mock_direct_response.text = (
            "<html><body><p>The energy sector saw record investment in carbon capture "
            "technology during Q1 2026, with over $4 billion committed across 12 new projects.</p></body></html>"
        )

        call_count = 0

        def fake_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_jina_response
            return mock_direct_response

        with patch("vi_engine.extract.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = fake_get
            mock_client_cls.return_value = mock_client

            result = fetch_snippet("https://example.com/energy")

        assert "carbon capture" in result
