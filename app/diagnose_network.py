"""
Deeper diagnostic: checks the RAW HTTP response (via requests) and what
feedparser sees (status/bozo/exception) for both the OpenAI and YouTube
RSS feeds. Run this if diagnose_sources.py showed 0 entries even with a
huge hours window — that means feedparser is failing silently, and this
script will show you WHY (network block, SSL error, bad response, etc).

pip install requests   (if not already installed)
"""

import feedparser
import requests

FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "YouTube (Matthew Berman)": "https://www.youtube.com/feeds/videos.xml?channel_id=UCawZsQWqfGSbCI5yjkdVkTA",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def check_raw_http(name: str, url: str):
    print(f"\n--- {name}: raw HTTP request ---")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  status_code: {r.status_code}")
        print(f"  content length: {len(r.content)} bytes")
        print(f"  content-type: {r.headers.get('content-type')}")
        if r.status_code != 200:
            print(f"  ⚠️ body preview: {r.text[:300]!r}")
    except requests.exceptions.SSLError as e:
        print(f"  ❌ SSL ERROR: {e}")
        print("  → likely a certificate issue on this machine. Try: pip install --upgrade certifi")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ CONNECTION ERROR: {e}")
        print("  → likely blocked by firewall/antivirus/VPN/proxy on this machine or network")
    except requests.exceptions.Timeout:
        print("  ❌ TIMEOUT — request took too long, network/proxy issue likely")
    except Exception as e:
        print(f"  ❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")


def check_feedparser(name: str, url: str):
    print(f"\n--- {name}: feedparser.parse() ---")
    feed = feedparser.parse(url, request_headers=HEADERS)
    print(f"  status: {feed.get('status', 'no status (connection likely failed)')}")
    print(f"  bozo: {feed.bozo}")
    if feed.bozo:
        print(f"  bozo_exception: {feed.bozo_exception}")
    print(f"  entries found: {len(feed.entries)}")


if __name__ == "__main__":
    for name, url in FEEDS.items():
        check_raw_http(name, url)
        check_feedparser(name, url)
        print()