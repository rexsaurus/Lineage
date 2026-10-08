#!/usr/bin/env python3
"""Image manager for Book-o-Matic: one catalogue of every image, a guard against regenerating or
re-sourcing what already exists, and a sync to Google Drive.

  python3 image_manager.py catalog            # rescan; write data/image_catalog.csv (+ .json)
  python3 image_manager.py check --id IMG-regina-1
  python3 image_manager.py check --prompt "A long black Cadillac funeral coach ..."
  python3 image_manager.py check --url https://archive.org/...   (sourced images)
  python3 image_manager.py check --file ~/BookDrop/IMG_0756.jpeg  (same bytes already filed?)
  python3 image_manager.py unused             # catalogued images no chapter uses
  python3 image_manager.py missing            # chapter references with no file, and PLATE-TODOs
  python3 image_manager.py drive-sync   # upload new/changed files; record Drive ids (book.yaml drive:)

`check` exits 0 and prints the match when the image already exists (so: do NOT regenerate or
re-download), and exits 1 when nothing matches. generate_images.py calls it before every generation.

Sources the catalogue reads:
  - image files under IMAGE_DIRS (hashed with SHA-256; the hash is the identity of the bytes)
  - #plate(...) / #plate-pair / image(...) references in pilot/*.typ (chapter, caption)
  - photos/photo_index.csv (Rex's photographs and supplied illustrations: subject, people, status)
  - data/image_prompts.json (every generated image's prompt; written by generate_images.py)
  - data/image_sources.csv (images fetched from the web or archives: source URL, rights)
Drive ids from previous syncs are kept in data/image_catalog.csv and carried forward.
"""
import argparse, csv, hashlib, json, os, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402

ROOT = Path(".")          # set by enter_project() in __main__
CATALOG = Path("data/image_catalog.csv")
PROMPTS = Path("data/image_prompts.json")
SOURCES = Path("data/image_sources.csv")
PHOTO_INDEX = Path("photos/photo_index.csv")
# where a project keeps images; add more in book.yaml -> images.dirs (globs, project-relative)
IMAGE_DIRS = ["photos/print", "photos/source", "photos/reference", "photos/generated", "photos/generated/print",
              "images", "images/print",
              "work/*/images", "work/*/images/print", "work/*/*/plates", "work/*/*/artwork",
              "records/*/plates"]
CHAPTER_GLOBS = ["chapters/*.typ", "book/*.typ", "pilot/*.typ"]
EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".webp"}
FIELDS = ["key", "path", "kind", "sha256", "bytes", "width", "height", "chapters", "captions",
          "origin", "prompt_sha", "source_url", "drive_id", "drive_md5", "note"]
REF = re.compile(r'(?:#plate|#plate-pair|image)\(\s*"([^"]+\.(?:jpe?g|png|gif|tiff?|webp))"(?:[^)]*?caption:\s*"([^"]*)")?', re.I)


def sha(p, algo="sha256"):
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def norm_prompt(t):
    return re.sub(r"\s+", " ", t.strip().lower())


def prompt_sha(t):
    return hashlib.sha256(norm_prompt(t).encode()).hexdigest()[:16]


def dims(p):
    try:
        out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(p)], capture_output=True, text=True).stdout
        w = re.search(r"pixelWidth: (\d+)", out); h = re.search(r"pixelHeight: (\d+)", out)
        return (w.group(1) if w else ""), (h.group(1) if h else "")
    except Exception:
        return "", ""


def kind_of(rel):
    name = Path(rel).name
    if name.startswith("IMG-"): return "generated"
    if "/artwork/" in rel: return "artwork"
    if "/mugshots/" in rel: return "record"
    if "/plates/" in rel: return "plate"
    if rel.startswith("photos/"): return "photo"
    if "museum" in rel: return "museum"
    return "other"


def load_csv(p):
    return list(csv.DictReader(open(p))) if p.exists() else []


def references():
    refs = {}
    for f in sorted({p for g in CHAPTER_GLOBS for p in ROOT.glob(g)}):
        text = f.read_text(errors="ignore")
        for m in REF.finditer(text):
            path = m.group(1).lstrip("/")
            r = refs.setdefault(path, {"chapters": set(), "captions": set()})
            r["chapters"].add(f.stem)
            if m.group(2): r["captions"].add(m.group(2))
    return refs


