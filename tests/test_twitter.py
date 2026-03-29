"""Tests for X (Twitter) publisher."""

from unittest.mock import MagicMock, patch

import pytest

from vi_engine.publishers.twitter import XPublisher, _parse_thread


# ── _parse_thread ───────────────────────────────────────────────────────────

class TestParseThread:
    def test_splits_on_dividers(self):
        text = "Tweet one\n\n---\n\nTweet two\n\n---\n\nTweet three"
        result = _parse_thread(text)
        assert result == ["Tweet one", "Tweet two", "Tweet three"]

    def test_strips_surrounding_whitespace(self):
        text = "\n\n  Tweet one  \n\n---\n\n  Tweet two  \n\n"
        result = _parse_thread(text)
        assert result == ["Tweet one", "Tweet two"]

    def test_skips_empty_segments(self):
        text = "Tweet one\n\n---\n\n\n\n---\n\nTweet two"
        result = _parse_thread(text)
        assert result == ["Tweet one", "Tweet two"]

    def test_truncates_long_tweets(self):
        long_tweet = "A" * 300
        result = _parse_thread(long_tweet)
        assert len(result[0]) == 280
        assert result[0].endswith("…")

    def test_allows_exactly_280_chars(self):
        tweet = "B" * 280
        result = _parse_thread(tweet)
        assert result[0] == tweet

    def test_single_tweet_no_divider(self):
        result = _parse_thread("Just one tweet here.")
        assert result == ["Just one tweet here."]

    def test_empty_input_returns_empty(self):
        assert _parse_thread("") == []
        assert _parse_thread("   \n\n   ") == []


# ── XPublisher ──────────────────────────────────────────────────────────────

def _make_publisher():
    """Return an XPublisher with a fully mocked tweepy.Client."""
    with patch("vi_engine.publishers.twitter.tweepy.Client") as mock_cls:
        publisher = XPublisher(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
        )
        mock_client = mock_cls.return_value
        publisher._client = mock_client
        return publisher, mock_client


class TestXPublisher:
    def test_name(self):
        publisher, _ = _make_publisher()
        assert publisher.name == "twitter"

    def test_single_tweet_posted(self):
        publisher, mock_client = _make_publisher()
        mock_client.create_tweet.return_value = MagicMock(data={"id": "111"})

        url = publisher.publish("Title", "Just a single tweet.")

        mock_client.create_tweet.assert_called_once_with(text="Just a single tweet.")
        assert "111" in url

    def test_thread_posted_as_replies(self):
        publisher, mock_client = _make_publisher()
        mock_client.create_tweet.side_effect = [
            MagicMock(data={"id": "100"}),
            MagicMock(data={"id": "101"}),
            MagicMock(data={"id": "102"}),
        ]

        content = "First tweet\n\n---\n\nSecond tweet\n\n---\n\nThird tweet"
        url = publisher.publish("Title", content)

        calls = mock_client.create_tweet.call_args_list
        assert len(calls) == 3
        # First tweet: no reply_to
        assert calls[0].kwargs.get("text") == "First tweet"
        assert "in_reply_to_tweet_id" not in calls[0].kwargs
        # Second tweet: replies to first
        assert calls[1].kwargs.get("in_reply_to_tweet_id") == "100"
        # Third tweet: replies to second
        assert calls[2].kwargs.get("in_reply_to_tweet_id") == "101"

        assert "100" in url

    def test_returns_url_of_first_tweet(self):
        publisher, mock_client = _make_publisher()
        mock_client.create_tweet.return_value = MagicMock(data={"id": "999"})

        url = publisher.publish("Title", "One tweet only.")
        assert url == "https://x.com/i/web/status/999"

    def test_raises_on_empty_content(self):
        publisher, mock_client = _make_publisher()
        with pytest.raises(ValueError, match="empty"):
            publisher.publish("Title", "")

    def test_tags_param_accepted_but_unused(self):
        """Tags are part of the Publisher interface but X doesn't use them."""
        publisher, mock_client = _make_publisher()
        mock_client.create_tweet.return_value = MagicMock(data={"id": "123"})
        # Should not raise
        publisher.publish("Title", "Tweet text.", tags=["tag1", "tag2"])
        mock_client.create_tweet.assert_called_once()

    def test_api_error_propagates(self):
        publisher, mock_client = _make_publisher()
        mock_client.create_tweet.side_effect = Exception("Rate limit exceeded")

        with pytest.raises(Exception, match="Rate limit"):
            publisher.publish("Title", "A tweet.")


# ── get_publisher registry ──────────────────────────────────────────────────

class TestGetPublisher:
    def test_returns_none_when_not_configured(self):
        from vi_engine.publishers import get_publisher
        with (
            patch("vi_engine.publishers.X_API_KEY", ""),
            patch("vi_engine.publishers.X_API_SECRET", ""),
            patch("vi_engine.publishers.X_ACCESS_TOKEN", ""),
            patch("vi_engine.publishers.X_ACCESS_TOKEN_SECRET", ""),
        ):
            assert get_publisher("twitter") is None

    def test_returns_publisher_when_configured(self):
        from vi_engine.publishers import get_publisher
        with (
            patch("vi_engine.publishers.X_API_KEY", "key"),
            patch("vi_engine.publishers.X_API_SECRET", "secret"),
            patch("vi_engine.publishers.X_ACCESS_TOKEN", "token"),
            patch("vi_engine.publishers.X_ACCESS_TOKEN_SECRET", "tsecret"),
            patch("vi_engine.publishers.twitter.tweepy.Client"),
        ):
            publisher = get_publisher("twitter")
            assert publisher is not None
            assert publisher.name == "twitter"
