"""
Tests for app/scrapers/openai.py

Run from the project root:
    uv run pytest tests/test_openai_scraper.py -v
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import feedparser

from app.scrapers.openai import OpenAIScraper


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
          <category>{item.get('category', '')}</category>
        </item>
        """
        for item in items
    )
    return f"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>OpenAI Test Feed</title>
    {entries_xml}
  </channel>
</rss>
"""


def _make_scraper() -> OpenAIScraper:
    with patch("app.scrapers.openai.DocumentConverter", MagicMock()):
        return OpenAIScraper()


def test_recent_article_is_included_with_correct_fields():
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {
            "title": "New Model Release",
            "link": "https://openai.com/news/new-model",
            "pubDate": now - timedelta(hours=3),
            "category": "product",
        },
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.openai.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    assert len(articles) == 1
    article = articles[0]
    assert article.title == "New Model Release"
    assert article.url == "https://openai.com/news/new-model"
    assert article.guid == "https://openai.com/news/new-model"
    assert article.category == "product"


def test_old_article_outside_window_is_excluded():
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {"title": "Old news", "link": "https://openai.com/news/old", "pubDate": now - timedelta(days=5)},
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.openai.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    assert articles == []


def test_mixed_recent_and_old_only_returns_recent():
    now = datetime.now(timezone.utc)
    xml = _build_rss([
        {"title": "Recent", "link": "https://openai.com/news/recent", "pubDate": now - timedelta(hours=1)},
        {"title": "Old", "link": "https://openai.com/news/old", "pubDate": now - timedelta(days=10)},
    ])
    scraper = _make_scraper()

    with patch("app.scrapers.openai.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == "Recent"


def test_empty_feed_returns_empty_list_without_error():
    scraper = _make_scraper()
    with patch("app.scrapers.openai.fetch_feed", return_value=feedparser.parse("")):
        articles = scraper.get_articles(hours=24)
    assert articles == []


def test_entry_missing_published_date_is_skipped_not_crashed():
    """An entry with no parsable pubDate should be silently skipped,
    not raise an AttributeError."""
    xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>OpenAI Test Feed</title>
    <item>
      <title>No date</title>
      <link>https://openai.com/news/no-date</link>
      <guid>https://openai.com/news/no-date</guid>
    </item>
  </channel>
</rss>
"""
    scraper = _make_scraper()
    with patch("app.scrapers.openai.fetch_feed", return_value=feedparser.parse(xml)):
        articles = scraper.get_articles(hours=24)
    assert articles == []