def catalog(args=None):
    old = {r["path"]: r for r in load_csv(CATALOG)}
    prompts = json.loads(PROMPTS.read_text()) if PROMPTS.exists() else {}
    sources = {r["path"]: r for r in load_csv(SOURCES)}
    photo_idx = {}
    for r in load_csv(PHOTO_INDEX):
        if r.get("print_file"): photo_idx[r["print_file"].lstrip("/")] = r
    refs = references()
    files = set()
    for pat in IMAGE_DIRS:
        for d in ROOT.glob(pat):
            if d.is_dir():
                for p in d.rglob("*"):
                    if p.suffix.lower() in EXT and p.is_file():
                        files.add(p.relative_to(ROOT).as_posix())
    files |= {p for p in refs if (ROOT / p).exists()}
    rows = []
    for rel in sorted(files):
        p = ROOT / rel
        try:
            digest = sha(p)
        except PermissionError:
            continue
        o = old.get(rel, {})
        w, h = (o.get("width"), o.get("height")) if o.get("sha256") == digest else dims(p)
        key = p.stem
        r = refs.get(rel, {"chapters": set(), "captions": set()})
        origin, psha, url, note = "", "", "", ""
        if key in prompts:
            origin, psha = "generated: " + prompts[key].get("model", "gpt-image-1"), prompt_sha(prompts[key]["prompt"])
        elif rel in photo_idx:
            pi = photo_idx[rel]
            origin = "photo_index " + pi["id"]; note = (pi.get("subject") or "")[:120] + (" [" + pi["status"] + "]" if pi.get("status") else "")
        elif rel in sources:
            origin, url, note = "sourced", sources[rel].get("url", ""), sources[rel].get("rights", "")
        if p.stat().st_size < 20000 and rel.startswith("photos/print"):
            note = "STAND-IN (real plate lives in the main checkout's photos/print)"
        rows.append(dict(key=key, path=rel, kind=kind_of(rel), sha256=digest, bytes=p.stat().st_size, width=w, height=h,
                         chapters=";".join(sorted(r["chapters"])), captions=" | ".join(sorted(r["captions"])),
                         origin=origin, prompt_sha=psha, source_url=url,
                         drive_id=o.get("drive_id", "") if o.get("sha256") == digest else "",
                         drive_md5=o.get("drive_md5", "") if o.get("sha256") == digest else "", note=note))
    CATALOG.parent.mkdir(exist_ok=True)
    with open(CATALOG, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    CATALOG.with_suffix(".json").write_text(json.dumps(rows, indent=1))
    by = {}
    for r in rows: by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"{len(rows)} images catalogued -> {CATALOG}  {by}")
    print(f"  used in a chapter: {sum(1 for r in rows if r['chapters'])}; on Drive: {sum(1 for r in rows if r['drive_id'])}")
    return rows


def check(args):
    rows = load_csv(CATALOG) or catalog()
    prompts = json.loads(PROMPTS.read_text()) if PROMPTS.exists() else {}
    hits = []
    if args.id:
        hits += [r for r in rows if r["key"] == args.id or r["key"].startswith(args.id + ".")]
        if args.id in prompts and not hits:
            print(f"prompt recorded for {args.id} but no file found (generated earlier, file lost?)")
    if args.prompt:
        ps = prompt_sha(args.prompt)
        hits += [r for r in rows if r["prompt_sha"] == ps]
        hits += [{"key": k, "path": "(prompt only)", "origin": "data/image_prompts.json"} for k, v in prompts.items()
                 if prompt_sha(v["prompt"]) == ps and not any(h.get("key") == k for h in hits)]
    if args.url:
        hits += [r for r in rows if r["source_url"] and r["source_url"].rstrip("/") == args.url.rstrip("/")]
    if args.file:
        d = sha(Path(args.file).expanduser())
        hits += [r for r in rows if r["sha256"] == d]
    for h in hits:
        print(f"EXISTS {h.get('key')}  {h.get('path')}  {h.get('origin','')}  chapters={h.get('chapters','')}  drive={h.get('drive_id','')}")
    if not hits: print("no match: safe to create or fetch")
    sys.exit(0 if hits else 1)


def unused(args):
    for r in load_csv(CATALOG) or catalog():
        if not r["chapters"] and r["kind"] in ("generated", "plate", "photo"):
            print(r["path"], r["note"])


def missing(args):
    refs = references()
    for path, r in sorted(refs.items()):
        p = ROOT / path
        if not p.exists():
            print("MISSING FILE", path, sorted(r["chapters"]))
        elif p.stat().st_size < 20000:
            print("STAND-IN    ", path, sorted(r["chapters"]))
    for f in sorted({p for g in CHAPTER_GLOBS for p in ROOT.glob(g)}):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if "PLATE-TODO" in line:
                print(f"PLATE-TODO   {f.name}:{n}  {line.strip()[:110]}")


