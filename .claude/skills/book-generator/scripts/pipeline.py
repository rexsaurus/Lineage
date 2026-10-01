#!/usr/bin/env python3
"""Show where the book's pipeline stands and what to run next. Run from project root.

  pipeline.py status
"""
import csv, re, sys
from pathlib import Path


def locked():
    try:
        import yaml
        return bool((yaml.safe_load(open("book.yaml")) or {}).get("transcription_locked"))
    except Exception:
        return False


def n(glob):
    return len(list(Path().glob(glob)))


def rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8"))) if Path(p).exists() else []


def unit_status():
    counts = {}
    for p in Path("content/units").glob("U*.md"):
        m = re.search(r"^status:\s*(\w+)", p.read_text(encoding="utf-8"), re.M)
        s = m.group(1) if m else "?"
        counts[s] = counts.get(s, 0) + 1
    return counts


def newest(globs):
    ts = [p.stat().st_mtime for g in globs for p in Path().glob(g)]
    return max(ts) if ts else 0


def main():
    chapters = rows("data/chapters.csv")
    us = unit_status(); total_units = sum(us.values())
    shaped = us.get("shaped", 0) + us.get("approved", 0)
    ch_files = [c for c in chapters if Path(c["file"]).exists()]
    map_ok = bool(chapters) and all(c.get("status") not in ("", "proposed") for c in chapters)
    draft = Path("output/book-draft.pdf")
    draft_fresh = draft.exists() and draft.stat().st_mtime >= newest(["chapters/*.typ", "book/**/*.typ", "photos/print/*"])
    bridges = sum(p.read_text().count("#bridge[") for p in Path("chapters").glob("*.typ")) if Path("chapters").exists() else 0

    stages = [
        ("1 transcribe  [GATE: confirm speakers]", "interview-transcriber", n("transcript/clean/S*.md") > 0 and Path("transcript/master.md").exists(),
         f"{n('transcript/clean/S*.md')} clean sessions" + ("; LOCKED (book.yaml): fix spellings in transcript/corrections.json, never re-run ASR" if locked() else "")),
        ("2 timeline", "timeline-organizer", Path("facts/timeline.csv").exists(), f"{len(rows('facts/timeline.csv'))} events"),
        ("3 separate", "content-separator", total_units > 0, f"{total_units} units {us}"),
        ("4 chapter map  [GATE: author approves]", "chapter-index-builder", map_ok,
         f"{len(chapters)} chapters" + ("" if map_ok else " — awaiting approval")),
        ("5 shape units", "content-separator + family-history-chapters", total_units > 0 and shaped == total_units,
         f"{shaped}/{total_units} shaped"),
        ("6 assemble chapters", "chapter-generator", bool(chapters) and len(ch_files) == len(chapters),
         f"{len(ch_files)}/{len(chapters)} chapter files"),
        ("7 photos (optional)", "photo-processor", True if not n("photos/source/*") else Path("photos/photo_index.csv").exists(),
         f"{n('photos/source/*')} photos"),
        ("8 records appendix", "records-archives", Path("chapters/91-where-the-records-are.typ").exists(),
         f"{len(rows('data/archives.csv'))} records"),
        ("9 glossary", "book-generator", Path("chapters/92-glossary.typ").exists(), f"{len(rows('data/reader_glossary.csv'))} terms"),
        ("10 timeline appendix", "timeline-organizer", Path("chapters/90-timeline.typ").exists(), ""),
        ("10b introduction", "foreword-generator", Path("book/front/introduction.typ").exists(), ""),
        ("11 draft build + index", "book-generator / book-layout", draft_fresh and Path("data/back_index.csv").exists(),
         "up to date" if draft_fresh else "stale or missing"),
        ("12 final  [GATE: 0 bridges, author sign-off]", "book-layout", Path("output/book-final.pdf").exists(),
         f"{bridges} bridges pending"),
    ]
    nxt = None
    for name, skill, done, detail in stages:
        mark = "✓" if done else "·"
        print(f" {mark} {name:42} {skill:44} {detail}")
        if not done and nxt is None: nxt = (name, skill)
    print(f"\nNEXT: {nxt[0]} → {nxt[1]}" if nxt else "\nAll stages complete.")


if __name__ == "__main__":
    main() if (sys.argv[1:] or ["status"])[0] == "status" else sys.exit(__doc__)
