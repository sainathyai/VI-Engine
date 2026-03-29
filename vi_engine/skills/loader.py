"""Skills loader — composes base + voice + industry + platform skill files into a system prompt."""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).parent

# ── Registry ────────────────────────────────────────────────────────────────

VOICES: dict[str, str] = {
    "skeptical_analyst": "voices/skeptical_analyst.md",
    "pragmatic_operator": "voices/pragmatic_operator.md",
    "contrarian": "voices/contrarian.md",
    "enthusiastic": "voices/enthusiastic.md",
    "policy_wonk": "voices/policy_wonk.md",
}

INDUSTRIES: dict[str, str] = {
    "oil_gas_energy": "industries/oil_gas_energy.md",
    "tech": "industries/tech.md",
    "fintech": "industries/fintech.md",
    "edtech": "industries/edtech.md",
}

PLATFORMS: dict[str, str] = {
    "blog": "platforms/blog.md",
    "linkedin": "platforms/linkedin.md",
    "twitter": "platforms/twitter.md",
}

# Human-readable labels for UI dropdowns
VOICE_LABELS: dict[str, str] = {
    "skeptical_analyst": "Skeptical Analyst",
    "pragmatic_operator": "Pragmatic Operator",
    "contrarian": "Contrarian",
    "enthusiastic": "Enthusiastic",
    "policy_wonk": "Policy Wonk",
}

INDUSTRY_LABELS: dict[str, str] = {
    "oil_gas_energy": "Oil, Gas & Energy",
    "tech": "Technology",
    "fintech": "FinTech",
    "edtech": "EdTech",
}

PLATFORM_LABELS: dict[str, str] = {
    "blog": "Blog Post",
    "linkedin": "LinkedIn",
    "twitter": "X / Twitter Thread",
}


# ── Loader ──────────────────────────────────────────────────────────────────

def _load(relative_path: str) -> str:
    path = SKILLS_DIR / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(
    *,
    voice: str | None = None,
    industry: str | None = None,
    platform: str | None = None,
) -> str:
    """Compose a system prompt from base voice + optional voice/industry/platform skills.

    Args:
        voice:    key from VOICES (e.g. "skeptical_analyst")
        industry: key from INDUSTRIES (e.g. "oil_gas_energy")
        platform: key from PLATFORMS (e.g. "blog", "linkedin", "twitter")

    Returns:
        A single string to use as the LLM system prompt.
    """
    sections: list[str] = []

    # Always include base voice
    base = _load("base/voice.md")
    if base:
        sections.append(base)

    # Editorial voice
    if voice and voice in VOICES:
        skill = _load(VOICES[voice])
        if skill:
            sections.append(skill)

    # Industry context
    if industry and industry in INDUSTRIES:
        skill = _load(INDUSTRIES[industry])
        if skill:
            sections.append(skill)

    # Platform formatting rules
    if platform and platform in PLATFORMS:
        skill = _load(PLATFORMS[platform])
        if skill:
            sections.append(skill)

    return "\n\n---\n\n".join(sections)


def list_voices() -> list[dict[str, str]]:
    """Return all available voices as [{"key": ..., "label": ...}] for UI dropdowns."""
    return [{"key": k, "label": v} for k, v in VOICE_LABELS.items()]


def list_industries() -> list[dict[str, str]]:
    return [{"key": k, "label": v} for k, v in INDUSTRY_LABELS.items()]


def list_platforms() -> list[dict[str, str]]:
    return [{"key": k, "label": v} for k, v in PLATFORM_LABELS.items()]
