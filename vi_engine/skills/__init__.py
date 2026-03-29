"""Skills system — layered prompt composition for human-style editorial content."""

from .loader import (
    INDUSTRIES,
    PLATFORMS,
    VOICES,
    build_system_prompt,
    list_industries,
    list_platforms,
    list_voices,
)

__all__ = [
    "build_system_prompt",
    "list_voices",
    "list_industries",
    "list_platforms",
    "VOICES",
    "INDUSTRIES",
    "PLATFORMS",
]
