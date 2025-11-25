"""
scorer.py

Implements scoring and prioritization rules for the Reddit → X bot.

Your rules:

Priority groups (highest → lowest):
1. TOP PRIORITY → Posts with NO body text AND type in {image, gallery}
2. SECOND PRIORITY → All other image or gallery posts
3. LOWEST PRIORITY → Text or Link posts (only if body ≤ 200 chars)

Scoring formula:
score = (upvotes * 0.65) \
      + (comments * 0.35) \
      + (upvote_ratio * 10) \
      + (post_age_hours * -0.3)

Ranking logic:
Sort by:
    1. priority_group (lower number = higher priority)
    2. engagement score (descending)

This module only ranks posts. Tweet building occurs elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from filtering import FilteredPost, IMAGE, GALLERY, TEXT, LINK
from logger import log_json


@dataclass
class RankedPost:
    filtered: FilteredPost
    priority: int
    score: float

    @property
    def raw(self):
        return self.filtered.raw

    @property
    def post_type(self):
        return self.filtered.post_type


class Scorer:
    def __init__(self):
        pass

    # ---------------------------------------------------
    # Priority group resolver
    # ---------------------------------------------------
    def get_priority_group(self, post: FilteredPost) -> int:
        body = (post.raw.get("selftext") or "").strip()

        # TOP PRIORITY → no body AND image/gallery
        if post.post_type in {IMAGE, GALLERY} and len(body) == 0:
            return 1

        # SECOND PRIORITY → image or gallery (with optional short body)
        if post.post_type in {IMAGE, GALLERY}:
            return 2

        # LOWEST PRIORITY → text or link
        if post.post_type in {TEXT, LINK}:
            return 3

        # fallback (should not happen due to filtering)
        return 99

    # ---------------------------------------------------
    # Engagement scoring
    # ---------------------------------------------------
    def compute_score(self, post: FilteredPost) -> float:
        ups = post.raw.get("ups") or post.raw.get("upvotes") or 0
        comments = post.raw.get("num_comments", 0)
        ratio = post.raw.get("upvote_ratio", 1.0)
        created_utc = post.raw.get("created_utc", 0)

        now = datetime.now(timezone.utc).timestamp()
        age_hours = max((now - created_utc) / 3600, 0)

        score = (
            (ups * 0.65)
            + (comments * 0.35)
            + (ratio * 10)
            + (age_hours * -0.3)
        )

        return round(score, 3)

    # ---------------------------------------------------
    # Main ranking function
    # ---------------------------------------------------
    def rank_candidates(self, posts: List[FilteredPost]) -> List[RankedPost]:
        ranked: List[RankedPost] = []

        for p in posts:
            prio = self.get_priority_group(p)
            score = self.compute_score(p)
            ranked.append(RankedPost(filtered=p, priority=prio, score=score))

            log_json(
                "info",
                component="scorer",
                event="scored_post",
                details={
                    "title": p.raw.get("title"),
                    "post_type": p.post_type,
                    "priority": prio,
                    "score": score,
                },
            )

        # Sort: priority ASC (1 = top priority), score DESC
        ranked.sort(key=lambda x: (x.priority, -x.score))

        log_json(
            "info",
            component="scorer",
            event="ranking_complete",
            details={"count": len(ranked)},
        )

        return ranked


# ---------------------------------------------------------
# Standalone test
# ---------------------------------------------------------
if __name__ == "__main__":
    from filtering import FilteredPost

    scorer = Scorer()

    sample_posts = [
        FilteredPost({"title": "A", "selftext": "", "ups": 100, "num_comments": 20, "upvote_ratio": 0.95, "created_utc": 1700000000}, IMAGE),
        FilteredPost({"title": "B", "selftext": "hello", "ups": 200, "num_comments": 50, "upvote_ratio": 0.90, "created_utc": 1700000000}, GALLERY),
        FilteredPost({"title": "C", "selftext": "short text", "ups": 80, "num_comments": 30, "upvote_ratio": 0.99, "created_utc": 1700000000}, TEXT),
    ]

    ranked = scorer.rank_candidates(sample_posts)

    for r in ranked:
        print(r.priority, r.score, r.raw.get("title"))
