#!/usr/bin/env python3
"""Photo backfill: find the full-size file for every low-resolution photograph (longest edge under 1200 px).

  python3 photo_backfill.py --project .            # look, and write data/photo_backfill.json
  python3 photo_backfill.py --project . --dry-run  # look, write nothing
  python3 photo_backfill.py --project . --no-fetch # only the project's own files, no network

Low-resolution copies are almost always a derivative saved instead of the original: the inline preview of a mail
attachment, or the thumbnail of an archive page. For each one, in order:

1. The project's own files: a larger image of the same picture (perceptual hash, same shape) anywhere in the project,
   most often the mail attachment itself (saved under archive-replies/_attachments/) or the archive's full download.
2. The holding institution, when the photograph's source URL is one whose full-size file sits at a predictable
   address: the Internet Archive (the item's largest image) and the Library of Congress / Chronicling America (the
   IIIF full-size image). robots.txt is honoured, one request per 2 seconds per host, a descriptive User-Agent; nothing
   behind a login. A file found is saved under photos/backfill/ and recorded in data/image_sources.csv.
3. Otherwise "not_located": the photo viewer and the photo cards then say, in red, that the full scan has not been
   found. A known-small scan that says so is fine; a blurry one presented as finished is not.

Nothing is ever upscaled or "enhanced" to fill the gap: that would be an invented image beside real scans.
Output: data/photo_backfill.json  {scan path: {state: ok | not_located, full, width, height, how, checked}}.
"""
import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402

LINEAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(LINEAGE / "app"))

UA = "Lineage photo backfill (family-history research; +https://github.com/rexsaurus/Lineage)"
IMG = re.compile(r"\.(jpe?g|png|tiff?|webp)$", re.I)
SKIP_DIRS = {".git", ".lineage", ".thumbs", "output", "node_modules", "lineage-assets", "backfill-rejected"}
_last = {}
_robots = {}


def _polite(url):
    host = urllib.parse.urlsplit(url).netloc
    rp = _robots.get(host)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = False
        _robots[host] = rp
    if rp is False or not rp.can_fetch(UA, url):
        return False
    wait = 2.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.time()
    return True


