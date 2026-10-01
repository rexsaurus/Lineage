#!/usr/bin/env python3
"""Copy the shareable, text part of the local records cache into the project.

    python $BOOKASSEMBLER/scripts/export_sources.py
    python $BOOKASSEMBLER/scripts/export_sources.py --dry-run
    python $BOOKASSEMBLER/scripts/export_sources.py --restricted '^museum/' \\
        --extract '^ships/data/=VOY0042|\\bSea Lark\\b'

Run from the book project folder (or --project DIR).

facts/records/_raw/ (keep it out of git) holds everything downloaded while
researching: PDFs, page images, newspaper scans, whole database dumps, web
pages. This script copies what may be shared and is useful as text into
facts/records/sources/ (which can be committed), and writes
facts/records/sources/MANIFEST.csv listing EVERY raw file with its size and
sha256, whether it was exported, and why not. The manifest plus the URLs you
keep beside each download let anyone re-fetch what is not exported.

Rules
  * Text only (txt, tsv, csv, json, md, html, geojson, log by default).
    Binaries stay local and are listed in the manifest.
  * Restricted paths are never exported: anything whose reproduction is
    restricted (archive or museum pages marked "may not be reproduced",
    copyrighted articles, grave-listing sites, ...). Link to them instead.
  * Files over big_file_mb are not copied whole. If an `extracts` rule matches
    the path, only the matching lines (plus the header line) are written to
    <path>.<name>.txt; otherwise the file is listed as too large.
  * facts/records/sources/ is regenerated each run (README.md is kept).

Configuration: facts/records/export.yaml (all keys optional), and/or flags:

    raw_dir: facts/records/_raw
    out_dir: facts/records/sources
    text_extensions: [.txt, .tsv, .csv, .json, .md, .html, .geojson, .log]
    skip: ['(^|/)scratch/']             # regexes on the path: not scanned at all
    restricted:                         # regexes on the path relative to raw_dir
      - pattern: '^museum/'
        note: catalogue pages may not be reproduced without permission
      - '(^|/)findagrave'               # a bare string works too
    big_file_mb: 5
    extracts:
      - path: '^ships/data/'            # which big files
        lines: 'VOY0042|\\bSea Lark\\b'   # which lines to keep
        name: sea-lark                  # suffix for the extract file
"""
import argparse
import csv
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

CONFIG = Path("facts/records/export.yaml")
DEFAULT_TEXT = [".txt", ".tsv", ".csv", ".json", ".md", ".html", ".geojson", ".log"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_config(a):
    cfg = {}
    path = Path(a.config) if a.config else CONFIG
    if path.exists():
        import yaml
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    elif a.config:
        sys.exit(f"config not found: {path}")
    restricted = []
    for r in cfg.get("restricted") or []:
        if isinstance(r, str):
            restricted.append((re.compile(r, re.I), "reproduction restricted"))
        else:
            restricted.append((re.compile(r["pattern"], re.I),
                               r.get("note") or "reproduction restricted"))
    for r in a.restricted:
        restricted.append((re.compile(r, re.I), "reproduction restricted"))
    extracts = []
    for e in cfg.get("extracts") or []:
        extracts.append((re.compile(e["path"]), re.compile(e["lines"]),
                         e.get("name") or "extract"))
    for e in a.extract:
        if "=" not in e:
            sys.exit(f"--extract wants PATH_REGEX=LINE_REGEX, got {e!r}")
        pth, lines = e.split("=", 1)
        extracts.append((re.compile(pth), re.compile(lines), "extract"))
    return dict(
        raw=Path(a.raw or cfg.get("raw_dir") or "facts/records/_raw"),
        out=Path(a.out or cfg.get("out_dir") or "facts/records/sources"),
        text={e.lower() if e.startswith(".") else "." + e.lower()
              for e in (cfg.get("text_extensions") or DEFAULT_TEXT)},
        skip=[re.compile(x) for x in (cfg.get("skip") or [])],
        restricted=restricted,
        big=float(a.big_mb if a.big_mb is not None else cfg.get("big_file_mb", 5)) * 1024 * 1024,
        extracts=extracts,
    )


def main():
    ap = argparse.ArgumentParser(description="Export shareable text from facts/records/_raw/.")
    P.add_project_arg(ap)
    ap.add_argument("--config", help=f"YAML config (default {CONFIG} if present)")
    ap.add_argument("--raw", help="raw cache folder (default facts/records/_raw)")
    ap.add_argument("--out", help="export folder (default facts/records/sources)")
    ap.add_argument("--restricted", action="append", default=[], metavar="REGEX",
                    help="path regex never to export (repeatable)")
    ap.add_argument("--extract", action="append", default=[], metavar="PATH_RE=LINE_RE",
                    help="for big files matching PATH_RE, keep lines matching LINE_RE")
    ap.add_argument("--big-mb", type=float, help="size limit for whole-file copies (5)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    a = ap.parse_args()
    P.enter_project(a.project)
    c = load_config(a)
    raw, out = c["raw"], c["out"]
    if not raw.is_dir():
        sys.exit(f"{raw}/ does not exist -- nothing to export")
    if out.resolve() == raw.resolve() or raw.resolve() in out.resolve().parents:
        sys.exit("out_dir must not be inside raw_dir")

    if out.exists() and not a.dry_run:
        for p in out.rglob("*"):
            if p.is_file() and p.name != "README.md":
                p.unlink()
    rows = []
    for p in sorted(raw.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(raw).as_posix()
        if any(s.search(rel) for s in c["skip"]):
            continue
        size = p.stat().st_size
        hit = next((note for rx, note in c["restricted"] if rx.search(rel)), None)
        if hit:
            exported, why = "no", f"{hit}; link to it instead"
        elif p.suffix.lower() not in c["text"]:
            exported, why = "no", "binary; re-download from the source URL"
        elif size > c["big"]:
            rule = next(((lr, name) for pr, lr, name in c["extracts"] if pr.search(rel)), None)
            if rule is None:
                exported, why = "no", f"over {c['big'] / 1048576:g} MB; no extract rule"
            else:
                lines_rx, name = rule
                dst = out / f"{rel}.{name}.txt"
                n = 0
                if not a.dry_run:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    with open(p, errors="ignore") as src, open(dst, "w") as w:
                        w.write(src.readline())
                        for line in src:
                            if lines_rx.search(line):
                                w.write(line)
                                n += 1
                exported, why = "extract", f"large dump; {n} matching rows in {dst.name}"
        else:
            if not a.dry_run:
                dst = out / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
            exported, why = "yes", ""
        rows.append([rel, size, sha256(p), exported, why])

    if a.dry_run:
        for r in rows:
            print(f"{r[3]:>7}  {r[0]}  {r[4]}")
    else:
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["raw_path", "bytes", "sha256", "exported", "note"])
            w.writerows(rows)
    done = sum(r[3] != "no" for r in rows)
    print(f"{len(rows)} raw file(s); {done} exported or extracted"
          + ("" if a.dry_run else f"; manifest {out / 'MANIFEST.csv'}"))


if __name__ == "__main__":
    main()