def drive_settings():
    """book.yaml -> drive: {parent_id: <Drive folder id>, token: <path to an OAuth user token json>}"""
    try:
        import yaml
        cfg = (yaml.safe_load(open("book.yaml")) or {}).get("drive") or {}
    except Exception:
        cfg = {}
    return cfg.get("parent_id"), Path(cfg.get("token", ".gdrive_token_rw.json")).expanduser()


def drive_sync(args):
    """Upload every catalogued image not yet on Drive (or changed since) into <parent>/Lineage/Images/<kind>/,
    plus PDFs under records/ and output/ into <parent>/Lineage/Records and /Book, and the catalogue itself.
    Needs google-api-python-client and google-auth-oauthlib, book.yaml drive.parent_id, and a user token
    with the drive.file scope (create it once with any OAuth installed-app flow)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    parent, token = drive_settings()
    if not parent or not token.exists():
        raise SystemExit("set book.yaml drive.parent_id and drive.token (an OAuth token json with drive.file scope)")
    c = Credentials.from_authorized_user_file(str(token), ["https://www.googleapis.com/auth/drive.file"])
    if c.expired and c.refresh_token:
        c.refresh(Request())
    svc = build("drive", "v3", credentials=c, cache_discovery=False)
    FOLDER = "application/vnd.google-apps.folder"

    def folder(name, par):
        q = f"name = '{name}' and '{par}' in parents and mimeType = '{FOLDER}' and trashed = false"
        got = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        return got[0]["id"] if got else svc.files().create(
            body={"name": name, "parents": [par], "mimeType": FOLDER}, fields="id").execute()["id"]

    root = folder("Lineage", parent); base = folder("Images", root)
    rows = catalog(); kinds = {}; up = 0
    for r in rows:
        p = ROOT / r["path"]
        if r["note"].startswith("STAND-IN"):
            continue
        m = sha(p, "md5")
        if r["drive_id"] and r["drive_md5"] == m:
            continue
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        media = MediaFileUpload(str(p), mimetype=mime)
        if r["drive_id"]:
            res = svc.files().update(fileId=r["drive_id"], media_body=media, fields="id,md5Checksum").execute()
        else:
            fid = kinds.get(r["kind"]) or kinds.setdefault(r["kind"], folder(r["kind"], base))
            res = svc.files().create(body={"name": r["path"].replace("/", "__"), "parents": [fid],
                                           "description": f"{r['captions']} {r['origin']} sha256={r['sha256']}"[:900]},
                                     media_body=media, fields="id,md5Checksum").execute()
        r["drive_id"], r["drive_md5"] = res["id"], res["md5Checksum"]; up += 1
        print("uploaded", r["path"])
    with open(CATALOG, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    ledger_p = Path("data/drive_documents.json")
    ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {}
    docs = [(p, "Records/" + p.parent.name) for p in sorted(Path("records").rglob("*.pdf"))]
    docs += [(p, "Book") for p in sorted(Path("output").glob("*.pdf"))]
    for p, sub in docs:
        rel = p.as_posix(); m = sha(p, "md5")
        if ledger.get(rel, {}).get("md5") == m:
            continue
        par = root
        for part in sub.split("/"):
            par = folder(part, par)
        media = MediaFileUpload(str(p), mimetype="application/pdf", resumable=True)
        if ledger.get(rel, {}).get("id"):
            res = svc.files().update(fileId=ledger[rel]["id"], media_body=media, fields="id,md5Checksum").execute()
        else:
            res = svc.files().create(body={"name": p.name, "parents": [par]}, media_body=media,
                                     fields="id,md5Checksum").execute()
        ledger[rel] = {"id": res["id"], "md5": res["md5Checksum"], "folder": sub}; up += 1
        print("uploaded", rel)
    ledger_p.write_text(json.dumps(ledger, indent=1))
    svc.files().create(body={"name": "image_catalog.csv", "parents": [base]},
                       media_body=MediaFileUpload(str(CATALOG), mimetype="text/csv")).execute()
    print(f"{up} uploaded; catalogue updated and copied to Drive")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Lineage image manager: catalogue, guard, Drive sync")
    add_project_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog"); sub.add_parser("unused"); sub.add_parser("missing"); sub.add_parser("drive-sync")
    c = sub.add_parser("check")
    for k in ("id", "prompt", "url", "file"): c.add_argument("--" + k)
    a = ap.parse_args()
    ROOT = enter_project(a.project)
    try:
        import yaml
        IMAGE_DIRS += ((yaml.safe_load(open("book.yaml")) or {}).get("images") or {}).get("dirs", [])
    except Exception:
        pass
    {"catalog": catalog, "check": check, "unused": unused, "missing": missing, "drive-sync": drive_sync}[a.cmd](a)
