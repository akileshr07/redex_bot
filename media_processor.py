"""
media_processor.py

Handles post-download image normalization for Twitter upload.
Your requirements:

✔ Convert .webp → .jpeg (ensures Twitter compatibility)
✔ Ensure file size < 15 MB (Twitter upload limit via web)
✔ Auto-resize image if too large
✔ Preserve aspect ratio
✔ Return final processed file path

This module performs:
1. Format normalization
2. Optional compression/resizing (Pillow)
3. Save optimized output in the same download directory

No GIF/video processing — those are already rejected upstream.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import os

from logger import log_json

MAX_BYTES = 15 * 1024 * 1024  # 15MB


class MediaProcessor:
    def __init__(self, max_bytes: int = MAX_BYTES):
        self.max_bytes = max_bytes

    # -------------------------------------------------------------
    # Convert WEBP → JPEG
    # -------------------------------------------------------------
    def _convert_webp_to_jpeg(self, src: Path) -> Path:
        dest = src.with_suffix(".jpg")
        try:
            img = Image.open(src).convert("RGB")
            img.save(dest, format="JPEG", quality=90)
            return dest
        except Exception as e:
            log_json(
                "error",
                component="media_processor",
                event="webp_conversion_failed",
                details={"src": str(src), "error": str(e)},
            )
            return src

    # -------------------------------------------------------------
    # Compress / resize until under 15MB
    # -------------------------------------------------------------
    def _shrink_to_fit(self, path: Path) -> Path:
        img = Image.open(path)

        # If already under limit → done
        if path.stat().st_size <= self.max_bytes:
            return path

        quality = 95
        width, height = img.size

        while True:
            # Gradient compression
            quality = max(10, quality - 10)

            # Optional resize if file huge
            if path.stat().st_size > self.max_bytes * 2:
                width = int(width * 0.9)
                height = int(height * 0.9)
                img = img.resize((width, height), Image.LANCZOS)

            img.save(path, format="JPEG", quality=quality)

            if quality == 10 or path.stat().st_size <= self.max_bytes:
                break

        log_json(
            "info",
            component="media_processor",
            event="image_resized",
            details={"size_bytes": path.stat().st_size, "quality": quality},
        )
        return path

    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------
    def ensure_format_and_size(self, src: Path) -> Path:
        # Convert WEBP → JPEG if needed
        if src.suffix.lower() == ".webp":
            src = self._convert_webp_to_jpeg(src)

        # Ensure size < 15MB
        src = self._shrink_to_fit(src)

        log_json(
            "info",
            component="media_processor",
            event="media_ready",
            details={"file": str(src), "size": src.stat().st_size},
        )

        return src


# -------------------------------------------------------------
# Standalone test
# -------------------------------------------------------------
if __name__ == "__main__":
    from pathlib import Path

    p = MediaProcessor()
    test_img = Path("downloads/test_image.webp")

    if test_img.exists():
        out = p.ensure_format_and_size(test_img)
        print("Processed:", out)
    else:
        print("Place a .webp file in downloads/ to test.")
