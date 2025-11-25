"""
tests/test.py

LIVE TEST SUITE for reddit-tech-to-x-bot
⚠ WARNING: This test uses REAL Twitter + Telegram credentials from your environment.
Make sure secrets are loaded before running.

Run inside Colab or locally:
    !python tests/test.py --dry-run
    !python tests/test.py --post   # ⚠ actually posts to Twitter

Test Flow:
1. Load config
2. Fetch subreddit posts (10h window)
3. Apply filters
4. Score + pick top post
5. Build tweet text
6. (Optional) Download + process image
7. (Optional) Upload + post tweet
8. Send Telegram alerts for test results
"""
from __future__ import annotations

import asyncio
import argparse
from pprint import pprint

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


async def run_test(dry_run: bool):
    cfg = load_config()

    rl = RateLimiter()
    fetcher = RedditFetcher(rl)
    filtering = Filtering()
    scorer = Scorer()
    builder = TweetBuilder(cfg.trim_strategy)
    downloader = ImageDownloader(rl)
    processor = MediaProcessor()
    twitter = TwitterClient(rl)
    notifier = Notifier()

    # Pick first subreddit
    sub_key, sub_cfg = next(iter(cfg.subreddits.items()))
    print(f"Testing subreddit: {sub_key}")

    await notifier.sorting_started(sub_cfg.name)

    # Fetch
    raw_posts = await fetcher.sliding_window_fetch(sub_cfg.url)
    print("Fetched posts:", len(raw_posts))

    survivors = []
    for p in raw_posts:
        fp = filtering.apply_hard_filters(p)
        if fp:
            survivors.append(fp)

    print("Survivors:", len(survivors))

    ranked = scorer.rank_candidates(survivors)
    top = ranked[0]
    post = top.filtered

    await notifier.post_selected(sub_cfg.name, post.raw.get("title"), post.raw.get("id"))

    # Build tweet
    tweet_text, ok = builder.build_tweet(post, sub_cfg.hashtags)
    if not ok:
        print("Tweet text failed to build.")
        await notifier.tweet_builder_failed(sub_cfg.name, "exceeds_limit")
        return

    print("Tweet text:")
    print(tweet_text)

    # Image
    media_ids = []
    media_path = None
    if post.post_type in {"image", "gallery"}:
        media_path = await downloader.download_first_image(post)
        if media_path:
            media_path = processor.ensure_format_and_size(media_path)
            print("Image downloaded + processed:", media_path)

    if dry_run:
        print("Dry run → Skipping Twitter post.")
        return

    # Upload + post
    if media_path:
        mid = await twitter.upload_media(media_path)
        if mid:
            media_ids = [mid]

    resp = await twitter.post_tweet(tweet_text, media_ids)
    print("Twitter response:")
    pprint(resp)

    await twitter.close()
    await notifier.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()

    dry = not args.post

    log_json("info", component="tests", event="test_start")
    asyncio.run(run_test(dry))
    log_json("info", component="tests", event="test_end")
