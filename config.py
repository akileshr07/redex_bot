"""
config.py

Configuration loader and default subreddit definitions for reddit-tech-to-x-bot.

- Loads environment variables (expects secrets in Render/Github Actions secrets)
- Exposes a `Config` dataclass and `load_config()` function
- Contains SUBREDDITS default structure derived from the information you provided

Do NOT store real secrets in this file; use environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

# --- Constants ---
IST = ZoneInfo("Asia/Kolkata")

# Default rate limits (token-bucket parameters). Tunable via env vars.
DEFAULT_RATE_LIMITS = {
    "reddit": {"capacity": 60, "refill_per_min": 60},
    "twitter_api": {"capacity": 300, "refill_per_15min": 300},
    "twitter_media": {"capacity": 50, "refill_per_15min": 50},
}

# Subreddits and hashtag lists (user-provided samples normalized here)
# Keys are friendly names used in the code; each entry contains metadata used by the scheduler
DEFAULT_SUBREDDITS = {
    "developersIndia": {
        "name": "developersIndia",
        "url": "https://www.reddit.com/r/developersIndia/",
        "post_time": time(hour=9, minute=0, tzinfo=IST),
        "category": "tech",
        "hashtags": [
            "#TechTwitter",
            "#Programming",
            "#Coding",
            "#WebDevelopment",
            "#DeveloperLife",
            "#100DaysOfCode",
            "#Tech",
        ],
    },
    "ProgrammerHumor": {
        "name": "ProgrammerHumor",
        "url": "https://www.reddit.com/r/ProgrammerHumor/",
        "post_time": time(hour=18, minute=0, tzinfo=IST),
        "category": "humor",
        "hashtags": [
            "#Funny",
            "#Humor",
            "#FunnyTweets",
            "#Memes",
            "#DankMemes",
            "#Comedy",
            "#LOL",
        ],
    },
    "technology": {
        "name": "technology",
        "url": "https://www.reddit.com/r/technology/",
        "post_time": time(hour=9, minute=0, tzinfo=IST),
        "category": "tech",
        "hashtags": [
            "#TechNews",
            "#TechnologyNews",
            "#AI",
            "#Innovation",
            "#Gadgets",
            "#Cybersecurity",
            "#TechTrends",
            "#NewTech",
        ],
    },
    "oddlysatisfying": {
        "name": "oddlysatisfying",
        "url": "https://www.reddit.com/r/oddlysatisfying/",
        "post_time": time(hour=12, minute=0, tzinfo=IST),
        "category": "satisfy",
        "hashtags": [
            "#OddlySatisfying",
            "#ASMR",
            "#Satisfying",
            "#Relaxing",
            "#SatisfyingVideos",
            "#Relaxation",
            "#ASMRCommunity",
        ],
    },
    "IndiaCricket": {
        "name": "IndiaCricket",
        "url": "https://www.reddit.com/r/IndiaCricket/hot/",
        "post_time": time(hour=15, minute=0, tzinfo=IST),
        "category": "sports",
        "hashtags": [
            "#Cricket",
            "#IPL",
            "#WorldCup",
            "#Sports",
            "#CricketLovers",
            "#TeamIndia",
            "#CricketFever",
        ],
    },
}


@dataclass
class SubredditConfig:
    name: str
    url: str
    post_time: time
    category: str
    hashtags: List[str] = field(default_factory=list)


@dataclass
class Config:
    # Subreddit mapping: friendly_name -> SubredditConfig
    subreddits: Dict[str, SubredditConfig]

    # Rate limits
    rate_limits: Dict[str, Dict]

    # Twitter credentials (read from env at runtime)
    twitter_api_key: Optional[str]
    twitter_api_secret: Optional[str]
    twitter_access_token: Optional[str]
    twitter_access_secret: Optional[str]

    # Telegram notifier
    telegram_bot_token: Optional[str]
    telegram_admin_chat_id: Optional[str]

    # Image & media settings
    max_image_size_mb: int
    max_images_per_tweet: int

    # Behavior flags
    trim_strategy: str  # 'hybrid'|'strict_reject'|'force_truncate'

    # Other runtime options
    python_runtime: str


def _load_subreddits_from_defaults() -> Dict[str, SubredditConfig]:
    cfg: Dict[str, SubredditConfig] = {}
    for key, v in DEFAULT_SUBREDDITS.items():
        cfg[key] = SubredditConfig(
            name=v["name"],
            url=v["url"],
            post_time=v["post_time"],
            category=v["category"],
            hashtags=v.get("hashtags", []),
        )
    return cfg


def load_config() -> Config:
    """Load configuration from environment variables with sensible defaults.

    This function intentionally avoids loading secrets from disk and expects them
    to be provided via environment variables (Render secrets / GitHub Actions secrets).
    """
    subreddits = _load_subreddits_from_defaults()

    rate_limits = DEFAULT_RATE_LIMITS.copy()

    # Allow overriding rate limits via environment variables
    try:
        reddit_cap = int(os.getenv("RATE_REDDIT_CAPACITY", "60"))
        rate_limits["reddit"]["capacity"] = reddit_cap
    except Exception:
        pass

    # Twitter credentials (should be set in Render secrets)
    twitter_api_key = os.getenv("X_API_KEY")
    twitter_api_secret = os.getenv("X_API_SECRET")
    twitter_access_token = os.getenv("X_ACCESS_TOKEN")
    twitter_access_secret = os.getenv("X_ACCESS_SECRET")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

    # Image defaults
    max_image_size_mb = int(os.getenv("MAX_IMAGE_SIZE_MB", "15"))
    # You requested strictly 1 image per tweet (first image only)
    max_images_per_tweet = int(os.getenv("MAX_IMAGES_PER_TWEET", "1"))

    # Trimming strategy: hybrid = trim hashtags first then force-truncate base text
    trim_strategy = os.getenv("TWEET_TRIM_STRATEGY", "hybrid")

    python_runtime = os.getenv("PYTHON_RUNTIME", "3.11")

    return Config(
        subreddits=subreddits,
        rate_limits=rate_limits,
        twitter_api_key=twitter_api_key,
        twitter_api_secret=twitter_api_secret,
        twitter_access_token=twitter_access_token,
        twitter_access_secret=twitter_access_secret,
        telegram_bot_token=telegram_bot_token,
        telegram_admin_chat_id=telegram_admin_chat_id,
        max_image_size_mb=max_image_size_mb,
        max_images_per_tweet=max_images_per_tweet,
        trim_strategy=trim_strategy,
        python_runtime=python_runtime,
    )


if __name__ == "__main__":
    # Quick smoke test
    cfg = load_config()
    print("Loaded config:")
    for k, v in cfg.subreddits.items():
        print(f" - {k}: post_time={v.post_time.isoformat()}, hashtags={len(v.hashtags)}")
