#!/usr/bin/env python3
"""Sort, check, and render the book's timeline. Run from the project root.

  timeline_tools.py sort      # sort facts/timeline.csv chronologically in place
  timeline_tools.py check     # report missing sources, bad dates, conflicts, ID gaps
  timeline_tools.py appendix  # write chapters/90-timeline.typ (confirmed + medium rows)
  timeline_tools.py md        # write facts/timeline.md grouped by decade
"""
import csv, re, sys
from collections import defaultdict
from pathlib import Path

CSV = Path("facts/timeline.csv")
FIELDS = ["event_id", "date_start", "date_end", "date_display", "precision", "date_basis",
          "event", "people", "place", "generation", "source", "quote", "confidence",
          "conflicts", "chapter"]
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
SRC = re.compile(r"\[S\d+ (\d{2}:\d{2}:\d{2}|¶\d+)\]|\bR\d{3,}\b|https?://")


def load():
    return list(csv.DictReader(open(CSV, encoding="utf-8")))


def save(rows):
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def key(r):
    d = r["date_start"] or "9999"
    parts = (d.split("-") + ["00", "00"])[:3]
    return (parts[0], parts[1], parts[2], r["date_end"] or "", r["event_id"])


def cmd_sort():
    rows = sorted(load(), key=key); save(rows); print(f"sorted {len(rows)} events")


def cmd_check():
    rows, bad = load(), 0
    for r in rows:
        eid = r["event_id"]
        for col in ("date_start", "date_end"):
            if r[col] and not DATE.match(r[col]):
                print(f"{eid}: {col} '{r[col]}' is not YYYY[-MM[-DD]]"); bad += 1
        if not r["date_start"] and r["precision"] != "unknown":
            print(f"{eid}: no date_start but precision is '{r['precision']}'"); bad += 1
        if not SRC.search(r["source"] or ""):
            print(f"{eid}: missing source ([S# hh:mm:ss], a record ID like R012, or a URL)"); bad += 1
        if r["precision"] in ("derived", "approx") and not r["date_basis"]:
            print(f"{eid}: derived date with no date_basis (show the arithmetic)"); bad += 1
        if r["conflicts"]:
            print(f"{eid}: CONFLICT -> {r['conflicts']}")
    print(f"{len(rows)} events, {bad} problems")


def decade(r):
    return (r["date_start"][:3] + "0s") if r["date_start"] else "Undated"


def cmd_md():
    groups = defaultdict(list)
    for r in sorted(load(), key=key):
        groups[decade(r)].append(r)
    out = ["# Timeline", ""]
    for dec, rs in groups.items():
        out += [f"## {dec}", ""]
        for r in rs:
            flag = "" if r["confidence"] == "high" else f" _({r['confidence']})_"
            out.append(f"- **{r['date_display'] or 'undated'}** — {r['event']}{flag} {r['source']}")
        out.append("")
    Path("facts/timeline.md").write_text("\n".join(out)); print("wrote facts/timeline.md")


def esc(s):
    return s.replace("[", "\\[").replace("]", "\\]").replace("#", "\\#").replace("*", "\\*").replace("_", "\\_")


def cmd_appendix():
    rows = [r for r in sorted(load(), key=key) if r["confidence"] in ("high", "medium") and r["date_start"]]
    lines = ['#import "/book/template.typ": *', '#show: chapter.with("A Timeline", columns: 1)', "",
             "#set par(first-line-indent: 0pt, justify: false)",
             "#table(columns: (1.1in, 1fr), stroke: none, row-gutter: 0.35em,"]
    for r in rows:
        lines.append(f"  [{esc(r['date_display'])}], [{esc(r['event'])}],")
    lines.append(")")
    Path("chapters").mkdir(exist_ok=True)
    Path("chapters/90-timeline.typ").write_text("\n".join(lines) + "\n")
    print(f"wrote chapters/90-timeline.typ with {len(rows)} events")


if __name__ == "__main__":
    {"sort": cmd_sort, "check": cmd_check, "md": cmd_md, "appendix": cmd_appendix}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
