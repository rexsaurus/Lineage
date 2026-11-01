#!/usr/bin/env python3
"""Fetch a short list of record pages politely, cache them, and log them in a chapter dossier.

    python $LINEAGE/scripts/fetch_records.py <slug> URL [URL ...] [--title "..."] [--group "..."]
    python $LINEAGE/scripts/fetch_records.py <slug> --list urls.txt      # one URL per line (# comments)
    python $LINEAGE/scripts/fetch_records.py <slug> URL --dry-run        # robots.txt verdicts only

Run from the project folder (or --project DIR). For targeted lookups of specific records
(a census page, a roster, a catalogue entry, a public-domain book), not for harvesting:

  * robots.txt is obeyed for the User-Agent below; a page it disallows is NOT fetched. It is
    logged as blocked and added to research/MANUAL-LOOKUPS.md for a person to look up.
  * At least 2 seconds between requests to the same site (--delay can only raise it).
  * The User-Agent names the project only (book.yaml research.user_agent, default
    "Lineage family research"); it may not contain an email address.
  * No logins, cookies, CAPTCHAs or bot-check workarounds. A 401/403/429 or a challenge page
    is logged as blocked and left alone; it goes on the manual-lookups list.
  * At most 50 URLs a run: a whole database is not a record.

Each page is saved under facts/records/_raw/<slug>/ (keep _raw/ out of git) with a
<file>.meta.json beside it (url, final url, retrieved, HTTP status, type, bytes, sha256). If
dossiers/<slug>/ exists, every URL also gets a SOURCES.csv row and a RESEARCH-LOG.md line.
Run export_sources.py afterwards to put the shareable text in git.
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402
import dossier as D  # noqa: E402

MIN_DELAY = 2.0
MAX_URLS = 50
CHALLENGE = re.compile(rb"cf-chl|challenge-platform|captcha|are you a robot|verify you are human", re.I)
_robots, _last = {}, {}


def user_agent():
    ua = ((P.load_book().get("research") or {}).get("user_agent") or "").strip() or "Lineage family research"
    if "@" in ua:
        sys.exit("book.yaml research.user_agent contains an email address; name the project only")
    return ua


def allowed(url, ua):
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser(base + "/robots.txt")
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=30) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            rp.parse([] if e.code == 404 else ["User-agent: *", "Disallow: /"])   # unreadable: assume no
        except Exception:
            rp.parse(["User-agent: *", "Disallow: /"])
        _robots[base] = rp
        _last[parts.netloc] = time.time()
    return _robots[base].can_fetch(ua, url)


def wait(netloc, delay):
    gap = time.time() - _last.get(netloc, 0)
    if gap < delay:
        time.sleep(delay - gap)
    _last[netloc] = time.time()


def filename(url, ctype):
    p = urlparse(url)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", (p.netloc + p.path + ("_" + p.query if p.query else "")).strip("/"))[:150]
    ext = {"text/html": ".html", "application/pdf": ".pdf", "application/json": ".json", "text/plain": ".txt",
           "text/csv": ".csv", "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif"}.get(ctype, "")
    return stem if not ext or stem.lower().endswith(ext) else stem + ext


def manual_lookup(url, why):
    f = Path("research/MANUAL-LOOKUPS.md")
    f.parent.mkdir(exist_ok=True)
    if not f.exists():
        tpl = Path(__file__).resolve().parent.parent / "templates" / "research" / "MANUAL-LOOKUPS.md"
        f.write_text(tpl.read_text() if tpl.exists() else "# Manual lookups\n\n")
    if url not in f.read_text():
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"| ? | {url} | {urlparse(url).netloc} | (fill in) | {why}; found by fetch_records.py {datetime.date.today()} |\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    P.add_project_arg(ap)
    ap.add_argument("slug", help="the chapter dossier (and _raw/ subfolder) these records belong to")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--list", help="a file of URLs, one per line")
    ap.add_argument("--title", default="", help="title for the SOURCES.csv row (one URL)")
    ap.add_argument("--group", default="", help="THE RECORDS heading for these sources")
    ap.add_argument("--delay", type=float, default=MIN_DELAY)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    P.enter_project(a.project)
    urls = list(a.urls)
    if a.list:
        urls += [l.strip() for l in open(a.list) if l.strip() and not l.lstrip().startswith("#")]
    if not urls:
        sys.exit("no URLs")
    if len(urls) > MAX_URLS:
        sys.exit(f"{len(urls)} URLs: at most {MAX_URLS} a run. These are targeted lookups, not a crawl.")
    ua, delay = user_agent(), max(a.delay, MIN_DELAY)
    has_dossier = D.ddir(a.slug).exists()
    raw = Path("facts/records/_raw") / a.slug
    for url in urls:
        site = urlparse(url).netloc
        if not allowed(url, ua):
            print(f"blocked by robots.txt: {url}")
            if not a.dry_run:
                manual_lookup(url, "robots.txt disallows automated fetching")
                if has_dossier:
                    D.log(a.slug, "fetch_records", url, site, "NOT FETCHED (robots.txt); on the manual-lookups list")
                    D.add_source(a.slug, title=a.title or url, url=url, status="blocked", group=a.group,
                                 used_for="not reached: robots.txt")
            continue
        if a.dry_run:
            print(f"allowed: {url}")
            continue
        wait(site, delay)
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body, status, final = r.read(), r.status, r.geturl()
                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
        except urllib.error.HTTPError as e:
            why = f"HTTP {e.code}" + (" (login or bot check; not bypassed)" if e.code in (401, 403, 429) else "")
            print(f"{why}: {url}")
            if e.code in (401, 403, 429):
                manual_lookup(url, why)
            if has_dossier:
                D.log(a.slug, "fetch_records", url, site, f"BLOCKED {why}" if e.code in (401, 403, 429) else why)
                D.add_source(a.slug, title=a.title or url, url=url, status="blocked", group=a.group, used_for=why)
            continue
        except Exception as e:
            print(f"failed: {url}: {e}")
            if has_dossier:
                D.log(a.slug, "fetch_records", url, site, f"failed: {e}")
            continue
        if ctype.startswith("text/html") and CHALLENGE.search(body[:20000]):
            print(f"challenge page (not bypassed): {url}")
            manual_lookup(url, "bot check; not bypassed")
            if has_dossier:
                D.log(a.slug, "fetch_records", url, site, "BLOCKED (bot check; not bypassed)")
                D.add_source(a.slug, title=a.title or url, url=url, status="blocked", group=a.group,
                             used_for="not reached: bot check")
            continue
        raw.mkdir(parents=True, exist_ok=True)
        out = raw / filename(final, ctype)
        out.write_bytes(body)
        sha = hashlib.sha256(body).hexdigest()
        meta = {"url": url, "final_url": final, "retrieved": datetime.datetime.now().isoformat(timespec="seconds"),
                "status": status, "content_type": ctype, "bytes": len(body), "sha256": sha, "user_agent": ua}
        Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(f"saved {out} ({len(body):,} bytes)")
        if has_dossier:
            D.log(a.slug, "fetch_records", url, site, f"found; {out} (sha256 {sha[:12]}…)")
            D.add_source(a.slug, title=a.title or url, url=url, local_path=str(out), status="found", group=a.group)


if __name__ == "__main__":
    main()
