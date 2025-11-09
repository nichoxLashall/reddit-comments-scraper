from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

from .utils_date import utc_timestamp_to_iso

DEFAULT_USER_AGENT = (
    "reddit-comments-scraper/1.0 (https://bitbash.dev; contact: sale@bitbash.dev)"
)

def _build_api_url(url: str) -> str:
    """
    Convert a standard Reddit post URL into its .json API endpoint.
    """
    url = url.strip()
    if not url:
        raise ValueError("Empty URL provided.")

    parsed = urlparse(url)
    if "reddit.com" not in parsed.netloc:
        raise ValueError(f"URL does not appear to be a Reddit URL: {url}")

    if url.endswith(".json"):
        return url

    if "reddit.com" in parsed.netloc:
        # If the URL already has a query string, insert .json before it.
        if parsed.query:
            base = url.split("?", 1)[0].rstrip("/")
            return f"{base}.json?{parsed.query}"
        return url.rstrip("/") + ".json"

    return url

def _detect_content_type(data: Dict[str, Any]) -> str:
    body = data.get("body")
    url = data.get("url") or data.get("permalink") or ""
    if body:
        return "text"
    if url:
        lowered = str(url).lower()
        if any(lowered.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            return "image"
        if any(lowered.endswith(ext) for ext in (".mp4", ".mov", ".webm")):
            return "video"
        return "link"
    return "unknown"

def _build_comment_object(data: Dict[str, Any], parent_id: Optional[str]) -> Dict[str, Any]:
    comment_id = data.get("name") or (f"t1_{data.get('id')}" if data.get("id") else None)
    link_id = data.get("link_id")
    author = data.get("author")
    permalink = data.get("permalink")
    created_utc = data.get("created_utc")
    upvotes = data.get("ups")

    content_type = _detect_content_type(data)
    created_time = utc_timestamp_to_iso(created_utc)

    if permalink and not str(permalink).startswith("http"):
        permalink = f"https://www.reddit.com{permalink}"

    if author and author not in ("[deleted]", "None"):
        user_url = f"https://www.reddit.com/user/{author}"
    else:
        user_url = None

    author_avatar = (
        data.get("author_icon_img")
        or data.get("snoovatar_img")
        or data.get("icon_img")
    )

    content_text = data.get("body") or ""

    comment_obj: Dict[str, Any] = {
        "comment_id": comment_id,
        "post_id": link_id,
        "author": author,
        "permalink": permalink,
        "upvotes": upvotes,
        "content_type": content_type,
        "parent_id": parent_id,
        "author_avatar": author_avatar,
        "userUrl": user_url,
        "contentText": content_text,
        "created_time": created_time,
        "replies": [],
    }
    return comment_obj

def _walk_children(
    children: List[Dict[str, Any]],
    seen_ids: Set[str],
    max_items: Optional[int],
    logger: logging.Logger,
    parent_id: Optional[str] = None,
    counter: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    if counter is None:
        counter = {"count": 0}

    results: List[Dict[str, Any]] = []

    for child in children:
        kind = child.get("kind")
        data = child.get("data") or {}

        # Skip "more" items for simplicity (they require an additional API call).
        if kind == "more":
            continue

        if kind != "t1":
            # Not a standard comment node, ignore quietly.
            continue

        comment_id = data.get("name") or (f"t1_{data.get('id')}" if data.get("id") else None)
        if not comment_id:
            continue

        if comment_id in seen_ids:
            logger.debug("Skipping duplicate comment_id: %s", comment_id)
            continue

        if max_items is not None and counter["count"] >= max_items:
            logger.debug("Reached max_items (%d), stopping traversal.", max_items)
            break

        seen_ids.add(comment_id)
        counter["count"] += 1

        comment_obj = _build_comment_object(data, parent_id=parent_id)

        replies = data.get("replies")
        if isinstance(replies, dict):
            nested_children = replies.get("data", {}).get("children", [])
            comment_obj["replies"] = _walk_children(
                nested_children,
                seen_ids=seen_ids,
                max_items=max_items,
                logger=logger,
                parent_id=comment_id,
                counter=counter,
            )
        else:
            comment_obj["replies"] = []

        results.append(comment_obj)

    return results

def fetch_comments_for_post(
    url: str,
    max_items: Optional[int] = None,
    proxies: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all comments for a given Reddit post URL and return a nested structure.

    :param url: Public Reddit post URL.
    :param max_items: Optional maximum number of comments (including replies).
    :param proxies: Optional requests-compatible proxies mapping.
    :param timeout: HTTP timeout in seconds.
    :param logger: Optional logger instance.
    :return: List of nested comment dictionaries.
    """
    logger = logger or logging.getLogger(__name__)

    api_url = _build_api_url(url)
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    logger.info("Fetching Reddit comments from: %s", api_url)

    try:
        response = requests.get(api_url, headers=headers, proxies=proxies, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("HTTP request to Reddit failed: %s", exc)
        return []

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode Reddit JSON response: %s", exc)
        return []

    if not isinstance(payload, list) or len(payload) < 2:
        logger.error("Unexpected Reddit API payload structure.")
        return []

    # Comments are typically in the second element's listing.
    comments_listing = payload[1]
    comments_data = comments_listing.get("data", {})
    children = comments_data.get("children", [])

    seen_ids: Set[str] = set()
    counter = {"count": 0}
    comments = _walk_children(
        children,
        seen_ids=seen_ids,
        max_items=max_items,
        logger=logger,
        parent_id=None,
        counter=counter,
    )

    logger.info("Parsed %d comment object(s) from the thread.", counter["count"])
    return comments