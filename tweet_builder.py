"""
tweet_builder.py

Constructs final tweet text following your exact rules:

RULE 1 — Determine Base Tweet Text
CASE A: Post has ONLY title (no body text)
    → Use ONLY the title
CASE B: Post has title AND NON-EMPTY body text
    → Use ONLY the body text
CASE C: Post has title + body + images (image/gallery)
    → Use ONLY the title

RULE 2 — Append Subreddit-Specific Hashtags
{base_text} {#tag1 #tag2 ...}

RULE 3 — 280-Character Enforcement (Hybrid Strategy)
Step 1 — If ≤ 280 chars → OK
Step 2 — If > 280 → Trim hashtags one by one (END → START)
Step 3 — If still > 280 → Trim base_text by removing characters until ≤ 280

If trimming fails (empty base_text), the post is rejected.

This module returns a tuple: (final_tweet_text, success_flag)
"""
from __future__ import annotations

from typing import List, Tuple

from filtering import FilteredPost, IMAGE, GALLERY
from logger import log_json

MAX_TWEET_LEN = 280


class TweetBuilder:
    def __init__(self, trim_strategy: str = "hybrid"):
        self.trim_strategy = trim_strategy

    # ---------------------------------------------------------
    # Determine base text
    # ---------------------------------------------------------
    def _select_base_text(self, post: FilteredPost) -> str:
        title = (post.raw.get("title") or "").strip()
        body = (post.raw.get("selftext") or "").strip()

        # CASE C — If images present, ALWAYS use title
        if post.post_type in {IMAGE, GALLERY}:
            return title

        # CASE A — Only title
        if body == "":
            return title

        # CASE B — Body exists & no images
        return body

    # ---------------------------------------------------------
    # Append hashtags
    # ---------------------------------------------------------
    def _append_hashtags(self, base: str, hashtags: List[str]) -> str:
        if not hashtags:
            return base
        return base + " " + " ".join(hashtags)

    # ---------------------------------------------------------
    # Trim hashtags one by one
    # ---------------------------------------------------------
    def _trim_hashtags(self, base_text: str, hashtags: List[str]) -> Tuple[str, List[str]]:
        current_hashtags = hashtags[:]
        while current_hashtags:
            tweet = base_text + " " + " ".join(current_hashtags)
            if len(tweet) <= MAX_TWEET_LEN:
                return tweet, current_hashtags
            current_hashtags.pop()  # remove last hashtag
        # Return without hashtags
        return base_text, []

    # ---------------------------------------------------------
    # Trim base text by characters until <= 280
    # ---------------------------------------------------------
    def _force_truncate_base(self, base_text: str) -> str:
        if len(base_text) <= MAX_TWEET_LEN:
            return base_text
        return base_text[:MAX_TWEET_LEN]

    # ---------------------------------------------------------
    # Public API: Build final tweet text
    # ---------------------------------------------------------
    def build_tweet(self, post: FilteredPost, hashtags: List[str]) -> Tuple[str, bool]:
        base_text = self._select_base_text(post)

        if not base_text:
            log_json(
                "warning",
                component="tweet_builder",
                event="empty_base_text",
                details={"title": post.raw.get("title")},
            )
            return "", False

        # Step 2 — Append hashtags
        tweet = self._append_hashtags(base_text, hashtags)

        # Step 3 — If <= 280 chars → done
        if len(tweet) <= MAX_TWEET_LEN:
            return tweet, True

        # Step 4 — Trim hashtags (hybrid logic)
        trimmed_tweet, remaining_tags = self._trim_hashtags(base_text, hashtags)

        if len(trimmed_tweet) <= MAX_TWEET_LEN:
            return trimmed_tweet, True

        # Step 5 — Hybrid: truncate base text if still too long
        truncated_base = self._force_truncate_base(base_text)

        if not truncated_base:
            return "", False

        # Reappend remaining hashtags if possible
        final_tweet = self._append_hashtags(truncated_base, remaining_tags)

        if len(final_tweet) <= MAX_TWEET_LEN:
            return final_tweet, True

        # Final fallback — return truncated base only
        if len(truncated_base) <= MAX_TWEET_LEN:
            return truncated_base, True

        # If that fails too → reject
        return "", False


# ---------------------------------------------------------
# Standalone test
# ---------------------------------------------------------
if __name__ == "__main__":
    from filtering import FilteredPost

    builder = TweetBuilder()

    sample = FilteredPost(
        {
            "title": "Example title",
            "selftext": "This is a long body text that should be used only if the post type is TEXT or LINK, not image.",
        },
        IMAGE,
    )

    tweet, ok = builder.build_tweet(sample, ["#Tag1", "#Tag2", "#Tag3"])
    print("OK?", ok)
    print(tweet)
