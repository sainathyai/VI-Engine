"""Publisher registry — returns the right Publisher instance for a platform name."""

from __future__ import annotations

from vi_engine.config import (
    GHOST_ADMIN_API_KEY,
    GHOST_ADMIN_URL,
    WORDPRESS_APP_PASSWORD,
    WORDPRESS_SITE_URL,
    WORDPRESS_USERNAME,
    X_ACCESS_TOKEN,
    X_ACCESS_TOKEN_SECRET,
    X_API_KEY,
    X_API_SECRET,
)

from .base import Publisher
from .ghost import GhostPublisher
from .twitter import XPublisher
from .wordpress import WordPressPublisher


def get_publisher(platform: str) -> Publisher | None:
    """Return a configured Publisher for *platform*, or None if not configured."""
    if platform == "ghost":
        if GHOST_ADMIN_URL and GHOST_ADMIN_API_KEY:
            return GhostPublisher(GHOST_ADMIN_URL, GHOST_ADMIN_API_KEY)
    elif platform == "wordpress":
        if WORDPRESS_SITE_URL and WORDPRESS_USERNAME and WORDPRESS_APP_PASSWORD:
            return WordPressPublisher(WORDPRESS_SITE_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD)
    elif platform == "twitter":
        if X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET:
            return XPublisher(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
    return None
