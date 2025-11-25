"""
notifier.py

Sends structured JSON alerts to Telegram.
Your Notification Requirements:

✔ Send logs for:
    - WHICH REDDIT POST IS SELECTED
    - When sorting starts
    - When tweet builder fails
    - When no qualifying post is found
    - All failures & permanent errors
    - Emergency fallback retweet events

✔ Use Telegram Bot API (sendMessage)
✔ Pure async aiohttp
✔ Clean, reusable component

Message Format:
<short message>
<JSON dump of details>
"""
from __future__ import annotations

import aiohttp
import asyncio
import json
from typing import Dict, Any

from config import load_config
from logger import log_json

TELEGRAM_SEND_URL = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier:
    def __init__(self):
        cfg = load_config()
        self.token = cfg.telegram_bot_token
        self.chat_id = cfg.telegram_admin_chat_id
        self.session = aiohttp.ClientSession()

    # -------------------------------------------------------------
    # Format and send a message to Telegram
    # -------------------------------------------------------------
    async def send_alert(self, short: str, payload: Dict[str, Any]):
        if not self.token or not self.chat_id:
            # Telegram not configured
            return

        text = f"{short}\n```json\n{json.dumps(payload, indent=2)}\n```"

        url = TELEGRAM_SEND_URL.format(token=self.token)
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with self.session.post(url, data=data) as resp:
                _ = await resp.text()  # not used, but ensures request completes
        except Exception as e:
            log_json(
                "error",
                component="notifier",
                event="telegram_send_failed",
                details={"error": str(e)},
            )

    # -------------------------------------------------------------
    # Convenience wrappers for common events
    # -------------------------------------------------------------
    async def sorting_started(self, subreddit: str):
        await self.send_alert("Sorting started", {"subreddit": subreddit})

    async def post_selected(self, subreddit: str, title: str, post_id: str):
        await self.send_alert(
            "Selected Reddit post",
            {"subreddit": subreddit, "title": title, "post_id": post_id},
        )

    async def no_post_selected(self, subreddit: str):
        await self.send_alert("No qualifying post found", {"subreddit": subreddit})

    async def tweet_builder_failed(self, subreddit: str, reason: str):
        await self.send_alert(
            "Tweet builder failed",
            {"subreddit": subreddit, "reason": reason},
        )

    async def error(self, component: str, reason: str, details: Dict[str, Any] = None):
        await self.send_alert(
            f"Error in {component}",
            {"reason": reason, "details": details or {}},
        )

    async def emergency_backoff(self, retweeted_id: str):
        await self.send_alert(
            "Emergency fallback triggered",
            {"retweeted_id": retweeted_id},
        )

    # -------------------------------------------------------------
    async def close(self):
        await self.session.close()


# -------------------------------------------------------------
# Standalone test
# -------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def _t():
        n = Notifier()
        await n.send_alert("Test alert", {"hello": "world"})
        await n.close()

    asyncio.run(_t())
