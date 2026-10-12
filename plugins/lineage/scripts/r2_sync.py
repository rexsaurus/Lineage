#!/usr/bin/env python3
"""Every photograph, image and published PDF of a project in a Cloudflare R2 bucket, so a published site
loads them from there rather than carrying them itself.

    python r2_sync.py --project DIR             # upload new or changed files; write data/r2_manifest.csv
    python r2_sync.py --project DIR --dry-run   # show the plan only (no credentials needed)

Layout in the bucket, under <prefix>/ (settings.publish.r2.prefix, default: the slug of the title):
    originals/<path>        photographs and scans as received (and the untouched _orig/ copy of a restored one)
    restorations/<path>     digitally restored versions (restore_photos.py; data/image_restorations.json)
    illustrations/<path>    generated or drawn images, never photographs
    thumbnails/<same>       ~480 px JPEG copies for grids, cards and lists
    chapters/<stem>.pdf     one PDF per story (chapter_pdfs.py, from settings.publish.chapters_dir)
    book/<slug>-v<VERSION>.pdf and book/<slug>.pdf   the compressed edition (book_edition.py)
    <key>                   each settings.publish.r2.extra_documents entry ({"path": ..., "key": ...})
<path> is the file's project path with any _orig/ segment removed, so keys are stable and never collide.
A file whose content changes is re-uploaded (its sha256 is kept in the object metadata and the manifest).

What counts as an illustration (data, not path rules):
  - photos/photo_index.csv rows with kind "illustration", or a subject starting "Illustration", or "generated"
    in needs_attention/comment (source_file, print_file and a print copy photos/print/<id>.* are counted);
  - data/image_catalog.csv rows of kind "generated" or "artwork" (image_manager.py);
  - files listed in data/image_prompts.json (generate_images.py) and files named IMG-*;
  - settings.publish.r2.illustration_globs (project-relative globs), if any.
A restoration is a file logged in data/image_restorations.json, named *-restored, or with an _orig/ copy beside it.

Manifest data/r2_manifest.csv: path, category, where, key, thumb_key, sha256, bytes, url, thumb_url
(site/build_instance.py --assets reads it; face_focus.py reads it). "where" is the story the image appears in
(photo_index chapter, or a reference in chapters/*.typ), else its top folder.

Credentials: settings.publish.r2.env_file (default ~/.config/lineage/r2.env) with R2_ENDPOINT, R2_BUCKET,
R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and, once public access is on, R2_PUBLIC_BASE. Never in git. Needs boto3;
thumbnails need Pillow (or macOS sips).
"""
import argparse
import csv
import fnmatch
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402
import _publish  # noqa: E402

IMG = re.compile(r"\.(jpe?g|png|gif|webp|tiff?|heic)$", re.I)
SKIP = ("/.thumbs/", "/_previews/", "/render/", "/.lineage/", "/.git/")
FIELDS = ["path", "category", "where", "key", "thumb_key", "sha256", "bytes", "url", "thumb_url"]
REF = re.compile(r'"/?([^"]+\.(?:jpe?g|png|gif|webp|tiff?))"', re.I)


def read_env(p):
    out = {}
    for line in Path(p).read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows(p):
    p = Path(p)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def illustrations(cfg):
    out = set()
    for r in rows("photos/photo_index.csv"):
        flag = ((r.get("kind") or "").lower() == "illustration"
                or re.match(r"\s*illustration", r.get("subject") or "", re.I)
                or "generated" in ((r.get("needs_attention") or "") + " " + (r.get("comment") or "")).lower())
        if flag:
            out |= {(r.get(k) or "").lstrip("/") for k in ("print_file", "source_file")} - {""}
            if r.get("id"):                             # a print copy named after the row: photos/print/<id>.*
                out |= {f.as_posix() for f in Path("photos/print").glob(r["id"] + ".*")}
    for r in rows("data/image_catalog.csv"):
        if (r.get("kind") or "") in ("generated", "artwork"):
            out.add(r.get("path", "").lstrip("/"))
    pj = Path("data/image_prompts.json")
    if pj.exists():
        try:
            d = json.loads(pj.read_text())
            for k, v in (d.items() if isinstance(d, dict) else []):
                f = (v.get("file") or v.get("path")) if isinstance(v, dict) else None
                out.add((f or k).lstrip("/"))
        except ValueError:
            pass
    globs = cfg["r2"].get("illustration_globs") or []
    return out, globs


