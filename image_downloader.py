"""
image_downloader.py

Downloads ONLY the *first image* from a Reddit post.
Strict rules based on your instructions:

✔ For gallery → download the FIRST image only
✔ For single-image post → download that image
✘ Reject GIFs/animated posts (handled earlier in filtering.py)
✘ Reject videos (handled earlier)

Additional responsibilities:
- Ensures valid direct image URL
- Supports .jpg, .jpeg, .png, .webp
- Saves to a temporary path
- Returns the downloaded file path, or None if no image

Media conversion/resizing happens in media_processor.py.
"""
from __future__ import annotations

import aiohttp
import asyncio
import os
from pathlib import Path
from typing import Optional

from filtering import FilteredPost, IMAGE, GALLERY
from logger import log_json
from rate_limiter import RateLimiter

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class ImageDownloader:
    def __init__(self, rate_limiter: RateLimiter, download_dir: str = "downloads"):
        self.rate_limiter = rate_limiter
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # Determine first image URL
    # -------------------------------------------------------------
    def _extract_first_image_url(self, post: FilteredPost) -> Optional[str]:
        raw = post.raw

        if post.post_type == IMAGE:
            url = raw.get("url_overridden_by_dest") or raw.get("url")
            return url

        if post.post_type == GALLERY:
            gallery = raw.get("gallery_data", {}).get("items", [])
            if not gallery:
                return None
            first_id = gallery[0].get("media_id")
            if not first_id:
                return None

            media_metadata = raw.get("media_metadata", {})
            meta = media_metadata.get(first_id)
            if not meta:
                return None

            # Reddit stores images in 'p' (preview) or 's' (source)
            if "s" in meta and "u" in meta["s"]:
                return meta["s"]["u"]
            if "p" in meta and len(meta["p"]) > 0:
                return meta["p"][0].get("u")

        return None

    # -------------------------------------------------------------
    # Validate extension
    # -------------------------------------------------------------
    def _valid_image_ext(self, url: str) -> bool:
        lower = url.lower().split("?")[0]
        return any(lower.endswith(ext) for ext in SUPPORTED_EXT)

    # -------------------------------------------------------------
    # Download file
    # -------------------------------------------------------------
    async def _download(self, url: str, dest: Path) -> bool:
        tries = 3
        async with aiohttp.ClientSession() as session:
            for attempt in range(tries):
                async with self.rate_limiter.acquire("reddit"):  # still count as reddit media
                    try:
                        async with session.get(url, timeout=15) as resp:
                            if resp.status != 200:
                                await asyncio.sleep(1)
                                continue

                            data = await resp.read()
                            dest.write_bytes(data)
                            return True
                    except Exception as e:
                        log_json(
                            "error",
                            component="image_downloader",
                            event="download_exception",
                            details={"url": url, "error": str(e), "attempt": attempt},
                        )
                        await asyncio.sleep(1)
        return False

    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------
    async def download_first_image(self, post: FilteredPost) -> Optional[Path]:
        if post.post_type not in {IMAGE, GALLERY}:
            return None

        url = self._extract_first_image_url(post)
        if not url:
            log_json(
                "warning",
                component="image_downloader",
                event="no_image_url",
                details={"title": post.raw.get("title")},
            )
            return None

        if not self._valid_image_ext(url):
            log_json(
                "warning",
                component="image_downloader",
                event="invalid_ext",
                details={"url": url},
            )
            return None

        # Determine filename
        ext = url.lower().split("?")[0].split(".")[-1]
        filename = f"img_{post.raw.get('id', 'unknown')}.{ext}"
        dest = self.download_dir / filename

        ok = await self._download(url, dest)
        if not ok:
            log_json(
                "error",
                component="image_downloader",
                event="download_failed",
                details={"url": url},
            )
            return None

        log_json(
            "info",
            component="image_downloader",
            event="download_success",
            details={"file": str(dest)},
        )
        return dest


# -----------------------------------------------------------------
# Standalone test
# -----------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    from filtering import FilteredPost
    from rate_limiter import RateLimiter

    async def _t():
        rl = RateLimiter()
        dl = ImageDownloader(rl)

        # Minimal mock image post
        p = FilteredPost(
            {
                "id": "abc123",
                "url_overridden_by_dest": "https://i.redd.it/mockedimage123.jpg",
            },
            IMAGE,
        )

        out = await dl.download_first_image(p)
        print("Downloaded:", out)

    asyncio.run(_t())
