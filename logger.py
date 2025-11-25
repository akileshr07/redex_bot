"""
logger.py

A simple, clean, structured JSON logger used across the bot.

Your requirements:
✔ Output MUST be clean JSON
✔ NO extra prefixes
✔ Always include timestamp, component, event, level
✔ Lightweight and non-blocking
✔ Works with stdout (Render logs)
✔ No file logging

Usage:
log_json("info", component="fetcher", event="fetch_start", details={...})
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import sys
from typing import Dict, Any


def log_json(level: str, component: str, event: str, details: Dict[str, Any] = None):
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": component,
        "event": event,
        "details": details or {},
    }

    # Print as a single JSON object per line
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


# -------------------------------------------------------------
# Quick test
# -------------------------------------------------------------
if __name__ == "__main__":
    log_json("info", component="logger", event="test", details={"hello": "world"})

