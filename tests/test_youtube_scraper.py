"""
Tests for app/scrapers/youtube.py

Run from the project root:
    uv run pytest tests/test_youtube_scraper.py -v
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app.scrapers.youtube import YouTubeScraper, ChannelVideo, Transcript


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _playlist_item(video_id: str, title: str, published_at: datetime) -> dict:
    return {
        "snippet": {
            "title": title,
            "description": f"description for {title}",
            "publishedAt": _iso(published_at),
        },
        "contentDetails": {
            "videoId": video_id,
            "videoPublishedAt": _iso(published_at),
        },
    }


def _make_scraper(api_key: str = "test-key") -> YouTubeScraper:
    scraper = YouTubeScraper()
    scraper.api_key = api_key
    return scraper


# ---------- ID parsing ----------

def test_extract_video_id_from_watch_url():
    scraper = _make_scraper()
    assert scraper._extract_video_id("https://www.youtube.com/watch?v=abc123&t=10s") == "abc123"


def test_extract_video_id_from_shorts_url():
    scraper = _make_scraper()
    assert scraper._extract_video_id("https://www.youtube.com/shorts/xyz789") == "xyz789"


def test_extract_video_id_from_short_domain():
    scraper = _make_scraper()
    assert scraper._extract_video_id("https://youtu.be/qwe456?t=5") == "qwe456"


def test_uploads_playlist_id_swaps_uc_prefix():
    scraper = _make_scraper()
    assert scraper._uploads_playlist_id("UCawZsQWqfGSbCI5yjkdVkTA") == "UUawZsQWqfGSbCI5yjkdVkTA"


def test_uploads_playlist_id_leaves_non_uc_ids_unchanged():
    scraper = _make_scraper()
    assert scraper._uploads_playlist_id("SOMEOTHERID") == "SOMEOTHERID"


# ---------- get_latest_videos ----------

def test_returns_empty_list_without_calling_api_when_no_key():
    scraper = _make_scraper(api_key=None)
    with patch.object(scraper, "_api_get") as mock_api_get:
        videos = scraper.get_latest_videos("UCsomechannel", hours=24)

    assert videos == []
    mock_api_get.assert_not_called()


def test_stops_pagination_once_item_older_than_cutoff():
    now = datetime.now(timezone.utc)
    scraper = _make_scraper()

    page_1 = {
        "items": [
            _playlist_item("v1", "Newest video", now - timedelta(hours=1)),
            _playlist_item("v2", "Still recent", now - timedelta(hours=5)),
            _playlist_item("v3", "Too old", now - timedelta(hours=48)),
        ],
        "nextPageToken": "page2token",  # should never be used — we stop before this
    }

    with patch.object(scraper, "_api_get", return_value=page_1) as mock_api_get:
        videos = scraper.get_latest_videos("UCsomechannel", hours=24)

    assert [v.video_id for v in videos] == ["v1", "v2"]
    mock_api_get.assert_called_once()  # never fetched page 2, since v3 signaled "past cutoff"


def test_paginates_when_every_item_on_page_is_recent():
    now = datetime.now(timezone.utc)
    scraper = _make_scraper()

    page_1 = {
        "items": [_playlist_item("v1", "First", now - timedelta(hours=1))],
        "nextPageToken": "page2token",
    }
    page_2 = {
        "items": [_playlist_item("v2", "Second", now - timedelta(hours=2))],
        # no nextPageToken -> end of results
    }

    with patch.object(scraper, "_api_get", side_effect=[page_1, page_2]) as mock_api_get:
        videos = scraper.get_latest_videos("UCsomechannel", hours=24)

    assert [v.video_id for v in videos] == ["v1", "v2"]
    assert mock_api_get.call_count == 2


def test_api_failure_returns_whatever_was_collected_so_far():
    scraper = _make_scraper()
    with patch.object(scraper, "_api_get", return_value=None):
        videos = scraper.get_latest_videos("UCsomechannel", hours=24)
    assert videos == []


def test_video_url_is_built_correctly():
    now = datetime.now(timezone.utc)
    scraper = _make_scraper()
    page_1 = {"items": [_playlist_item("abc123", "Some title", now)]}

    with patch.object(scraper, "_api_get", return_value=page_1):
        videos = scraper.get_latest_videos("UCsomechannel", hours=24)

    assert videos[0].url == "https://www.youtube.com/watch?v=abc123"


# ---------- scrape_channel ----------

def test_scrape_channel_merges_transcripts_by_video_id():
    now = datetime.now(timezone.utc)
    fixed_videos = [
        ChannelVideo(title="A", url="https://youtube.com/watch?v=v1", video_id="v1",
                     published_at=now, description="desc"),
        ChannelVideo(title="B", url="https://youtube.com/watch?v=v2", video_id="v2",
                     published_at=now, description="desc"),
    ]

    def fake_get_transcript(video_id):
        if video_id == "v1":
            return Transcript(text="transcript for v1")
        return None  # simulate disabled/unavailable transcript for v2

    scraper = _make_scraper()
    with patch.object(scraper, "get_latest_videos", return_value=fixed_videos), \
         patch.object(scraper, "get_transcript", side_effect=fake_get_transcript):
        result = scraper.scrape_channel("UCsomechannel", hours=150)

    by_id = {v.video_id: v for v in result}
    assert by_id["v1"].transcript == "transcript for v1"
    assert by_id["v2"].transcript is None