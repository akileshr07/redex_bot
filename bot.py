#!/usr/bin/env python3
"""
bot.py — Orchestrator

This is the HEART of your entire Reddit → X bot.

It wires together ALL independent components:
✔ config.py
✔ fetcher.py
✔ filtering.py
✔ scorer.py
✔ tweet_builder.py
✔ image_downloader.py
✔ media_processor.py
✔ twitter_client.py
✔ rate_limiter.py
✔ notifier.py
✔ logger.py

Responsibilities of bot.py:
1. Determine which subreddits should run at the current scheduled time
2. For each subreddit:
    - Notify: sorting started
    - Sliding-window fetch
    - Apply HARD FILTERS
    - Score + rank
    - Select top candidate
    - Build tweet text
    - Download first image
    - Convert + resize (media_processor)
    - Upload to X
    - Post tweet
    - Notify selection + success
3. Handle full error chain
4. On total failure → emergency fallback retweet

This file is designed to be triggered by GitHub Actions cron.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from config import load_config
from fetcher import RedditFetcher
from filtering import Filtering
from scorer import Scorer
from tweet_builder import TweetBuilder
from image_downloader import ImageDownloader
from media_processor import MediaProcessor
from twitter_client import TwitterClient
from rate_limiter import RateLimiter
from notifier import Notifier
from logger import log_json

IST = ZoneInfo("Asia/Kolkata")


class Bot:
    def __init__(self):
        self.cfg = load_config()

        self.rate_limiter = RateLimiter()
        self.fetcher = RedditFetcher(self.rate_limiter)
        self.filtering = Filtering()
        self.scorer = Scorer()
        self.builder = TweetBuilder(self.cfg.trim_strategy)
        self.downloader = ImageDownloader(self.rate_limiter)
        self.processor = MediaProcessor()
        self.twitter = TwitterClient(self.rate_limiter)
        self.notifier = Notifier()

    # -------------------------------------------------------------
    # Check if a subreddit is scheduled to run now
    # -------------------------------------------------------------
    def _is_scheduled_now(self, schedule_time) -> bool:
        now = datetime.now(IST)
        return now.hour == schedule_time.hour and now.minute == schedule_time.minute

    # -------------------------------------------------------------
    # Process one subreddit
    # -------------------------------------------------------------
    async def _process_subreddit(self, name: str, cfg):
        subreddit = cfg.name

        await self.notifier.sorting_started(subreddit)
        log_json("info", component="bot", event="sorting_started", details={"subreddit": subreddit})

        # Sliding-window fetch
        raw_posts = await self.fetcher.sliding_window_fetch(cfg.url)

        if not raw_posts:
            await self.notifier.no_post_selected(subreddit)
            log_json("info", component="bot", event="no_posts_in_window", details={"subreddit": subreddit})
            return

        # Hard filtering
        survivors = []
        for p in raw_posts:
            fp = self.filtering.apply_hard_filters(p)
            if fp:
                survivors.append(fp)

        if not survivors:
            await self.notifier.no_post_selected(subreddit)
            log_json("info", component="bot", event="no_survivors", details={"subreddit": subreddit})
            return

        # Scoring
        ranked = self.scorer.rank_candidates(survivors)

        if not ranked:
            await self.notifier.no_post_selected(subreddit)
            return

        top = ranked[0]
        post = top.filtered

        await self.notifier.post_selected(subreddit, post.raw.get("title"), post.raw.get("id"))

        # Build tweet
        tweet_text, ok = self.builder.build_tweet(post, cfg.hashtags)
        if not ok:
            await self.notifier.tweet_builder_failed(subreddit, "text_exceeds_limit")
            return

        # Download first image (if applicable)
        media_path = None
        if post.post_type in {"image", "gallery"}:
            media_path = await self.downloader.download_first_image(post)
            if media_path:
                media_path = self.processor.ensure_format_and_size(media_path)

        # Upload media if exists
        media_ids = []
        if media_path:
            media_id = await self.twitter.upload_media(media_path)
            if media_id:
                media_ids = [media_id]

        # Post tweet
        resp = await self.twitter.post_tweet(tweet_text, media_ids)
        if not resp.get("success"):
            await self.notifier.error("twitter", "tweet_failed", resp)
            # Emergency fallback retweet
            ret = await self.twitter.retweet_latest("striver_79")
            if ret.get("success"):
                await self.notifier.emergency_backoff(ret.get("retweeted_id"))
            return

        log_json("info", component="bot", event="tweet_posted", details={"tweet_id": resp.get("tweet_id")})

    # -------------------------------------------------------------
    # Main entry
    # -------------------------------------------------------------
    async def run(self):
        log_json("info", component="bot", event="run_start")

        tasks = []
        for key, sub in self.cfg.subreddits.items():
            if self._is_scheduled_now(sub.post_time):
                tasks.append(self._process_subreddit(key, sub))

        # SAFER VERSION (your request)
        if not tasks:
            log_json("info", component="bot", event="no_subreddits_scheduled")

            # ALWAYS close sessions
            await self.twitter.close()
            await self.notifier.close()
            return

        try:
            await asyncio.gather(*tasks)
        finally:
            await self.twitter.close()
            await self.notifier.close()

        log_json("info", component="bot", event="run_complete")


# -------------------------------------------------------------
# CLI entrypoint
# -------------------------------------------------------------
if __name__ == "__main__":
    bot = Bot()
    asyncio.run(bot.run())
