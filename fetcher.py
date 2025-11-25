"""
fetcher.py

Async Reddit JSON fetcher using basic web scraping.
(No OAuth; uses Reddit's public JSON endpoints.)

Implements sliding window logic:
- Try posts from last 10 hours
- If none survive filtering, try last 24 hours
- If none, try last 48 hours

This module **only fetches raw posts**.
Filtering/scoring is handled in separate components.
"""
from __future__ import annotations

import aiohttp
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from rate_limiter import RateLimiter
from logger import log_json

USER_AGENT = "Mozilla/5.0 (reddit-tech-to-x-bot)"

# Windows in hours for sliding window
WINDOWS = [10, 24, 48]


class FetchError(Exception):
    pass


class RedditFetcher:
    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def _fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch JSON from Reddit with rate limiting and retries."""
        tries = 3
        async with aiohttp.ClientSession() as session:
            for attempt in range(tries):
                async with self.rate_limiter.acquire("reddit"):
                    try:
                        async with session.get(
                            url,
                            headers={"User-Agent": USER_AGENT},
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            if resp.status != 200:
                                log_json(
                                    "error",
                                    component="fetcher",
                                    event="http_error",
                                    details={"url": url, "status": resp.status},
                                )
                                await asyncio.sleep(1)
                                continue
                            return await resp.json()
                    except Exception as e:
                        log_json(
                            "error",
                            component="fetcher",
                            event="exception",
                            details={"url": url, "error": str(e), "attempt": attempt},
                        )
                        await asyncio.sleep(1)
            raise FetchError(f"Failed to fetch URL after retries: {url}")

    async def fetch_candidates(self, subreddit_url: str, window_hours: int) -> List[Dict[str, Any]]:
        """
        Fetch posts from subreddit JSON feed and filter by age window.

        Returns list of raw Reddit posts (dicts).

        subreddit_url example:
            https://www.reddit.com/r/developersIndia/
        """
        json_url = subreddit_url.rstrip("/") + "/new.json?limit=100"

        data = await self._fetch_json(json_url)

        children = data.get("data", {}).get("children", [])
        posts = [c.get("data", {}) for c in children]

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=window_hours)

        filtered = []
        for p in posts:
            created_utc = p.get("created_utc")
            if not isinstance(created_utc, (int, float)):
                continue
            post_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)

            if post_time >= cutoff:
                filtered.append(p)

        log_json(
            "info",
            component="fetcher",
            event="window_fetch_complete",
            details={
                "subreddit_url": subreddit_url,
                "window_hours": window_hours,
                "posts_total": len(posts),
                "posts_in_window": len(filtered),
            },
        )
        return filtered

    async def sliding_window_fetch(self, subreddit_url: str) -> List[Dict[str, Any]]:
        """
        Performs sliding window fetch:
        Try 10h, then 24h, then 48h.

        Returns first non-empty list of posts.
        """
        for w in WINDOWS:
            posts = await self.fetch_candidates(subreddit_url, w)
            if posts:
                return posts
        return []


# --- Standalone test ---
if __name__ == "__main__":
    from rate_limiter import RateLimiter

    async def _test():
        rl = RateLimiter()
        fetcher = RedditFetcher(rl)

        posts = await fetcher.sliding_window_fetch("https://www.reddit.com/r/ProgrammerHumor/")
        print(f"Fetched {len(posts)} posts in sliding-window test.")

    asyncio.run(_test())
