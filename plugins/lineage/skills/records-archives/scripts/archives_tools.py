#!/usr/bin/env python3
"""Records & archives utilities. Run from the project root.

  archives_tools.py check      # sources present, statuses valid, private fields flagged
  archives_tools.py asks       # data/archive_asks.md: follow-up list grouped by holder
  archives_tools.py appendix   # chapters/91-where-the-records-are.typ (print-safe fields only)
"""
import csv, re, sys
from collections import defaultdict
from pathlib import Path

CSV = Path("data/archives.csv")
FIELDS = ["record_id", "item", "type", "description", "date_range", "holder", "holder_relation",
          "location_general", "location_detail_private", "condition", "status", "mentioned_in",
          "chapter", "official_copy_hint", "print_permission", "follow_up"]
STATUSES = {"confirmed", "mentioned", "unknown", "lost", "destroyed", "institutional"}
PRIVATE = re.compile(r"\d{2,}\s+\w+\s+(st|street|ave|avenue|rd|road|dr|drive|ln|lane|ct|way)\b|\(\d{3}\)|\d{3}[-.]\d{3}[-.]\d{4}|@", re.I)
TYPE_ORDER = ["photographs", "letters", "documents", "bible", "military", "legal", "recordings",
              "heirlooms", "institutional", "other"]


def load():
    return list(csv.DictReader(open(CSV, encoding="utf-8")))


def cmd_check():
    bad = 0
    for r in load():
        rid = r["record_id"]
        if r["status"] not in STATUSES:
            print(f"{rid}: status '{r['status']}' not in {sorted(STATUSES)}"); bad += 1
        if not re.search(r"\[S\d+ |https?://", r["mentioned_in"] or "") and r["status"] != "institutional":
            print(f"{rid}: mentioned_in needs a transcript citation [S# hh:mm:ss] or a record URL"); bad += 1
        for col in ("location_general", "description", "holder"):
            if PRIVATE.search(r[col] or ""):
                print(f"{rid}: {col} looks like a street address, phone or email — move it to location_detail_private"); bad += 1
    print(f"{bad} problems")


def cmd_asks():
    by = defaultdict(list)
    for r in load():
        if r["follow_up"] or r["status"] in ("mentioned", "unknown"):
            by[r["holder"] or "Holder unknown"].append(r)
    out = ["# Records to ask about", ""]
    for holder, rs in sorted(by.items()):
        out += [f"## {holder}" + (f" ({rs[0]['holder_relation']})" if rs[0]["holder_relation"] else ""), ""]
        for r in rs:
            ask = r["follow_up"] or "Confirm it still exists, where it's kept, and whether it can be scanned."
            src = f" _{r['mentioned_in']}_" if r["mentioned_in"] else ""
            out.append(f"- **{r['item']}** ({r['record_id']}, {r['status']}) — {ask}{src}")
        out.append("")
    Path("data/archive_asks.md").write_text("\n".join(out)); print("wrote data/archive_asks.md")


def esc(s):
    return (s or "").replace("[", "\\[").replace("]", "\\]").replace("#", "\\#").replace("*", "\\*").replace("_", "\\_").replace("@", "\\@")


def cmd_appendix():
    rows = [r for r in load() if r["print_permission"].strip().lower() in ("yes", "public")]
    groups = defaultdict(list)
    for r in rows:
        groups[r["type"] if r["type"] in TYPE_ORDER else "other"].append(r)
    L = ['#import "/book/template.typ": *', '#show: chapter.with("Where the Records Are", columns: 1)', "",
         "#set par(first-line-indent: 0pt)",
         "What survives of the family's papers, photographs and keepsakes, and who looks after them "
         "as of this printing. Items remembered but now lost are listed too, so no one spends years looking.", ""]
    for t in TYPE_ORDER:
        if t not in groups: continue
        L += [f"== {t.capitalize()}", ""]
        for r in sorted(groups[t], key=lambda r: r["item"].lower()):
            loc = "" if PRIVATE.search(r["location_general"] or "") else r["location_general"]
            where = r["holder"] or ""
            if loc:
                where = f"{where}, {loc}" if where else loc
            state = {"lost": "Lost.", "destroyed": "Destroyed.", "unknown": "Whereabouts unknown."}.get(r["status"], "")
            line = f"*{esc(r['item'])}*"
            if r["date_range"]: line += f" ({esc(r['date_range'])})"
            line += "."
            if r["description"]: line += f" {esc(r['description'].rstrip('.'))}."
            if where and r["status"] not in ("lost", "destroyed", "unknown"):
                line += f" {'Kept by' if r['holder'] else 'Kept in'} {esc(where)}."
            if state: line += f" {state}"
            if r["official_copy_hint"]: line += f" _{esc(r['official_copy_hint'])}_"
            L += [line, ""]
    Path("chapters").mkdir(exist_ok=True)
    Path("chapters/91-where-the-records-are.typ").write_text("\n".join(L))
    print(f"wrote appendix with {len(rows)} items ({len(load()) - len(rows)} held back: no print permission)")


if __name__ == "__main__":
    {"check": cmd_check, "asks": cmd_asks, "appendix": cmd_appendix}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
