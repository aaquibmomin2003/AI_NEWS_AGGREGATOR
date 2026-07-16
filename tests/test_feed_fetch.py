"""
Tests for app/utils/feed_fetch.py

Run from the project root:
    uv run pytest tests/test_feed_fetch.py -v
"""

from unittest.mock import patch, MagicMock
import requests

from app.utils.feed_fetch import fetch_feed


MINIMAL_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Test Article</title>
      <link>https://example.com/article-1</link>
      <guid>https://example.com/article-1</guid>
      <pubDate>Mon, 13 Jul 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _mock_response(status_code=200, content=b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.side_effect = None
    return resp


def test_fetch_feed_success_returns_parsed_entries():
    with patch("app.utils.feed_fetch.requests.get") as mock_get:
        mock_get.return_value = _mock_response(200, MINIMAL_RSS.encode())
        feed = fetch_feed("https://example.com/rss.xml")

    assert len(feed.entries) == 1
    assert feed.entries[0].title == "Test Article"
    mock_get.assert_called_once()
    # Confirm we send a real User-Agent, not requests' default (some
    # servers, like YouTube, are known to reject bare/default clients)
    _, kwargs = mock_get.call_args
    assert "User-Agent" in kwargs["headers"]
    assert "python" not in kwargs["headers"]["User-Agent"].lower()


def test_fetch_feed_ssl_error_returns_empty_feed_not_exception():
    with patch("app.utils.feed_fetch.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.SSLError("certificate has expired")
        feed = fetch_feed("https://example.com/rss.xml")

    # Must not raise — callers rely on `if not feed.entries` never crashing
    assert feed.entries == []


def test_fetch_feed_ssl_error_does_not_retry():
    """SSL errors aren't transient — retrying won't fix an expired cert,
    so we should fail fast (one call only) rather than wasting attempts."""
    with patch("app.utils.feed_fetch.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.SSLError("certificate has expired")
        fetch_feed("https://example.com/rss.xml", retries=2)

    assert mock_get.call_count == 1


def test_fetch_feed_retries_on_5xx_then_succeeds():
    with patch("app.utils.feed_fetch.requests.get") as mock_get, \
         patch("app.utils.feed_fetch.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _mock_response(500),
            _mock_response(200, MINIMAL_RSS.encode()),
        ]
        feed = fetch_feed("https://example.com/rss.xml", retries=2)

    assert len(feed.entries) == 1
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()  # backed off exactly once before succeeding


def test_fetch_feed_exhausts_retries_returns_empty_feed():
    with patch("app.utils.feed_fetch.requests.get") as mock_get, \
         patch("app.utils.feed_fetch.time.sleep"):
        mock_get.return_value = _mock_response(500)
        feed = fetch_feed("https://example.com/rss.xml", retries=2)

    assert feed.entries == []
    assert mock_get.call_count == 3  # initial attempt + 2 retries


def test_fetch_feed_connection_error_retries_then_gives_up():
    with patch("app.utils.feed_fetch.requests.get") as mock_get, \
         patch("app.utils.feed_fetch.time.sleep"):
        mock_get.side_effect = requests.exceptions.ConnectionError("blocked")
        feed = fetch_feed("https://example.com/rss.xml", retries=1)

    assert feed.entries == []
    assert mock_get.call_count == 2  # initial + 1 retry


def test_fetch_feed_4xx_does_not_retry():
    """A real 404 (page doesn't exist) is not transient — don't waste retries."""
    with patch("app.utils.feed_fetch.requests.get") as mock_get, \
         patch("app.utils.feed_fetch.time.sleep") as mock_sleep:
        mock_get.return_value = _mock_response(404)
        feed = fetch_feed("https://example.com/rss.xml", retries=2)

    assert feed.entries == []
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()