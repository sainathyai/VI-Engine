"""Anthropic: filter (Haiku) + synthesis (Sonnet). Prompts live here — tune in Phase 1."""

from __future__ import annotations

from anthropic import Anthropic

from vi_engine.config import (
    ANTHROPIC_API_KEY,
    DOMAIN_TAG,
    FILTER_MODEL,
    SYNTHESIS_MODEL,
)
from vi_engine.skills import build_system_prompt


FILTER_SYSTEM = """You are a strict editor for a vertical intelligence brief.
Given a brief that may contain full markdown or only headline/metadata, reply with exactly one word: KEEP or DISCARD.
KEEP only if the title/headline context suggests an actionable regulatory, compliance, or fintech market signal for a professional audience (not generic SEO fluff)."""


SYNTHESIS_SYSTEM = """You write structured analysis for a niche news site.
Output valid Markdown with: H1 title, short executive summary, H2 sections with clear SEO-friendly headers, bullet key takeaways, and a "Sources" line citing the original page. Be factual; do not invent citations beyond the provided text."""


PREVIEW_SYSTEM = """You are an editorial assistant. Given the full text of a web page, write a concise preview (3-5 sentences) that helps a human editor decide whether this article is worth including in a professional newsletter.

Cover: What is the article about? What is the key insight or news? Who is the target audience? Why might it matter?

Be specific and factual. Do not add opinions or recommendations. Do not use markdown formatting."""


def get_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("Set ANTHROPIC_API_KEY in .env")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _extract_text(msg) -> str:
    parts: list[str] = []
    for block in msg.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def filter_keep_or_discard(client: Anthropic, markdown: str) -> bool:
    msg = client.messages.create(
        model=FILTER_MODEL,
        max_tokens=10,
        system=FILTER_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Domain focus: {DOMAIN_TAG}\n\n---\n\n{markdown[:120_000]}",
            }
        ],
    )
    return _extract_text(msg).upper().startswith("KEEP")


def synthesize_article(client: Anthropic, source_url: str, markdown: str) -> str:
    msg = client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=4096,
        system=SYNTHESIS_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Source URL: {source_url}\n\n---\n\n{markdown[:180_000]}",
            }
        ],
    )
    return _extract_text(msg)


def generate_preview(client: Anthropic, markdown: str) -> str:
    msg = client.messages.create(
        model=FILTER_MODEL,
        max_tokens=300,
        system=PREVIEW_SYSTEM,
        messages=[{"role": "user", "content": markdown[:60_000]}],
    )
    return _extract_text(msg)


# ── Skills-aware generation ──────────────────────────────────────────────────

def generate_platform_content(
    client: Anthropic,
    *,
    source_content: str,
    platform: str,
    voice: str | None = None,
    industry: str | None = None,
    title: str = "",
) -> str:
    """Generate platform-specific content (blog, linkedin, twitter) using the skills system.

    Args:
        client:         Anthropic client
        source_content: The synthesized article text (markdown) to rewrite for the platform
        platform:       "blog" | "linkedin" | "twitter"
        voice:          editorial voice key (e.g. "skeptical_analyst")
        industry:       industry key (e.g. "oil_gas_energy")
        title:          optional article title for context

    Returns:
        Platform-formatted content string ready for preview or publishing.
    """
    system_prompt = build_system_prompt(
        voice=voice,
        industry=industry,
        platform=platform,
    )

    platform_instruction = {
        "blog": (
            "Rewrite the following article as a polished long-form blog post following all "
            "the format and voice rules in your instructions. Output clean markdown."
        ),
        "linkedin": (
            "Write a LinkedIn post based on the key insight in the following article. "
            "Follow the format and voice rules in your instructions. Output plain text only — "
            "no markdown, no bullet points, no headers."
        ),
        "twitter": (
            "Write an X (Twitter) thread based on the following article. "
            "Follow the format and voice rules in your instructions. "
            "Separate each tweet with a blank line and --- divider."
        ),
    }.get(platform, "Rewrite the following content for your platform.")

    user_content = f"{platform_instruction}\n\n"
    if title:
        user_content += f"Title: {title}\n\n"
    user_content += f"---\n\n{source_content[:120_000]}"

    msg = client.messages.create(
        model=SYNTHESIS_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return _extract_text(msg)
