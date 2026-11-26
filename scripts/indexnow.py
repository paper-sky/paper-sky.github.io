#!/usr/bin/env python3
"""IndexNow with content-hash manifest — eli5.sok.lv pattern.

Only URLs whose source hash changed are submitted. No args = submit the delta.
  --seed   write the manifest from current sources without sending anything
  --all    submit every known URL regardless of hashes
  paths    explicit URL paths (old behaviour), still submitted unconditionally
Key file is public; the key is not a secret.
"""
import argparse, hashlib, json, pathlib, re, urllib.request

KEY = "ps4f9c2a7e18b"
ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = "https://papersky.sok.lv"
ENDPOINT = "https://api.indexnow.org/indexnow"
MANIFEST = ROOT / "indexnow_manifest.json"

def sources():
    m = {"/": ROOT / "index.html",
         "/methodology/": ROOT / "methodology.md",
         "/archive/": ROOT / "archive.html"}
    for p in (ROOT / "_journal").glob("*.md"):
        m[f"/journal/{p.stem}/"] = p
    for p in (ROOT / "_notes").glob("*.md"):
        m[f"/notes/{p.stem}/"] = p
    return m

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_manifest():
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}

def submit(urls):
    if not urls:
        print("[indexnow] nothing changed")
        return True
    # delta mode yields relative paths; IndexNow requires absolute URLs (else 422)
    urls = [u if u.startswith("http") else SITE + u for u in urls]
    body = json.dumps({"host": "papersky.sok.lv", "key": KEY, "urlList": urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("[indexnow]", r.status, "for", len(urls), "URL(s)")
        return r.status in (200, 202)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("paths", nargs="*")
    a = ap.parse_args()

    src = sources()
    old = load_manifest()
    current = {u: digest(p) for u, p in src.items()}

    if a.paths:
        urls = [p if p.startswith("http") else SITE + ("/" if p == "/" else p) for p in a.paths]
        if submit(urls):
            old.update({u: current.get(u, old.get(u, "")) for u in urls})
            MANIFEST.write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    changed = [u for u, h in current.items() if a.all or old.get(u) != h]
    if a.seed:
        MANIFEST.write_text(json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[indexnow] seeded {len(current)} URL hash(es), nothing sent")
        return
    if submit(changed):
        MANIFEST.write_text(json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[indexnow] manifest updated ({len(current)} URL hash(es))")

if __name__ == "__main__":
    main()