def _get(url, binary=False):
    if not _polite(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read()
    except Exception:
        return None
    return data if binary else data.decode("utf-8", "replace")


def _size(data):
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        return im.size


def from_institution(url):
    """(bytes, page url) of the largest image the institution serves for this record, or None."""
    u = urllib.parse.urlsplit(url or "")
    if u.netloc.endswith("archive.org"):
        m = re.search(r"/(?:details|download)/([^/?#]+)", u.path)
        meta = _get(f"https://archive.org/metadata/{m.group(1)}") if m else None
        if not meta:
            return None
        files = [f for f in json.loads(meta).get("files", []) if IMG.search(f.get("name", "")) and "thumb" not in f.get("name", "").lower()]
        if not files:
            return None
        best = max(files, key=lambda f: int(f.get("size") or 0))
        full = f"https://archive.org/download/{m.group(1)}/{urllib.parse.quote(best['name'])}"
        data = _get(full, binary=True)
        return (data, full) if data else None
    if u.netloc.endswith("loc.gov"):
        j = _get(url.split("?")[0].rstrip("/") + "/?fo=json")
        if not j:
            return None
        try:
            d = json.loads(j)
        except ValueError:
            return None
        cands = []
        for res in (d.get("resources") or []) + [d.get("item") or {}]:
            for f in (res.get("files") or []) if isinstance(res, dict) else []:
                for v in f if isinstance(f, list) else [f]:
                    if isinstance(v, dict) and IMG.search(str(v.get("url", "")).split("?")[0]):
                        cands.append(v)
        for v in (d.get("image_url") or []):
            cands.append({"url": v, "width": 0})
        if not cands:
            return None
        best = max(cands, key=lambda v: int(v.get("width") or 0) * int(v.get("height") or 1))
        full = best["url"] if best["url"].startswith("http") else "https:" + best["url"]
        data = _get(full, binary=True)
        return (data, full) if data else None
    return None


def main():
    ap = argparse.ArgumentParser(description="Find the full-size file for each low-resolution photograph")
    add_project_arg(ap)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true", help="only look in the project's own files")
    a = ap.parse_args()
    root = enter_project(a.project).resolve()
    import server  # noqa: E402  (the app: the Project class)
    import photos  # noqa: E402
    project = server.Project(root)
    reg = photos.registry(project)
    low = [p for p in reg["photos"] if p["isLowRes"]]
    out_f = root / "data" / "photo_backfill.json"
    state = json.loads(out_f.read_text()) if out_f.exists() else {}

    # every image in the project, sized and hashed (cached in .lineage/photo_meta.json)
    files = [p.relative_to(root).as_posix() for p in root.rglob("*")
             if p.is_file() and IMG.search(p.name) and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS)]
    meta = every = photos._meta(project, files)
    # never a derivative: restorations (and the restored twin of an _orig/ scan), print files, generated or stylised
    # renderings. A "larger copy" that is one of these is an invented image, not the original scan.
    derived = {photos.key(p["image"]) for p in reg["photos"] if p["restored"]}
    rj = root / "data" / "image_restorations.json"
    derived |= {photos.key(k) for k in (json.loads(rj.read_text()) if rj.exists() else {})}
    prompts = root / "data" / "image_prompts.json"
    gen_ids = set(json.loads(prompts.read_text())) if prompts.exists() else set()
    cat = root / "data" / "image_catalog.csv"
    crows = list(csv.DictReader(open(cat, encoding="utf-8"))) if cat.exists() else []
    bad_keys = set()
    for r in crows:
        text = " ".join([r.get("note") or "", r.get("captions") or "", r.get("kind") or ""])
        if r.get("key") in gen_ids or re.search(r"illustration|generated|styli[sz]ed|rendering|engraving", text, re.I):
            bad_keys.add(r.get("key"))
        elif re.search(r"\brestored\b", text, re.I) and "/_orig/" not in (r.get("path") or ""):
            derived.add(photos.key(r.get("path")))
    renderings = {photos.key(r.get("path")) for r in crows if r.get("key") in bad_keys}   # every copy of a rendering
    derived |= renderings
    look = [every[f] for f in every if photos.key(f) in renderings]
    near = lambda m: any(m[2] is not None and bin(m[2] ^ x[2]).count("1") <= 6 and abs(m[0] / m[1] - x[0] / x[1]) < 0.03 * x[0] / x[1] for x in look)
    meta = {f: m for f, m in meta.items() if photos.key(f) not in derived and "-restored" not in f
            and not f.startswith(("photos/print/", "photos/generated/", "images/print/")) and not near(m)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    found = located = 0
    for p in low:
        scan = photos.key(p["original"] or p["image"])
        m = every.get(p["original"] or p["image"]) or every.get(scan)
        if not m:
            continue
        w, h, dh = m
        best = None
        for f, (fw, fh, fdh) in meta.items():
            if max(fw, fh) < max(photos.LOW_RES, 1.5 * max(w, h)) or abs(fw / fh - w / h) > 0.03 * (w / h):
                continue
            if bin(dh ^ fdh).count("1") <= 6 and (best is None or fw * fh > best[1] * best[2]):
                best = (f, fw, fh)
        how = "project file"
        if not best and not a.no_fetch and p.get("source") and p["source"].get("url"):
            got = from_institution(p["source"]["url"])
            if got:
                data, full_url = got
                fw, fh = _size(data)
                if max(fw, fh) >= max(photos.LOW_RES, 1.5 * max(w, h)):
                    ext = IMG.search(urllib.parse.urlsplit(full_url).path)
                    rel = f"photos/backfill/{Path(scan).stem}{ext.group(0).lower() if ext else '.jpg'}"
                    if not a.dry_run:
                        (root / rel).parent.mkdir(parents=True, exist_ok=True)
                        (root / rel).write_bytes(data)
                        src = root / "data" / "image_sources.csv"
                        new = not src.exists()
                        with open(src, "a", newline="", encoding="utf-8") as fh_:
                            wr = csv.writer(fh_)
                            if new:
                                wr.writerow(["path", "url", "title", "creator", "date", "rights", "retrieved", "chapter"])
                            wr.writerow([rel, full_url, p["title"], (p["source"] or {}).get("institution", ""), p["date"], "", now[:10], ""])
                    best, how = (rel, fw, fh), "re-fetched from " + urllib.parse.urlsplit(full_url).netloc
        if best:
            state[scan] = {"state": "ok", "full": best[0], "width": best[1], "height": best[2], "how": how, "checked": now}
            found += 1
            print(f"found   {p['title'][:60]:60}  {w}x{h} -> {best[1]}x{best[2]}  ({how}: {best[0]})")
        else:
            state[scan] = {"state": "not_located", "width": w, "height": h, "checked": now}
            located += 1
            print(f"missing {p['title'][:60]:60}  {w}x{h}")
    print(f"low resolution: {len(low)} · full size found: {found} · not located: {located}")
    if not a.dry_run:
        out_f.write_text(json.dumps(dict(sorted(state.items())), indent=1) + "\n", encoding="utf-8")
        print(f"-> {out_f.relative_to(root)}")


if __name__ == "__main__":
    main()
