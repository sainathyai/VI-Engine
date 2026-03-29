"""Auto-categorize candidates by domain and content type.

Two modes:
  - classify_by_keywords(): fast, no API call, runs during collection
  - classify_by_llm(): uses Haiku for accurate tagging, runs during enrich
"""

from __future__ import annotations

import re

from anthropic import Anthropic

from vi_engine.config import FILTER_MODEL

# ─── Keyword-based (instant, free) ────────────────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "AI & Machine Learning": [
        "ai ", "artificial intelligence", "machine learning", "llm", "gpt",
        "claude", "gemini", "neural", "transformer", "deep learning",
        "openai", "anthropic", "hugging face", "diffusion", "embedding",
        "fine-tun", "rlhf", "rag ", "agent", "copilot", "chatbot",
        "computer vision", "nlp", "large language",
    ],
    "Cybersecurity": [
        "security", "hack", "breach", "malware", "ransomware", "phishing",
        "vulnerability", "cve-", "exploit", "zero-day", "compromised",
        "cybersecurity", "authentication", "encryption", "ddos",
    ],
    "Fintech & Crypto": [
        "fintech", "crypto", "bitcoin", "ethereum", "blockchain", "defi",
        "payment", "banking", "aml ", "compliance", "regulation", "sec ",
        "stablecoin", "cbdc", "neobank",
    ],
    "Gaming": [
        "game", "gaming", "steam", "playstation", "xbox", "nintendo",
        "fortnite", "esports", "unreal engine", "unity ", "gpu ",
    ],
    "Cloud & Infrastructure": [
        "aws ", "azure", "gcp ", "kubernetes", "docker", "serverless",
        "cloud ", "infrastructure", "devops", "terraform", "ci/cd",
    ],
    "Software Dev": [
        "programming", "developer", "open source", "github", "rust ",
        "python ", "javascript", "typescript", "react ", "linux",
        "compiler", "framework", "api ", "sdk ",
    ],
    "Hardware & Chips": [
        "chip", "semiconductor", "nvidia", "amd ", "intel ", "arm ",
        "cpu ", "gpu ", "apple silicon", "quantum",
    ],
    "Business & Startups": [
        "startup", "funding", "acquisition", "ipo ", "layoff", "valuation",
        "venture capital", "series a", "series b", "unicorn",
    ],
}

CONTENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "Product Launch": [
        "launch", "introducing", "announcing", "released", "now available",
        "new feature", "unveil", "debut", "ships", "rolls out",
    ],
    "Breaking News": [
        "breaking", "just in", "urgent", "compromised", "breach", "outage",
        "down ", "incident", "emergency",
    ],
    "Analysis & Opinion": [
        "analysis", "opinion", "why ", "how ", "what we learned",
        "deep dive", "explained", "review", "perspective", "state of",
    ],
    "Tutorial & Guide": [
        "how to", "tutorial", "guide", "step by step", "build a",
        "getting started", "walkthrough",
    ],
    "Research & Paper": [
        "paper", "research", "study", "arxiv", "findings", "benchmark",
        "dataset", "evaluation",
    ],
    "Industry Report": [
        "report", "survey", "trends", "forecast", "market", "quarterly",
        "annual",
    ],
}


def _match_keywords(text: str, keyword_map: dict[str, list[str]]) -> str:
    text_lower = text.lower()
    best_cat = ""
    best_count = 0
    for cat, keywords in keyword_map.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_cat = cat
    return best_cat if best_count > 0 else ""


def classify_by_keywords(title: str, description: str = "") -> tuple[str, str]:
    """Return (category, content_type) based on keyword matching."""
    text = f"{title} {description}"
    category = _match_keywords(text, DOMAIN_KEYWORDS)
    content_type = _match_keywords(text, CONTENT_TYPE_KEYWORDS)
    return category, content_type


# ─── LLM-based (accurate, costs ~$0.0005 per call) ────────

CLASSIFY_SYSTEM = """You are a news categorizer. Given an article title and snippet, respond with exactly two lines:
DOMAIN: <one of: AI & Machine Learning, Cybersecurity, Fintech & Crypto, Gaming, Cloud & Infrastructure, Software Dev, Hardware & Chips, Business & Startups, Science & Research, Policy & Regulation, Other>
TYPE: <one of: Product Launch, Breaking News, Analysis & Opinion, Tutorial & Guide, Research & Paper, Industry Report, Company Update, Other>

Be precise. Pick the single best fit for each."""


def classify_by_llm(client: Anthropic, title: str, snippet: str) -> tuple[str, str]:
    """Return (category, content_type) via Haiku classification."""
    msg = client.messages.create(
        model=FILTER_MODEL,
        max_tokens=60,
        system=CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": f"Title: {title}\n\nSnippet: {snippet[:500]}"}],
    )
    text = ""
    for block in msg.content:
        if block.type == "text":
            text += block.text

    category = ""
    content_type = ""
    for line in text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("DOMAIN:"):
            category = line.split(":", 1)[1].strip()
        elif line.upper().startswith("TYPE:"):
            content_type = line.split(":", 1)[1].strip()
    return category, content_type
