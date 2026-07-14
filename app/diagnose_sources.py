"""
Diagnostic: shows the raw state of every scraper's source data, ignoring
the `hours` cutoff, so you can tell "no new content" apart from "something
is misconfigured or the source is stale."

Run with: uv run python -m app.diagnose_sources   (adjust import path as needed)
"""

from datetime import datetime, timezone

from app.config import YOUTUBE_CHANNELS
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.openai import OpenAIScraper
from app.scrapers.anthropic import AnthropicScraper


def check_youtube():
    print("\n=== YouTube ===")
    print(f"Configured channels: {YOUTUBE_CHANNELS!r}")
    if not YOUTUBE_CHANNELS:
        print("⚠️  YOUTUBE_CHANNELS is empty — no channels will ever be scraped.")
        return

    scraper = YouTubeScraper()
    for channel_id in YOUTUBE_CHANNELS:
        videos = scraper.get_latest_videos(channel_id, hours=999999)  # effectively no cutoff
        print(f"\nChannel {channel_id}: {len(videos)} entries in RSS feed")
        for v in videos[:3]:
            age_hours = (datetime.now(timezone.utc) - v.published_at).total_seconds() / 3600
            print(f"  - {v.title[:60]!r} | published {v.published_at} | {age_hours:.1f}h ago")


def check_anthropic():
    print("\n=== Anthropic ===")
    scraper = AnthropicScraper()
    for rss_url in scraper.rss_urls:
        import feedparser
        feed = feedparser.parse(rss_url)
        print(f"\n{rss_url}")
        print(f"  bozo (malformed?): {getattr(feed, 'bozo', 'n/a')}")
        print(f"  entries: {len(feed.entries)}")
        if feed.entries:
            latest = feed.entries[0]
            published = getattr(latest, "published", "unknown")
            print(f"  most recent entry: {latest.get('title', '')[:60]!r} | published: {published}")


def check_openai():
    print("\n=== OpenAI ===")
    scraper = OpenAIScraper()
    articles = scraper.get_articles(hours=999999)  # effectively no cutoff
    print(f"Total entries (no cutoff): {len(articles)}")
    for a in articles[:3]:
        age_hours = (datetime.now(timezone.utc) - a.published_at).total_seconds() / 3600
        print(f"  - {a.title[:60]!r} | published {a.published_at} | {age_hours:.1f}h ago")


if __name__ == "__main__":
    check_youtube()
    check_anthropic()
    check_openai()