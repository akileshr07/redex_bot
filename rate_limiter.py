"""
rate_limiter.py

Async Token‑Bucket Rate Limiter (per‑endpoint).

Your Requirements:
✔ Must support Reddit, Twitter API, Twitter Media endpoints
✔ Prevent API spam
✔ Fully async, safe for concurrency
✔ Clean, independent component
✔ Used by fetcher, twitter_client, image_downloader, etc.

Behavior:
- Each endpoint has its own bucket
- Bucket has: capacity, tokens, refill rate
- Tokens refill every second
- acquire(endpoint) waits until a token becomes available
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict

from config import load_config
from logger import log_json


class _TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_sec
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self):
        async with self.lock:
            # Refill tokens
            now = time.monotonic()
            elapsed = now - self.last_refill
            refill_amount = elapsed * self.refill_rate
            if refill_amount > 0:
                self.tokens = min(self.capacity, self.tokens + refill_amount)
                self.last_refill = now

            # Wait until token available
            while self.tokens < 1:
                await asyncio.sleep(0.05)
                now = time.monotonic()
                elapsed = now - self.last_refill
                refill_amount = elapsed * self.refill_rate
                if refill_amount > 0:
                    self.tokens = min(self.capacity, self.tokens + refill_amount)
                    self.last_refill = now

            # Consume 1 token
            self.tokens -= 1


class RateLimiter:
    def __init__(self):
        cfg = load_config()

        # Convert refill-per-minute settings → per‑second rates
        rl = cfg.rate_limits

        self.buckets: Dict[str, _TokenBucket] = {}

        # Reddit bucket
        reddit_cap = rl["reddit"].get("capacity", 60)
        reddit_refill = rl["reddit"].get("refill_per_min", 60) / 60.0
        self.buckets["reddit"] = _TokenBucket(reddit_cap, reddit_refill)

        # Twitter API (non-media)
        tw_cap = rl["twitter_api"].get("capacity", 300)
        tw_refill = rl["twitter_api"].get("refill_per_15min", 300) / (15 * 60)
        self.buckets["twitter_api"] = _TokenBucket(tw_cap, tw_refill)

        # Twitter Media
        media_cap = rl["twitter_media"].get("capacity", 50)
        media_refill = rl["twitter_media"].get("refill_per_15min", 50) / (15 * 60)
        self.buckets["twitter_media"] = _TokenBucket(media_cap, media_refill)

    # -------------------------------------------------------------
    # Async context manager
    # -------------------------------------------------------------
    async def acquire(self, endpoint: str):
        bucket = self.buckets.get(endpoint)
        if not bucket:
            raise ValueError(f"Rate limiter missing endpoint: {endpoint}")

        await bucket.consume()

        # Logging minimal to avoid spam
        log_json(
            "debug",
            component="rate_limiter",
            event="token_acquired",
            details={"endpoint": endpoint},
        )

        class _Ctx:
            async def __aenter__(self_inner):
                return None

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()


# -------------------------------------------------------------
# Standalone test
# -------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def _t():
        rl = RateLimiter()

        async def hit(n):
            async with rl.acquire("reddit"):
                print(f"Request {n} OK")

        await asyncio.gather(*(hit(i) for i in range(10)))

    asyncio.run(_t())
