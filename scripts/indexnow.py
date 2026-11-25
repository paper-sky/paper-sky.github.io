#!/usr/bin/env python3
"""Submit new Paper Sky URLs to IndexNow. Key file is public, key is never a secret."""
import json, pathlib, sys, urllib.request

KEY = "ps4f9c2a7e18b"
ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = "https://papersky.sok.lv"
ENDPOINT = "https://api.indexnow.org/indexnow"

urls = sys.argv[1:] or ["/", "/methodology/", "/archive/", "/journal/2026-11-25/"]
urls = [u if u.startswith("http") else SITE + ("/" if u == "/" else u) for u in urls]
body = json.dumps({"host": "papersky.sok.lv", "key": KEY, "urlList": urls}).encode()
req = urllib.request.Request(ENDPOINT, data=body,
                             headers={"Content-Type": "application/json; charset=utf-8"})
with urllib.request.urlopen(req, timeout=30) as r:
    print("[indexnow]", r.status, "for", len(urls), "URL(s)")
