"""
Shared helper for fetching RSS/Atom feeds.

Why this exists: feedparser.parse(url) fetches the URL itself using urllib,
which on some machines fails due to expired/outdated CA certs, and sends no
real User-Agent — some servers (YouTube included) respond with malformed or
error pages to that default UA. requests handles both of these fine, so we
fetch with requests and only use feedparser for parsing.
"""

import logging
import time
from typing import Optional

import feedparser
import requests

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def fetch_feed(url: str, timeout: int = 15, headers: Optional[dict] = None, retries: int = 2):
    """Fetch and parse an RSS/Atom feed. Returns a feedparser FeedParserDict.
    On any network failure, returns an empty-but-valid feedparser result
    (feed.entries == []) rather than raising, so callers can keep their
    existing `if not feed.entries` checks unchanged.

    Retries with backoff on 5xx errors and timeouts, since some feed
    endpoints (notably YouTube's) are known to intermittently return
    transient 500s under repeated automated requests."""
    headers = headers or DEFAULT_HEADERS
    last_error = None

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.bozo:
                log.warning(f"Feed at {url} parsed with warnings: {feed.bozo_exception}")
            return feed
        except requests.exceptions.SSLError as e:
            log.error(f"SSL error fetching {url}: {e}")
            break  # not transient, retrying won't help
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            last_error = e
            if status and 500 <= status < 600 and attempt < retries:
                wait = 2 ** (attempt + 1)  # 2s, 4s, ...
                log.warning(f"HTTP {status} fetching {url}, retrying in {wait}s (attempt {attempt + 1}/{retries})...")
                time.sleep(wait)
                continue
            log.error(f"HTTP error fetching {url}: {e}")
            break
        except requests.exceptions.ConnectionError as e:
            last_error = e
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                log.warning(f"Connection error fetching {url}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            log.error(f"Connection error fetching {url}: {e}")
            break
        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                log.warning(f"Timeout fetching {url}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            log.error(f"Timeout fetching {url}")
            break
        except Exception as e:
            log.error(f"Unexpected error fetching {url}: {e}")
            break

    # Return a valid, empty feed so `if not feed.entries` keeps working
    return feedparser.parse("")