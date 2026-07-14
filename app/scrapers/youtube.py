from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import time
import logging

from dotenv import load_dotenv
load_dotenv()

import requests
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig

log = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self):
        proxy_config = None
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")

        if proxy_username and proxy_password:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy_username,
                proxy_password=proxy_password
            )

        self.transcript_api = YouTubeTranscriptApi(proxy_config=proxy_config)

        self.api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            log.warning(
                "YOUTUBE_API_KEY is not set — get_latest_videos will return no "
                "results. Create a free key in Google Cloud Console (enable "
                "'YouTube Data API v3') and add it to your .env."
            )

    def _uploads_playlist_id(self, channel_id: str) -> str:
        """Every channel's uploads playlist ID is the channel ID with the
        'UC' prefix swapped for 'UU'. This avoids an extra API call to look
        it up via channels.list."""
        if channel_id.startswith("UC"):
            return "UU" + channel_id[2:]
        return channel_id  # already a playlist-style ID, or non-standard

    def _extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id)
            text = " ".join([snippet.text for snippet in transcript.snippets])
            return Transcript(text=text)
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception:
            return None

    def _api_get(self, endpoint: str, params: dict, retries: int = 2) -> Optional[dict]:
        params = {**params, "key": self.api_key}
        last_error = None
        for attempt in range(retries + 1):
            try:
                resp = requests.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=params, timeout=15)
                if resp.status_code == 403:
                    log.error(
                        f"YouTube API returned 403 — check that the API key is valid, "
                        f"'YouTube Data API v3' is enabled for it, and daily quota isn't exhausted. "
                        f"Response: {resp.text[:300]}"
                    )
                    return None
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                last_error = e
                if status and 500 <= status < 600 and attempt < retries:
                    wait = 2 ** (attempt + 1)
                    log.warning(f"YouTube API {status}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                log.error(f"YouTube API HTTP error: {e}")
                return None
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < retries:
                    wait = 2 ** (attempt + 1)
                    log.warning(f"YouTube API request failed ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                log.error(f"YouTube API request failed: {e}")
                return None
        return None

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> list[ChannelVideo]:
        if not self.api_key:
            return []

        playlist_id = self._uploads_playlist_id(channel_id)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        videos: List[ChannelVideo] = []
        page_token = None

        while True:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._api_get("playlistItems", params)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            hit_older_than_cutoff = False
            for item in items:
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})

                published_str = content_details.get("videoPublishedAt") or snippet.get("publishedAt")
                if not published_str:
                    continue
                published_time = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

                if published_time < cutoff_time:
                    hit_older_than_cutoff = True
                    break  # uploads playlist is newest-first, so we can stop here

                video_id = content_details.get("videoId")
                if not video_id:
                    continue

                videos.append(
                    ChannelVideo(
                        title=snippet.get("title", ""),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        video_id=video_id,
                        published_at=published_time,
                        description=snippet.get("description", ""),
                    )
                )

            if hit_older_than_cutoff:
                break

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return videos

    def scrape_channel(self, channel_id: str, hours: int = 150) -> list[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        result = []
        for video in videos:
            transcript = self.get_transcript(video.video_id)
            result.append(video.model_copy(update={"transcript": transcript.text if transcript else None}))
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = YouTubeScraper()
    transcript: Transcript = scraper.get_transcript("jqd6_bbjhS8")
    print(transcript.text if transcript else "No transcript found")
    channel_videos: List[ChannelVideo] = scraper.scrape_channel("UCn8ujwUInbJkBhffxqAPBVQ", hours=200)
    print(f"Found {len(channel_videos)} videos")