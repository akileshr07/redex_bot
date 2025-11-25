"""
twitter_client.py

Handles ALL Twitter (X) API v1.1 interactions using OAuth 1.0a.

Your requirements:
✔ Use OAuth 1.0a (consumer key/secret + access token/secret)
✔ Upload ONLY 1 image (your strict instruction)
✔ Post tweet with optional media
✔ Emergency fallback: RETWEET the latest tweet from @striver_79
✔ Rate-limited (using RateLimiter)
✔ JSON-structured logs

Endpoints used:
- POST media/upload → https://upload.twitter.com/1.1/media/upload.json
- POST statuses/update → https://api.twitter.com/1.1/statuses/update.json
- GET statuses/user_timeline → https://api.twitter.com/1.1/statuses/user_timeline.json
- POST statuses/retweet/:id.json

This component is completely async and isolated.
"""
from __future__ import annotations

import aiohttp
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

from requests_oauthlib import OAuth1

from rate_limiter import RateLimiter
from logger import log_json
from config import load_config


class TwitterClient:
    def __init__(self, rate_limiter: RateLimiter):
        cfg = load_config()

        self.rate_limiter = rate_limiter

        self.auth = OAuth1(
            cfg.twitter_api_key,
            cfg.twitter_api_secret,
            cfg.twitter_access_token,
            cfg.twitter_access_secret,
        )

        self.session = aiohttp.ClientSession()

    # -------------------------------------------------------------
    # INTERNAL helper: perform OAuth1 request with aiohttp
    # -------------------------------------------------------------
    async def _post(self, url: str, data: Dict[str, Any] = None, files: Dict[str, Any] = None):
        """
        aiohttp does NOT support OAuth1 natively.
        We generate headers using requests_oauthlib then pass into aiohttp.
        """
        from requests import Request
        from requests.sessions import Session as ReqSession

        req = Request("POST", url, data=data)
        prep = req.prepare()

        # Sign request using OAuth1
        auth = self.auth(prep)
        headers = dict(prep.headers)

        async with self.rate_limiter.acquire("twitter_api"):
            async with self.session.post(url, data=data, headers=headers) as resp:
                try:
                    return await resp.json()
                except Exception:
                    text = await resp.text()
                    return {"error": text, "status": resp.status}

    async def _post_media(self, url: str, data: Dict[str, Any], file_path: Path):
        # Same OAuth signing process but with file upload
        from requests import Request
        req = Request("POST", url, files={'media': file_path.open('rb')}, data=data)
        prep = req.prepare()
        auth = self.auth(prep)
        headers = dict(prep.headers)

        form = aiohttp.FormData()
        form.add_field("media", file_path.open("rb"), filename=file_path.name)

        async with self.rate_limiter.acquire("twitter_media"):
            async with self.session.post(url, data=form, headers=headers) as resp:
                try:
                    return await resp.json()
                except Exception:
                    text = await resp.text()
                    return {"error": text, "status": resp.status}

    # -------------------------------------------------------------
    # Upload 1 image to Twitter
    # -------------------------------------------------------------
    async def upload_media(self, file_path: Path) -> Optional[str]:
        url = "https://upload.twitter.com/1.1/media/upload.json"

        log_json(
            "info",
            component="twitter_client",
            event="media_upload_start",
            details={"file": str(file_path)},
        )

        resp = await self._post_media(url, data={}, file_path=file_path)

        if not resp or "media_id_string" not in resp:
            log_json(
                "error",
                component="twitter_client",
                event="media_upload_failed",
                details={"response": resp},
            )
            return None

        media_id = resp.get("media_id_string")

        log_json(
            "info",
            component="twitter_client",
            event="media_upload_success",
            details={"media_id": media_id},
        )

        return media_id

    # -------------------------------------------------------------
    # Post tweet with optional media
    # -------------------------------------------------------------
    async def post_tweet(self, text: str, media_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        url = "https://api.twitter.com/1.1/statuses/update.json"

        payload = {"status": text}
        if media_ids:
            payload["media_ids"] = ",".join(media_ids)

        log_json(
            "info",
            component="twitter_client",
            event="tweet_post_start",
            details={"text": text[:50], "media_ids": media_ids},
        )

        resp = await self._post(url, data=payload)

        if not resp or "id" not in resp and "id_str" not in resp:
            log_json(
                "error",
                component="twitter_client",
                event="tweet_post_failed",
                details={"response": resp},
            )
            return {"success": False, "response": resp}

        tweet_id = resp.get("id_str") or str(resp.get("id"))

        log_json(
            "info",
            component="twitter_client",
            event="tweet_post_success",
            details={"tweet_id": tweet_id},
        )

        return {"success": True, "tweet_id": tweet_id}

    # -------------------------------------------------------------
    # Emergency fallback: RETWEET @striver_79 latest tweet
    # -------------------------------------------------------------
    async def retweet_latest(self, username: str = "striver_79") -> Dict[str, Any]:
        # Fetch recent tweets
        url = "https://api.twitter.com/1.1/statuses/user_timeline.json"
        timeline = await self._post(url, data={"screen_name": username, "count": 1})

        if not timeline or not isinstance(timeline, list) or not timeline:
            log_json(
                "error",
                component="twitter_client",
                event="retweet_timeline_fetch_failed",
                details={"response": timeline},
            )
            return {"success": False, "response": timeline}

        latest_id = timeline[0].get("id_str") or str(timeline[0].get("id"))

        # Retweet
        url = f"https://api.twitter.com/1.1/statuses/retweet/{latest_id}.json"
        resp = await self._post(url)

        if "retweeted" in resp and resp["retweeted"] is True:
            log_json(
                "info",
                component="twitter_client",
                event="emergency_retweet_success",
                details={"retweeted_id": latest_id},
            )
            return {"success": True, "retweeted_id": latest_id}

        log_json(
            "error",
            component="twitter_client",
            event="emergency_retweet_failed",
            details={"response": resp},
        )
        return {"success": False, "response": resp}

    # -------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------
    async def close(self):
        await self.session.close()


# -------------------------------------------------------------
# Standalone test (⚠ Will post real tweets if enabled!)
# -------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    from rate_limiter import RateLimiter

    async def _t():
        client = TwitterClient(RateLimiter())
        print("Twitter client initialized.")

        # WARNING: This only tests post_tweet with no media
        resp = await client.post_tweet("Test tweet from dev environment.")
        print(resp)

        await client.close()

    asyncio.run(_t())
