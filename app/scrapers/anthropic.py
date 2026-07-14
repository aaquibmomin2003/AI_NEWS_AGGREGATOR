from datetime import datetime, timedelta, timezone
from typing import List, Optional
from docling.document_converter import DocumentConverter
from pydantic import BaseModel

from app.utils.feed_fetch import fetch_feed


class AnthropicArticle(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None


class AnthropicScraper:
    def __init__(self):
        self.rss_urls = [
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        ]
        self.converter = DocumentConverter()

    def get_articles(self, hours: int = 24) -> List[AnthropicArticle]:
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        cutoff_date = cutoff_time.date()
        articles = []
        seen_guids = set()
        
        for rss_url in self.rss_urls:
            feed = fetch_feed(rss_url)
            if not feed.entries:
                continue
            
            for entry in feed.entries:
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue
                
                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)

                # This source (a third-party GitHub mirror) only records the
                # publish DATE, not the actual time of day — every entry
                # shows 00:00:00 UTC. Comparing that against an exact
                # rolling-hour cutoff would unfairly exclude articles from
                # "today" just because midnight is earlier than the cutoff
                # hour. So for midnight-only timestamps, compare calendar
                # dates instead of exact datetimes.
                is_midnight_only = (
                    published_time.hour == 0
                    and published_time.minute == 0
                    and published_time.second == 0
                )
                if is_midnight_only:
                    is_recent = published_time.date() >= cutoff_date
                else:
                    is_recent = published_time >= cutoff_time

                if is_recent:
                    guid = entry.get("id", entry.get("link", ""))
                    if guid not in seen_guids:
                        seen_guids.add(guid)
                        articles.append(AnthropicArticle(
                            title=entry.get("title", ""),
                            description=entry.get("description", ""),
                            url=entry.get("link", ""),
                            guid=guid,
                            published_at=published_time,
                            category=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None
                        ))
        
        return articles

    def url_to_markdown(self, url: str) -> Optional[str]:
        try:
            result = self.converter.convert(url)
            return result.document.export_to_markdown()
        except Exception:
            return None


if __name__ == "__main__":
    scraper = AnthropicScraper()
    articles: List[AnthropicArticle] = scraper.get_articles(hours=100)
    markdown: str = scraper.url_to_markdown(articles[1].url)
    print(markdown)