#!/usr/bin/env python3
"""Paper Sky post-publish audit — adapted from the be850 audit pattern.

Usage:
  python3 audit_page.py                  # live audit of the latest chapter
  python3 audit_page.py --date 2026-11-25
  python3 audit_page.py --source         # source-only checks (no network)

Live checks use curl, not urllib: python's TLS fingerprint gets Cloudflare
challenges served as 404 (exact failure documented in be850/audit_chapter.py).
Exit 1 on any FAIL; WARNs do not fail. Writes data/audit-<date>.json.
"""
import argparse, datetime, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "data"
DOMAIN = "https://papersky.sok.lv"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

def fetch(url, tries=3, wait=10):
    last = None
    for i in range(tries):
        try:
            p = subprocess.run(["curl", "-sS", "-A", UA, "--max-time", "25",
                                "-w", "\n__STATUS__%{http_code}", url],
                               capture_output=True, text=True, timeout=30)
            out = p.stdout
            if "__STATUS__" in out:
                body, _, code = out.rpartition("\n__STATUS__")
                return int(code.strip() or 0), body
            last = f"curl exit {p.returncode}"
        except Exception as e:
            last = type(e).__name__
        if i + 1 < tries:
            import time; time.sleep(wait)
    return 0, last or "no response"

def latest_date():
    ds = []
    for p in (ROOT / "_journal").glob("*.md"):
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", p.read_text(encoding="utf-8"), re.M)
        if m: ds.append(m.group(1))
    return max(ds) if ds else None

def frontmatter(text):
    out = {}
    for line in text.splitlines():
        if line.strip() == "": break
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out

def record(checks, label, ok, fatal=True, detail=""):
    checks.append({"check": label, "status": "PASS" if ok else ("FAIL" if fatal else "WARN"),
                   "detail": detail[:180]})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--source", action="store_true")
    a = ap.parse_args()
    date = a.date or latest_date()
    if not date:
        raise SystemExit("no journal chapter found")
    checks = []

    # --- source checks (deterministic, no network) ---
    jp = ROOT / "_journal" / f"{date}.md"
    txt = jp.read_text(encoding="utf-8") if jp.exists() else ""
    fm = frontmatter(txt)
    body = txt.split("---", 2)[-1]
    for key in ("title", "cold_open", "hook", "sky_note", "description"):
        record(checks, f"frontmatter.{key}", bool(fm.get(key)))
    record(checks, "frontmatter.article", fm.get("article", "").lower() == "true")
    words = len(re.findall(r"\b[\w-]+\b", body))
    record(checks, "body >= 300 words", words >= 300, fatal=False, detail=str(words))
    low = body.lower()
    # disclaimer and the Sky cross-link live in the LAYOUT, not in the markdown body
    layout_text = ((ROOT / "_layouts" / "default.html").read_text(encoding="utf-8")
                   + (ROOT / "_layouts" / "journal.html").read_text(encoding="utf-8")).lower()
    record(checks, "disclaimer present", "not investment advice" in low or "not investment advice" in layout_text)
    record(checks, "ledger $1,000", "$1,000" in body or "$1000" in body)
    record(checks, "Sky cross-link", "skychapter.sok.lv" in low or "skychapter.sok.lv" in layout_text)
    record(checks, "Vita cross-link", "vita.sok.lv" in low or "vita.sok.lv" in layout_text)
    record(checks, "chapter has Beyond crypto", "Beyond crypto" in body)
    notes = sorted((ROOT / "_notes").glob("*.md"))
    record(checks, "notes >= 5", len(notes) >= 5, detail=str(len(notes)))
    style = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
    record(checks, "cookiebar [hidden] CSS", "#cookiebar[hidden]{display:none" in style)
    for n in notes:
        nf = frontmatter(n.read_text(encoding="utf-8"))
        record(checks, f"note {n.stem} frontmatter", bool(nf.get("title") and nf.get("description")))

    if not a.source:
        url = f"{DOMAIN}/journal/{date}/"
        code, html = fetch(url)
        record(checks, "chapter HTTP 200", code == 200, detail=str(code))
        if code == 200:
            record(checks, "canonical", f'<link rel="canonical" href="{url}">' in html)
            record(checks, "H1", bool(re.search(r"<h1[^>]*>.+</h1>", html, re.S)))
            blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
            types = []
            for b in blocks:
                try: types.append(json.loads(b).get("@type"))
                except Exception: types.append("INVALID")
            record(checks, "JSON-LD WebSite+Article", "WebSite" in types and "Article" in types,
                   detail=str(types))
            record(checks, "JSON-LD no duplicate WebSite", types.count("WebSite") == 1,
                   detail=str(types))
            record(checks, "OG tags", all(x in html for x in ("og:title", "og:image", "og:url")))
            record(checks, "twitter:image", "twitter:image" in html)
            record(checks, "cookie bar", 'id="cookiebar"' in html)
            record(checks, "consent key", "ps_cookie_consent" in html)
            record(checks, "live disclaimer", "not investment advice" in html.lower())
            record(checks, "live Beyond crypto", "Beyond crypto" in html)
        sm, smap = fetch(DOMAIN + "/sitemap.xml")
        record(checks, "sitemap contains chapter", sm == 200 and url in smap, detail=str(sm))
        rr, rss = fetch(DOMAIN + "/rss.xml")
        record(checks, "rss contains chapter", rr == 200 and url in rss, detail=str(rr))
        kc, _ = fetch(DOMAIN + "/ps4f9c2a7e18b.txt")
        record(checks, "IndexNow key 200", kc == 200, detail=str(kc))
        nc, nh = fetch(DOMAIN + "/notes/rwa/")
        record(checks, "note page 200", nc == 200, detail=str(nc))

    fails = [c for c in checks if c["status"] == "FAIL"]
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / f"audit-{date}.json"
    out.write_text(json.dumps({"date": date, "checked_at": datetime.datetime.now(datetime.timezone.utc)
                               .isoformat(), "checks": checks, "fails": len(fails)},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[audit] {date}: {len(checks)} checks, {len(fails)} FAIL -> {out}")
    for c in fails[:10]:
        print("  FAIL", c["check"], c["detail"])
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
