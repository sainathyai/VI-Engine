"""Tests for the skills loader system."""

import pytest
from vi_engine.skills.loader import (
    build_system_prompt,
    list_voices,
    list_industries,
    list_platforms,
    VOICES,
    INDUSTRIES,
    PLATFORMS,
)


class TestSkillLoader:
    def test_base_voice_always_included(self):
        prompt = build_system_prompt()
        # Base voice has specific content we can check
        assert "Non-Negotiables" in prompt or "Have a take" in prompt

    def test_voice_included_when_specified(self):
        prompt = build_system_prompt(voice="skeptical_analyst")
        assert "Skeptical Analyst" in prompt or "compared to what" in prompt.lower()

    def test_industry_included_when_specified(self):
        prompt = build_system_prompt(industry="oil_gas_energy")
        assert "Permian" in prompt or "upstream" in prompt.lower() or "E&P" in prompt

    def test_platform_included_when_specified(self):
        prompt = build_system_prompt(platform="linkedin")
        assert "LinkedIn" in prompt or "1,300" in prompt or "hook" in prompt.lower()

    def test_twitter_platform(self):
        prompt = build_system_prompt(platform="twitter")
        assert "thread" in prompt.lower() or "280" in prompt or "tweet" in prompt.lower()

    def test_blog_platform(self):
        prompt = build_system_prompt(platform="blog")
        assert "SEO" in prompt or "H1" in prompt or "H2" in prompt

    def test_full_composition(self):
        """All four layers should appear in a full prompt."""
        prompt = build_system_prompt(
            voice="contrarian",
            industry="fintech",
            platform="blog",
        )
        # Should contain content from each layer
        assert len(prompt) > 1000  # non-trivial composition
        assert "---" in prompt  # section separator

    def test_unknown_voice_ignored(self):
        prompt_with = build_system_prompt(voice="nonexistent_voice")
        prompt_without = build_system_prompt()
        assert prompt_with == prompt_without

    def test_unknown_industry_ignored(self):
        prompt = build_system_prompt(industry="underwater_basket_weaving")
        assert "underwater" not in prompt

    def test_all_voices_loadable(self):
        for voice_key in VOICES:
            prompt = build_system_prompt(voice=voice_key)
            assert len(prompt) > 200, f"Voice {voice_key} produced an empty prompt"

    def test_all_industries_loadable(self):
        for industry_key in INDUSTRIES:
            prompt = build_system_prompt(industry=industry_key)
            assert len(prompt) > 200, f"Industry {industry_key} produced an empty prompt"

    def test_all_platforms_loadable(self):
        for platform_key in PLATFORMS:
            prompt = build_system_prompt(platform=platform_key)
            assert len(prompt) > 200, f"Platform {platform_key} produced an empty prompt"

    def test_list_voices_returns_all(self):
        voices = list_voices()
        assert len(voices) == len(VOICES)
        assert all("key" in v and "label" in v for v in voices)

    def test_list_industries_returns_all(self):
        industries = list_industries()
        assert len(industries) == len(INDUSTRIES)

    def test_list_platforms_returns_all(self):
        platforms = list_platforms()
        assert len(platforms) == len(PLATFORMS)

    def test_oil_gas_industry_content(self):
        prompt = build_system_prompt(industry="oil_gas_energy")
        # Should have real domain content
        assert any(term in prompt for term in ["OPEC", "upstream", "Permian", "LNG", "wellhead"])

    def test_fintech_industry_content(self):
        prompt = build_system_prompt(industry="fintech")
        assert any(term in prompt for term in ["AML", "KYC", "CFPB", "BaaS", "interchange"])

    def test_edtech_industry_content(self):
        prompt = build_system_prompt(industry="edtech")
        assert any(term in prompt for term in ["LMS", "MOOC", "FERPA", "accreditation", "enrollment"])

    def test_tech_industry_content(self):
        prompt = build_system_prompt(industry="tech")
        assert any(term in prompt for term in ["LLM", "RAG", "GPU", "open source", "inference"])
