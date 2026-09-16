"""
mastodon_client.py
-------------------
Client for Mastodon's PUBLIC hashtag timeline endpoint. Public timelines
on Mastodon instances are readable without an access token, so this needs
no signup, no API key, and no extra package -- just `urllib.request`.

Docs: https://docs.joinmastodon.org/methods/timelines/#tag
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from config import (
    MASTODON_INSTANCE,
    MASTODON_LIMIT,
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
)


def _get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SynopticWeatherPlatform/1.0",
            "Accept": "application/json",
        },
    )
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def fetch_hashtag_posts(hashtag: str, limit: int = None):
    """Fetch recent public posts for a single hashtag from MASTODON_INSTANCE."""
    limit = limit or MASTODON_LIMIT
    tag = urllib.parse.quote(hashtag.lstrip("#"))
    url = f"{MASTODON_INSTANCE}/api/v1/timelines/tag/{tag}?limit={limit}"
    try:
        statuses = _get_json(url)
    except RuntimeError:
        # Network unavailable or instance unreachable -- fail soft so the
        # rest of the pipeline (NWS data) can still run.
        return []

    return [_simplify_status(s, hashtag) for s in statuses]


def fetch_all_hashtags(hashtags):
    posts = []
    for tag in hashtags:
        posts.extend(fetch_hashtag_posts(tag))
    return posts


def _simplify_status(status: dict, hashtag: str) -> dict:
    account = status.get("account", {}) or {}
    return {
        "id": status.get("id"),
        "hashtag": hashtag,
        "author": account.get("acct"),
        "content": status.get("content", ""),
        "created_at": status.get("created_at"),
        "url": status.get("url"),
        # sentiment fields filled in by the ETL pipeline
        "sentiment_label": None,
        "sentiment_score": None,
        "fetched_at": None,
    }
