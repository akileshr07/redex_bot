# Reddit → X (Twitter) Async Bot

A fully optimized **async + modular + rate‑limited** Reddit → X bot engineered for high reliability, clean debugging, and production‑grade automation.

This project fetches high‑quality posts from multiple subreddits, filters + scores them using custom engagement logic, builds a perfectly formatted tweet, downloads & processes the first image, uploads to X using v1.1 media endpoints, posts the tweet, and sends all logs + alerts to Telegram.

Everything is split into small independent components under `bot.py` (orchestrator).

---
## 🚀 Key Features

### ✔ 100% Async Architecture (aiohttp)
### ✔ Sliding-window Reddit fetch (10h → 24h → 48h)
### ✔ Heavy filtering for content quality
### ✔ Custom engagement scoring system
### ✔ Intelligent tweet builder (hashtags + trimming)
### ✔ Download & process only *first* image
### ✔ Media processing (webp → jpeg, resizing < 15MB)
### ✔ X API v1.1 OAuth 1.0a posting
### ✔ Rate-limiter (token-bucket per API)
### ✔ Telegram structured JSON alerts
### ✔ GitHub Actions scheduled runs
### ✔ Render deployment support
### ✔ Clean modular code easy to debug

---
# 📁 Project Structure

```
reddit-tech-to-x-bot/
│
├── bot.py                  # Main orchestrator
├── config.py               # Configuration loader
├── fetcher.py              # Reddit JSON scraping
├── filtering.py            # Hard filters (reject videos, GIFs, long text...)
├── scorer.py               # Engagement scoring + ranking
├── tweet_builder.py        # Tweet construction + trimming
├── image_downloader.py     # Download first image only
├── media_processor.py      # Convert/resize images for X
├── twitter_client.py       # OAuth1.0a client for X v1.1
├── rate_limiter.py         # Async token-bucket limiter
├── notifier.py             # Telegram JSON alerts
├── logger.py               # Structured JSON logger
│
├── tests/
│    └── test.py            # Live/dry-run testing suite
│
├── .github/workflows/
│    └── schedule.yml       # GitHub Actions cron run
│
├── render.yaml             # Render deployment file
├── requirements.txt        # Dependencies
└── README.md               # Documentation
```

---
# ⚙️ How It Works (System Flow)

### **1. bot.py starts automatically via GitHub Actions cron**
Each scheduled run matches subreddit post times (IST):
- 09:00
- 12:00
- 15:00
- 18:00
- Optional 21:00

### **2. Fetcher retrieves posts from the subreddit**
- Uses Reddit public JSON
- No OAuth or API keys needed
- Sliding-window logic:
  1. Last 10 hours
  2. If none → last 24 hours
  3. If none → last 48 hours

### **3. filtering.py applies HARD FILTERS**
Rejects posts that are:
- Videos (v.redd.it, YouTube, TikTok…)
- GIFs or animated
- Polls
- Crossposts
- NSFW / Spoilers
- Deleted / removed / locked
- Promoted / ads
- Stickied / distinguished
- Text > 200 characters

### **4. scorer.py ranks remaining posts**
Using priority groups:

1. **Top priority:** image/gallery with *no body*
2. **Second priority:** image/gallery with short body
3. **Lowest:** text or link posts

Scoring function:
```
score = (upvotes * 0.65)
      + (comments * 0.35)
      + (upvote_ratio * 10)
      + (post_age_hours * -0.3)
```
The highest‑ranked post is selected.

### **5. tweet_builder.py constructs the final tweet**
Rules enforced strictly:
- If image/gallery → use **title only**
- If text post → use **body only**
- If title-only → use **title**
- Append subreddit-specific hashtags
- Hybrid trimming system ensures tweet ≤ 280 chars:
  1. Trim hashtags one-by-one
  2. If still too long → trim base text character-by-character

### **6. image_downloader.py downloads FIRST image only**
- For gallery → load first `media_id`
- For image posts → use `url_overridden_by_dest`
- Supports `.jpg`, `.jpeg`, `.png`, `.webp`

### **7. media_processor.py prepares image for X**
- Converts `.webp → .jpeg`
- Resizes until < 15MB
- Preserves aspect ratio

### **8. twitter_client.py uploads media & posts tweet**
- Uses OAuth1.0a (v1.1 endpoints)
- Uploads media
- Posts tweet
- On failure → emergency fallback retweet from `@striver_79`

### **9. notifier.py sends alerts to Telegram**
Events include:
- Sorting started
- Post selected
- Tweet builder failed
- No post found
- Errors / exceptions
- Emergency fallback

---
# 🧪 Testing: Live & Dry-Run

Run the live/dry-run test suite:

### **Dry-run (safe, does not post to X)**
```
python tests/test.py --dry-run
```

### **Live mode (⚠ posts to X)**
```
python tests/test.py --post
```

---
# 🔐 Environment Variables (Render/GitHub Actions)

Set these through Render or GitHub Actions secrets:
```
X_API_KEY
X_API_SECRET
X_ACCESS_TOKEN
X_ACCESS_SECRET
TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_CHAT_ID
```
Optional:
```
MAX_IMAGE_SIZE_MB=15
MAX_IMAGES_PER_TWEET=1
TWEET_TRIM_STRATEGY=hybrid
```

---
# 🚀 Deployment

## 1. Deploy to Render
Add all env variables in Render → Environment.

Deploy using **render.yaml**:
```
render.yaml
```
This runs:
```
pip install -r requirements.txt
python bot.py
```

## 2. GitHub Actions Scheduler
`.github/workflows/schedule.yml` triggers bot 5× daily.

You can also trigger manually.

---
# ✔️ Maintenance & Debugging

Because each module is independent, debugging is extremely easy.

Check Render logs (JSON structured):
```
component: fetcher       → Reddit fetching
component: filtering     → Hard filters
component: scorer        → Ranking & scoring
component: tweet_builder → Text & hashtags
component: twitter_client→ Upload & post
component: notifier      → Telegram alerts
```

All failures automatically alert Telegram.

---
# 🙌 Credits

Designed & architected by **ChatGPT (Project Manager Mode)** and implemented for **Akilesh R** with:
- Clean component separation
- Bulletproof async logic
- Production-grade reliability

---
# 🎯 Final Notes

This bot is ready for real-world deployment.
You now have a:
- Fully async
- Fully modular
- Fully debuggable
- Fully automated
Reddit → Twitter posting system.

If you want:
- monitoring dashboards
- retry policies
- multi-account support
- expansion to Mastodon/Bluesky
- analytics

Just ask! 🚀
