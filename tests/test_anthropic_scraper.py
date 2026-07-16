"""
Tests for app/scrapers/anthropic.py

Run from the project root:
    uv run pytest tests/test_anthropic_scraper.py -v
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import feedparser

from app.scrapers.anthropic import AnthropicScraper


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _build_rss(items: list[dict]) -> str:
    entries_xml = "\n".join(
        f"""
        <item>
          <title>{item['title']}</title>
          <link>{item['link']}</link>
          <guid>{item['link']}</guid>
          <pubDate>{_rfc822(item['pubDate'])}</pubDate>
        </item>
        """
        for item in items
    )
    return f"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Anthropic Test Feed</title>
    {entries_xml}
  </channel>
</rss>
"""


def _make_scraper() -> AnthropicScraper:
    # DocumentConverter() is only used by url_to_markdown, not get_articles,
    # but __init__ constructs it eagerly — mock it out so tests don't pull
    # in docling's model-loading machinery.
    with patch("app.scrapers.anthropic.DocumentConverter", MagicMock()):
        return AnthropicScraper()


def test_recent_article_with_real_timestamp_is_included():
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {"title": "Recent", "link": "https://a.com/1", "pubDate": now - timedelta(hours=2)},
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    # fetch_feed is mocked to return the same content for all 3 rss_urls,
    # but seen_guids is shared across that loop, so the duplicate guid
    # from source 2 and 3 gets correctly skipped — only 1 survives.
    assert len(articles) == 1
    assert articles[0].guid == "https://a.com/1"


def test_old_article_with_real_timestamp_is_excluded():
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {"title": "Old", "link": "https://a.com/2", "pubDate": now - timedelta(hours=48)},
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    assert articles == []


def test_midnight_timestamp_from_today_is_included_even_if_hour_has_passed():
    """This is the actual bug we hit in production: the GitHub mirror feed
    only records a DATE (00:00:00), not a real publish time. An article
    dated 'today' should count as recent even if today's midnight is
    technically more than `hours` before the exact run time."""
    now = datetime.now(timezone.utc)
    todays_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    xml = _build_rss([
        {"title": "Today, midnight-only timestamp", "link": "https://a.com/3", "pubDate": todays_midnight},
    ])
    scraper = _make_scraper()

    # A short window that would normally exclude a plain midnight timestamp
    # if today's midnight was more than `hours` hours ago
    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=1)

    # Same dedup note as above: 1 survivor across the 3 mocked sources
    assert len(articles) == 1
    assert articles[0].guid == "https://a.com/3"


def test_midnight_timestamp_from_yesterday_is_excluded():
    """Same midnight-only quirk, but for a genuinely old article — the
    calendar-date fallback should not become so lenient it never expires
    anything."""
    now = datetime.now(timezone.utc)
    yesterdays_midnight = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    xml = _build_rss([
        {"title": "Yesterday, midnight-only timestamp", "link": "https://a.com/4", "pubDate": yesterdays_midnight},
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=1)

    assert articles == []


def test_dedup_across_the_three_rss_urls():
    """get_articles loops over 3 mirror feeds (news/research/engineering).
    The same guid appearing in more than one must only be counted once."""
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {"title": "Same article", "link": "https://a.com/dup", "pubDate": now - timedelta(hours=1)},
    ])
    scraper = _make_scraper()
    assert len(scraper.rss_urls) == 3

    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    # Even though the same guid is present in all 3 mocked source feeds,
    # seen_guids is shared across the whole loop, so only 1 survives.
    assert len(articles) == 1
    assert articles[0].guid == "https://a.com/dup"


def test_empty_feed_does_not_raise():
    scraper = _make_scraper()
    with patch("app.scrapers.anthropic.fetch_feed", return_value=feedparser.parse("")):
        articles = scraper.get_articles(hours=24)
    assert articles == []