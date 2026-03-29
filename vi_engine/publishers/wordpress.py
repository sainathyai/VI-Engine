"""WordPress REST API publisher.

Requires WordPress with Application Passwords enabled (WP 5.6+, no plugin needed).

Setup:
  1. WP Admin → Users → Profile → Application Passwords → Add new
  2. Set WORDPRESS_SITE_URL=https://your-site.com
  3. Set WORDPRESS_USERNAME=admin
  4. Set WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx  (spaces ok, will be stripped)
"""

from __future__ import annotations

import base64

import httpx

from .base import Publisher


class WordPressPublisher(Publisher):
    """Publish posts to WordPress via the REST API (Application Passwords auth)."""

    def __init__(self, site_url: str, username: str, app_password: str) -> None:
        self._url = site_url.rstrip("/")
        creds = f"{username}:{app_password.replace(' ', '')}"
        self._auth = "Basic " + base64.b64encode(creds.encode()).decode()

    @property
    def name(self) -> str:
        return "wordpress"

    def publish(self, title: str, html: str, tags: list[str] | None = None) -> str:
        payload: dict = {
            "title": title,
            "content": html,
            "status": "publish",
        }
        resp = httpx.post(
            f"{self._url}/wp-json/wp/v2/posts",
            json=payload,
            headers={"Authorization": self._auth},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("link", "")