def restorations():
    out = set()
    rj = Path("data/image_restorations.json")
    if rj.exists():
        try:
            for k, v in json.loads(rj.read_text()).items():
                out.add(((v or {}).get("file") if isinstance(v, dict) else None) or k)
        except ValueError:
            pass
    return out


def where_map():
    """project path -> the story it appears in."""
    out = {}
    for r in rows("photos/photo_index.csv"):
        ch = (r.get("chapter") or "").strip()
        if ch:
            for k in ("print_file", "source_file"):
                if r.get(k):
                    out.setdefault(r[k].lstrip("/"), Path(ch).stem)
    for f in sorted(Path("chapters").glob("*.typ")) if Path("chapters").is_dir() else []:
        for m in REF.finditer(f.read_text(encoding="utf-8", errors="ignore")):
            out.setdefault(m.group(1).lstrip("/"), f.stem)
    return out


def classify(rel, ctx):
    illus, globs, restored, every, where_of, prefix = ctx
    p = Path(rel)
    if "_orig" in p.parts:
        cat = "originals"
    elif rel in restored or p.stem.endswith("-restored") or (p.parent / "_orig" / p.name).as_posix() in every:
        cat = "restorations"
    elif rel in illus or p.name.startswith("IMG-") or any(fnmatch.fnmatch(rel, g) for g in globs):
        cat = "illustrations"
    else:
        cat = "originals"
    clean = "/".join(x for x in p.parts if x != "_orig")
    where = where_of.get(clean) or where_of.get(rel) or (p.parts[0] if len(p.parts) > 1 else "other")
    return cat, where, f"{prefix}/{cat}/{clean}"


def plan_for(cfg):
    prefix = cfg["r2"]["prefix"]
    skip = SKIP + tuple(cfg["r2"].get("skip") or ())
    files = set()
    for d in cfg["r2"]["scan"]:
        base = Path(d)
        if not base.exists():
            continue
        for f in base.rglob("*"):
            rel = f.as_posix()
            if f.is_file() and IMG.search(f.name) and not any(s in "/" + rel for s in skip):
                files.add(rel)
    illus, globs = illustrations(cfg)
    ctx = (illus, globs, restorations(), files, where_map(), prefix)
    plan = []
    for rel in sorted(files):
        cat, where, key = classify(rel, ctx)
        plan.append({"path": rel, "category": cat, "where": where, "key": key})
    docs = []
    ver = _publish.version()
    if ver:
        ed = Path("output") / f"{cfg['slug']}-v{ver}.pdf"
        docs += [(ed, f"{prefix}/book/{ed.name}"), (ed, f"{prefix}/book/{cfg['slug']}.pdf")]
    cd = Path(cfg["chapters_dir"])
    if cd.is_dir():
        docs += [(f, f"{prefix}/chapters/{f.name}") for f in sorted(cd.glob("*.pdf"))]
    for x in cfg["r2"].get("extra_documents") or []:
        if isinstance(x, dict) and x.get("path"):
            docs.append((Path(x["path"]), f"{prefix}/{(x.get('key') or Path(x['path']).name).lstrip('/')}"))
    for p, key in docs:
        if p.is_file():
            plan.append({"path": p.as_posix(), "category": "documents", "where": key.split("/")[1], "key": key})
        else:
            print(f"  (not found, skipped: {p})")
    return plan


