#!/usr/bin/env python3
"""Post post/post.txt (+ post/card.png) to X once per day.

Runs inside GitHub Actions. Needs four repo secrets:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
If any is missing it exits quietly (nothing is posted).
Writes posted/<date>.json after a successful post so the same day never posts twice.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "post" / "post.txt"
CARD = ROOT / "post" / "card.png"
LOG_DIR = ROOT / "posted"

keys = [os.environ.get(k, "").strip() for k in
        ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")]
if not all(keys):
    print("::notice::X secrets not set yet — skipping the post.")
    sys.exit(0)
if os.environ.get("X_POSTING_PAUSED", "").lower() in ("1", "true", "yes"):
    print("::notice::Posting is paused (repo variable X_POSTING_PAUSED).")
    sys.exit(0)

today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
log = LOG_DIR / f"{today}.json"
if log.exists() and os.environ.get("FORCE_POST") != "1":
    print(f"::notice::Already posted today ({log.name}) — skipping.")
    sys.exit(0)

if not TEXT.exists():
    print("::notice::No post/post.txt — nothing to post.")
    sys.exit(0)
text = TEXT.read_text(encoding="utf-8").strip()
if not text:
    print("::notice::post.txt is empty — nothing to post.")
    sys.exit(0)

import requests  # noqa: E402
from requests_oauthlib import OAuth1  # noqa: E402

auth = OAuth1(*keys)
media_ids = []
if CARD.exists():
    # X API v2 media upload (one-shot, images under 5 MB).
    with CARD.open("rb") as f:
        r = requests.post("https://api.x.com/2/media/upload", auth=auth,
                          files={"media": ("card.png", f, "image/png")},
                          data={"media_category": "tweet_image", "media_type": "image/png"},
                          timeout=60)
    if r.ok:
        body = r.json()
        mid = (body.get("data") or {}).get("id") or body.get("media_id_string")
        if mid:
            media_ids.append(str(mid))
    if not media_ids:
        # Fallback: legacy v1.1 upload endpoint.
        with CARD.open("rb") as f:
            r2 = requests.post("https://upload.twitter.com/1.1/media/upload.json", auth=auth,
                               files={"media": f}, timeout=60)
        if r2.ok and r2.json().get("media_id_string"):
            media_ids.append(r2.json()["media_id_string"])
        else:
            print(f"::warning::Image upload failed (v2 {r.status_code}: {r.text[:300]} | "
                  f"v1.1 {r2.status_code}: {r2.text[:300]}). Posting text only.")

payload = {"text": text}
if media_ids:
    payload["media"] = {"media_ids": media_ids}
r = requests.post("https://api.x.com/2/tweets", auth=auth, json=payload, timeout=60)
if not r.ok:
    print(f"::error::X rejected the post ({r.status_code}): {r.text[:600]}")
    sys.exit(1)

tweet = r.json().get("data", {})
LOG_DIR.mkdir(exist_ok=True)
log.write_text(json.dumps({"date": today, "id": tweet.get("id"), "text": text,
                           "image": bool(media_ids)}, indent=1), encoding="utf-8")
print(f"Posted: https://x.com/i/web/status/{tweet.get('id')}")
