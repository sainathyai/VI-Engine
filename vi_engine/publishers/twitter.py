"""X (Twitter) publisher — posts a thread via the X API v2.

Setup (X Developer Portal → your app → Keys and Tokens):
  1. Create a project + app at developer.twitter.com
  2. Enable "Read and Write" permissions (User Auth Settings)
  3. Generate: API Key, API Secret, Access Token, Access Token Secret
  4. Set env vars: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET

Free tier: 500 tweets/month — enough for several threads per week.
"""

from __future__ import annotations

import re

import tweepy

from .base import Publisher


def _parse_thread(text: str) -> list[str]:
    """Split `---`-delimited thread text into individual tweet strings.

    Strips blank lines around each tweet and skips empty segments.
    Truncates any tweet that exceeds 280 chars to 277 + '…'.
    """
    segments = re.split(r"(?m)^\s*---\s*$", text)
    tweets: list[str] = []
    for seg in segments:
        tweet = seg.strip()
        if not tweet:
            continue
        if len(tweet) > 280:
            tweet = tweet[:279] + "…"
        tweets.append(tweet)
    return tweets


class XPublisher(Publisher):
    """Publish a thread to X (Twitter) using OAuth 1.0a User Context."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
    ) -> None:
        self._client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    @property
    def name(self) -> str:
        return "twitter"

    def publish(self, title: str, html: str, tags: list[str] | None = None) -> str:
        """Post a thread. `html` is treated as plain-text thread content
        with tweets separated by `---` dividers (as produced by the twitter skill).

        Returns the URL of the first tweet.
        """
        tweets = _parse_thread(html)
        if not tweets:
            raise ValueError("No tweet content found — thread is empty after parsing.")

        # Post first tweet
        resp = self._client.create_tweet(text=tweets[0])
        first_id: str = str(resp.data["id"])
        prev_id = first_id

        # Chain the rest as replies
        for tweet_text in tweets[1:]:
            resp = self._client.create_tweet(
                text=tweet_text,
                in_reply_to_tweet_id=prev_id,
            )
            prev_id = str(resp.data["id"])

        return f"https://x.com/i/web/status/{first_id}"
