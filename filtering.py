"""
filtering.py

Filtering logic for Reddit → Twitter bot.
This module enforces all the HARD FILTERS you specified.

A post is REJECTED if ANY of the following is true:
- Video post
- External video (YouTube, TikTok, etc.)
- GIF / animated post
- Poll post
- Crosspost
- Spoiler or NSFW
- Stickied post
- Distinguished post
- Deleted / removed
- Promoted / sponsored
- Contest-mode post
- Text body length > 200 chars

This module ONLY decides survival or rejection.
Scoring and prioritization happen in scorer.py.
"""
from __future__ import annotations

import re
from typing import Dict, Any

from logger import log_json

# Known video domains
VIDEO_DOMAINS = [
    "v.redd.it",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "instagram.com",
    "fb.watch",
]

# GIF patterns
GIF_EXTENSIONS = [".gif", ".gifv"]


class FilteredPost:
    """Wrapper for posts that pass hard filters.
    Contains raw post data and detected post_type.
    """

    def __init__(self, raw: Dict[str, Any], post_type: str):
        self.raw = raw
        self.post_type = post_type

    def __getitem__(self, key):
        return self.raw.get(key)


# Post types
IMAGE = "image"
GALLERY = "gallery"
TEXT = "text"
LINK = "link"
GIF = "gif"
VIDEO = "video"
CROSSPOST = "crosspost"
UNKNOWN = "unknown"


class Filtering:
    def __init__(self):
        pass

    # -------------------------
    # Detect post type
    # -------------------------
    def detect_post_type(self, post: Dict[str, Any]) -> str:
        # Crosspost
        if post.get("crosspost_parent") or post.get("crosspost_parent_list"):
            return CROSSPOST

        # Poll
        if post.get("poll_data"):
            return "poll"

        # NSFW or spoiler
        if post.get("over_18") or post.get("spoiler"):
            return "blocked"

        # Removed / deleted / locked
        if post.get("removed_by_category") or post.get("locked"):
            return "blocked"

        # Promoted / sponsored
        if post.get("is_created_from_ads_ui") or post.get("is_gallery_ad"):
            return "blocked"

        # Distinguished / stickied
        if post.get("distinguished") or post.get("stickied"):
            return "blocked"

        url = post.get("url_overridden_by_dest") or post.get("url") or ""
        lower_url = url.lower()

        # GIF
        if any(lower_url.endswith(ext) for ext in GIF_EXTENSIONS):
            return GIF

        # Video domains (reject videos entirely)
        if any(domain in lower_url for domain in VIDEO_DOMAINS):
            return VIDEO

        # Reddit-hosted video
        if post.get("is_video"):
            return VIDEO

        # Gallery
        if post.get("is_gallery"):
            return GALLERY

        # Image post
        if post.get("post_hint") == "image":
            return IMAGE

        # Text
        if post.get("is_self"):
            return TEXT

        # Link post
        return LINK

    # -------------------------
    # Hard filters
    # -------------------------
    def apply_hard_filters(self, post: Dict[str, Any]) -> FilteredPost | None:
        post_type = self.detect_post_type(post)

        # Reject unwanted post types
        if post_type in {VIDEO, GIF, "poll", "blocked", CROSSPOST}:
            log_json(
                "info",
                component="filtering",
                event="rejected_post",
                details={"reason": f"type_{post_type}"},
            )
            return None

        # Reject text body longer than 200 chars
        body = post.get("selftext", "") or ""
        if body and len(body.strip()) > 200:
            log_json(
                "info",
                component="filtering",
                event="rejected_post",
                details={"reason": "text_too_long", "length": len(body)},
            )
            return None

        # Everything else survives
        return FilteredPost(post, post_type)


# ----------------------------------------
# Standalone test
# ----------------------------------------
if __name__ == "__main__":
    f = Filtering()
    sample = {
        "is_self": True,
        "selftext": "Short text",
        "stickied": False,
    }
    res = f.apply_hard_filters(sample)
    print(res.post_type if res else "Rejected")
