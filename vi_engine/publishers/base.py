"""Abstract base class for CMS/platform publishers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Publisher(ABC):
    """Publish a newsletter to a CMS or social platform."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform identifier (e.g. 'ghost', 'wordpress')."""
        ...

    @abstractmethod
    def publish(self, title: str, html: str, tags: list[str] | None = None) -> str:
        """Publish content and return the live URL (or empty string on failure)."""
        ...