def thumbnail(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(src)
        im.thumbnail((480, 480))
        im.convert("RGB").save(dst, "JPEG", quality=78)
        return True
    except Exception:
        pass
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", "-Z", "480", str(src), "--out", str(dst)],
                       capture_output=True)
    return dst.exists()


def main():
    ap = argparse.ArgumentParser(description="sync a project's images and PDFs to Cloudflare R2")
    add_project_arg(ap)
    ap.add_argument("--dry-run", action="store_true", help="show the plan; upload nothing")
    a = ap.parse_args()
    root = enter_project(a.project)
    cfg = _publish.settings(root)
    prefix = cfg["r2"]["prefix"]
    plan = plan_for(cfg)
    counts = {}
    for x in plan:
        counts[x["category"]] = counts.get(x["category"], 0) + 1
    print(f"{len(plan)} files under {prefix}/: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "nothing to sync"))
    if a.dry_run:
        for x in plan[:60]:
            print(f"  {x['category']:13} {x['key']}")
        if len(plan) > 60:
            print(f"  … and {len(plan) - 60} more")
        return
    envp = Path(cfg["r2"]["env_file"])
    if not envp.exists():
        print(f"no R2 credentials at {envp}: skipping the upload (see docs/HOWTO.md, Publishing a family site)")
        return
    e = read_env(envp)
    missing = [k for k in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY") if not e.get(k)]
    if missing:
        print(f"{envp} lacks {', '.join(missing)}: skipping the upload")
        return
    try:
        import boto3
    except ImportError:
        print("boto3 is not installed (pip install boto3): skipping the upload")
        return
    s3 = boto3.client("s3", endpoint_url=e["R2_ENDPOINT"], aws_access_key_id=e["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=e["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = e.get("R2_BUCKET") or "lineage"
    existing, tok = {}, None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix + "/"}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            existing[o["Key"]] = o["Size"]
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    man_p = Path("data/r2_manifest.csv")
    old = {r["path"]: r for r in rows(man_p)}
    thumbs = Path(".lineage/r2-thumbs")

    def put(src, key, h, src_rel):
        s3.upload_file(str(src), bucket, key, ExtraArgs={
            "ContentType": mimetypes.guess_type(Path(key).name)[0] or "application/octet-stream",
            "Metadata": {"sha256": h, "source": src_rel[:900]}, "CacheControl": "public, max-age=31536000"})

    def one(x):
        p = Path(x["path"])
        h = sha(p)
        x.update({"sha256": h, "bytes": p.stat().st_size, "thumb_key": ""})
        same = x["key"] in existing and old.get(x["path"], {}).get("sha256") == h
        if not same:
            put(p, x["key"], h, x["path"])
        if x["category"] in ("originals", "restorations", "illustrations"):
            tkey = x["key"].replace(prefix + "/", prefix + "/thumbnails/", 1)
            tkey = re.sub(r"\.(png|gif|webp|tiff?|heic|jpeg)$", ".jpg", tkey, flags=re.I)
            x["thumb_key"] = tkey
            if same and tkey in existing:
                return "same"
            t = thumbs / (h[:16] + ".jpg")
            if t.exists() or thumbnail(p, t):
                put(t, tkey, h, x["path"] + " (thumbnail)")
        return "same" if same else "up"

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, plan))
    base = e.get("R2_PUBLIC_BASE", "").rstrip("/")
    for x in plan:
        x["url"] = f"{base}/{x['key']}" if base else ""
        x["thumb_url"] = f"{base}/{x['thumb_key']}" if base and x.get("thumb_key") else ""
    man_p.parent.mkdir(exist_ok=True)
    with open(man_p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(plan)
    up = res.count("up")
    print(f"R2: {up} uploaded, {len(res) - up} unchanged -> data/r2_manifest.csv"
          + ("" if base else "  (no R2_PUBLIC_BASE yet: public access not enabled, so no URLs)"))


if __name__ == "__main__":
    main()
