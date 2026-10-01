#!/usr/bin/env python3
"""Collect the verifiable facts the introduction draws on -> data/foreword_facts.md
Run from the project root after chapters are assembled.
"""
import csv, re, sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "chapter-index-builder" / "scripts"))
from index_tools import strip_calls  # noqa: E402


def rows(p):
    return list(csv.DictReader(open(p, encoding="utf-8"))) if Path(p).exists() else []


def secs(d):
    parts = [int(x) for x in re.findall(r"\d+", d or "")]
    while len(parts) < 3: parts.insert(0, 0)
    h, m, s = parts[-3:]; return h * 3600 + m * 60 + s


def main():
    c = yaml.safe_load(open("book.yaml")) or {}
    sessions = rows("transcript/sessions.csv")
    chapters = sorted(rows("data/chapters.csv"), key=lambda r: float(r["chapter"]))
    timeline = rows("facts/timeline.csv")
    photos = rows("photos/photo_index.csv")
    records = rows("data/archives.csv")
    total = sum(secs(s.get("duration")) for s in sessions)
    years = sorted(r["date_start"][:4] for r in timeline if r.get("date_start"))
    places = sorted({p.strip() for r in timeline for p in (r.get("place") or "").split(";") if p.strip()})
    words = sum(int(r.get("word_count") or 0) for r in chapters)
    quotes = 0
    for p in Path("chapters").glob("*.typ") if Path("chapters").exists() else []:
        for line in strip_calls(p.read_text()).splitlines():
            if line.lstrip().startswith(("#import", "//")):
                continue
            line = re.sub(r"#idx(-see)?\([^)]*\)", "", line)
            quotes += line.count('"') // 2 + line.count("#verbatim[")
    L = ["# Facts for the introduction", "",
         f"- Subject: {c.get('narrator', {}).get('name')} (born {c.get('narrator', {}).get('birth_year') or '?'}, {c.get('narrator', {}).get('birthplace') or '?'})",
         f"- Author: {c.get('interviewer', {}).get('name')}",
         f"- Recordings: {len(sessions)} sessions, {total // 3600} h {total % 3600 // 60} m in total",
         ]
    for s in sessions:
        L.append(f"  - {s.get('session')}: \"{Path(s.get('file', '')).stem}\", {s.get('recorded', '?')}, {s.get('duration', '?')}, place: {s.get('place') or '?'}")
    L += [f"- Years covered by the timeline: {years[0]}–{years[-1]}" if years else "- Years covered: (timeline empty)",
          f"- Places: {', '.join(places) or '(none recorded)'}",
          f"- Family figures: {', '.join(c.get('family_figures') or [])}",
          f"- Book: {len(chapters)} chapters, about {words:,} words of narrative, roughly {quotes} quotations in the subject's own words",
          f"- Photos placed: {sum(1 for p in photos if p.get('chapter'))} of {len(photos)}"
          + (f" ({sum(1 for p in photos if (p.get('kind') or '').startswith('illustration'))} illustrations)" if any(p.get('kind') for p in photos) else ""),
          f"- Records and keepsakes indexed: {len(records)}", "", "## Chapters", ""]
    part = None
    for r in chapters:
        if r.get("part") and r["part"] != part:
            part = r["part"]; L += ["", f"### {part}"]
        L.append(f"- {r['chapter']}. {r['title']} ({r.get('date_range') or '?'}): {r.get('summary') or '(no summary yet)'}")
    Path("data").mkdir(exist_ok=True)
    Path("data/foreword_facts.md").write_text("\n".join(L) + "\n")
    print("wrote data/foreword_facts.md")


if __name__ == "__main__":
    main()
