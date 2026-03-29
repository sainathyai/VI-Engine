"""Ghost CMS Admin API publisher.

Requires Ghost v4+ with Admin API enabled.

Setup:
  1. Ghost Admin → Integrations → Add custom integration → copy Admin API Key
  2. Set GHOST_ADMIN_URL=https://your-blog.ghost.io
  3. Set GHOST_ADMIN_API_KEY=<key_id>:<secret>
"""

from __future__ import annotations

import json
import time

import httpx
import jwt

from .base import Publisher


def _mobiledoc_from_html(html: str) -> str:
    """Wrap arbitrary HTML in a Ghost mobiledoc HTML card (works on all Ghost versions)."""
    doc = {
        "version": "0.3.1",
        "atoms": [],
        "cards": [["html", {"html": html}]],
        "markups": [],
        "sections": [[10, 0]],
    }
    return json.dumps(doc)


def _make_token(key_id: str, secret_hex: str) -> str:
    iat = int(time.time())
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
    return jwt.encode(
        payload,
        bytes.fromhex(secret_hex),
        algorithm="HS256",
        headers={"kid": key_id},
    )


class GhostPublisher(Publisher):
    """Publish posts to Ghost via the Admin API."""

    def __init__(self, admin_url: str, admin_api_key: str) -> None:
        """
        admin_url     – e.g. https://your-blog.ghost.io
        admin_api_key – format <key_id>:<hex_secret>  (from Ghost Integrations page)
        """
        self._url = admin_url.rstrip("/")
        key_id, secret = admin_api_key.split(":", 1)
        self._key_id = key_id
        self._secret = secret

    @property
    def name(self) -> str:
        return "ghost"

    def publish(self, title: str, html: str, tags: list[str] | None = None) -> str:
        token = _make_token(self._key_id, self._secret)
        payload = {
            "posts": [
                {
                    "title": title,
                    "mobiledoc": _mobiledoc_from_html(html),
                    "status": "published",
                    "tags": [{"name": t} for t in (tags or [])],
                }
            ]
        }
        resp = httpx.post(
            f"{self._url}/ghost/api/admin/posts/",
            json=payload,
            headers={"Authorization": f"Ghost {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["posts"][0].get("url", "")