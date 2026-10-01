#!/usr/bin/env python3
"""Cut the clean transcripts into story units, from content/boundaries.csv.

    python $LINEAGE/scripts/make_units.py            # write units + coverage report
    python $LINEAGE/scripts/make_units.py --check    # report only, write nothing
    python $LINEAGE/scripts/make_units.py --prune    # also move stale unit files aside

Run from the book project folder (or --project DIR).

content/boundaries.csv -- one row per cut point:

  session,start,id,title,part,section,tier,people,places,events,flags
  S1,00:00:05,U001,The farm at Tannacreek,life,childhood,,Ruth Calder;Agnes Calder,"Tannacreek, Ontario",E003,
  S1,00:06:40,X,false start while the recorder is adjusted,,,,,,,
  S1,00:07:12,U002,Leaving for the city,life,young-adult,,,"Toronto, Ontario",E010;E011,
  S2,00:00:03,U002,Leaving for the city,life,young-adult,,,,,

  start   timestamp (HH:MM:SS) of the first paragraph of the unit, as printed
          in transcript/clean/<S>.md. Everything from one cut to the next cut
          in the same session belongs to that unit, so coverage is exact by
          construction: no paragraph can be silently dropped or double-counted.
  id      U### for a unit; the same id may appear in several sessions (a story
          told twice is one unit with two spans). X marks an excluded span:
          the title column then holds the reason, and the span goes to
          content/excluded.md instead of a unit.
  part    life | family (or your own). family units get `section:` and `tier:`
          (told / witnessed) in frontmatter; others get `era:` from `section`.
  people, places, events, flags
          semicolon-separated lists. Places usually contain commas, so quote
          the cell. events are timeline IDs (E###). flags are free text
          ("REVIEW: ..." for anything sensitive about living people).
  Blank lines and rows whose session cell starts with # are ignored.

Writes content/units/U###-slug.md (frontmatter + ## Source / ## Shaped /
## Notes) and content/excluded.md. Re-running is safe: for a unit file that
already exists, the editorial fields (chapter, order, lead_in, break_before,
status) and the ## Shaped and ## Notes sections are carried over; only the
boundary-driven metadata and ## Source are regenerated. A unit whose Source
changed under existing Shaped text is reported so it can be re-checked.

Prints a coverage report and exits 1 if any paragraph is uncovered.
"""
import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

CLEAN = Path("transcript/clean")
UNITS = Path("content/units")
BOUNDS = Path("content/boundaries.csv")
EXCLUDED = Path("content/excluded.md")
PARA = re.compile(r"^\*\*(?P<spk>[^*]+)\*\* \[(?P<s>S\d+) (?P<t>\d{1,2}:\d{2}:\d{2})\] (?P<rest>.*)$")
COLS = ["session", "start", "id", "title", "part", "section", "tier",
        "people", "places", "events", "flags"]
EDITORIAL = ["chapter", "order", "lead_in", "break_before", "status"]


def split_list(v):
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def ys(v):
    """A YAML scalar: plain when safe, JSON-quoted otherwise."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.fullmatch(r"[A-Za-z0-9][^:#\[\]{}\",'&*!|>%@`]*", s) and s == s.strip() \
            and s.lower() not in ("yes", "no", "true", "false", "null", "on", "off"):
        return s
    return json.dumps(s, ensure_ascii=False)


def ylist(xs):
    return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in xs) + "]"


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "untitled"


def read_bounds():
    if not BOUNDS.exists():
        sys.exit(f"{BOUNDS} not found. Header:\n  {','.join(COLS)}")
    out, bad = [], 0
    with open(BOUNDS, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        missing = [c for c in ("session", "start", "id", "title") if c not in (rd.fieldnames or [])]
        if missing:
            sys.exit(f"{BOUNDS}: missing column(s) {missing}. Header:\n  {','.join(COLS)}")
        for n, r in enumerate(rd, start=2):
            r = {k: (v or "").strip() for k, v in r.items() if k}
            if not r.get("session") or r["session"].startswith("#"):
                continue
            try:
                r["t"] = P.secs(r["start"])
            except Exception:
                print(f"{BOUNDS}:{n}: bad start {r.get('start')!r} (want HH:MM:SS)")
                bad += 1
                continue
            r["id"] = r["id"].upper()
            if r["id"] != "X" and not re.fullmatch(r"U\d+", r["id"]):
                print(f"{BOUNDS}:{n}: id {r['id']!r} should be U### or X")
                bad += 1
                continue
            r["line"] = n
            out.append(r)
    if bad:
        sys.exit(f"{bad} bad row(s) in {BOUNDS}")
    return out


def read_paras():
    paras = {}
    for f in sorted(CLEAN.glob("S*.md"), key=lambda p: P.session_key(p.stem)):
        rows = []
        for line in f.read_text(encoding="utf-8").splitlines():
            m = PARA.match(line)
            if m:
                rows.append((P.secs(m["t"]), m["spk"], line))
        paras[f.stem] = rows
    return paras


def read_existing():
    """id -> (path, frontmatter dict, shaped text, notes text, source text)."""
    import yaml
    out = {}
    for p in sorted(UNITS.glob("U*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
        src = body.split("## Source", 1)[-1].split("## Shaped", 1)[0].strip()
        shaped = body.split("## Shaped", 1)[1].split("## Notes", 1)[0].strip() \
            if "## Shaped" in body else ""
        notes = body.split("## Notes", 1)[1].strip() if "## Notes" in body else ""
        uid = str(fm.get("id") or p.name.split("-")[0])
        out[uid] = (p, fm, shaped, notes, src)
    return out


def main():
    ap = argparse.ArgumentParser(description="Cut clean transcripts into story units.")
    P.add_project_arg(ap)
    ap.add_argument("--check", action="store_true", help="coverage report only; write nothing")
    ap.add_argument("--prune", action="store_true",
                    help="move unit files whose id is no longer in boundaries.csv "
                         "to content/units/_stale/")
    a = ap.parse_args()
    P.enter_project(a.project)

    bounds = read_bounds()
    paras = read_paras()
    if not paras:
        sys.exit(f"no transcripts in {CLEAN}/ -- run render_transcripts.py first")

    units, excluded, problems = {}, [], []
    uncovered = {}
    by_session = {}
    for b in bounds:
        by_session.setdefault(b["session"], []).append(b)

    for sid in by_session:
        if sid not in paras:
            problems.append(f"boundaries.csv names {sid}, but {CLEAN}/{sid}.md does not exist")
    for sid, rows in paras.items():
        marks = sorted(by_session.get(sid, []), key=lambda b: b["t"])
        if not rows:
            continue
        stamps = {t for t, _, _ in rows}
        for b in marks:
            if b["t"] not in stamps:
                problems.append(f"boundaries.csv:{b['line']}: {sid} {b['start']} is not the "
                                "timestamp of any paragraph (cut still applied by time)")
        first = marks[0]["t"] if marks else None
        before = [ln for t, _, ln in rows if first is None or t < first]
        if before:
            uncovered[sid] = before
        last_t = rows[-1][0] + 60
        for i, b in enumerate(marks):
            lo = b["t"]
            hi = marks[i + 1]["t"] if i + 1 < len(marks) else last_t
            if hi <= lo:
                problems.append(f"boundaries.csv:{b['line']}: {sid} {b['start']} duplicates "
                                "the next cut point")
                continue
            body = [ln for t, _, ln in rows if lo <= t < hi]
            if not body:
                continue
            span = f"{sid} {P.hms(lo)}-{P.hms(min(hi, last_t) - 1)}"
            if b["id"] == "X":
                excluded.append((span, b["title"] or "no reason given", body))
                continue
            u = units.get(b["id"])
            if u is None:
                u = units[b["id"]] = dict(
                    id=b["id"], title=b["title"], part=b.get("part") or "life",
                    section=b.get("section", ""), tier=b.get("tier", ""),
                    people=[], places=[], events=[], flags=[], spans=[], src=[], n=0)
            elif b["title"] and b["title"] != u["title"]:
                problems.append(f"boundaries.csv:{b['line']}: {b['id']} titled "
                                f"{b['title']!r} here but {u['title']!r} earlier (first wins)")
            u["spans"].append(span)
            u["src"].append("\n\n".join(body))
            u["n"] += len(body)
            for key, col in (("people", "people"), ("places", "places"),
                             ("events", "events"), ("flags", "flags")):
                for v in split_list(b.get(col)):
                    if v not in u[key]:
                        u[key].append(v)

    # ---- report ------------------------------------------------------------
    total = sum(len(r) for r in paras.values())
    n_unit = sum(u["n"] for u in units.values())
    n_excl = sum(len(b) for _, _, b in excluded)
    n_unc = sum(len(v) for v in uncovered.values())
    print(f"paragraphs: {total} in {len(paras)} session(s)")
    print(f"  in units:   {n_unit}  ({len(units)} units)")
    print(f"  excluded:   {n_excl}  ({len(excluded)} spans)")
    print(f"  UNCOVERED:  {n_unc}")
    for sid, lines in uncovered.items():
        why = "no boundaries for this session" if sid not in by_session else "before the first cut"
        print(f"    {sid}: {len(lines)} paragraph(s), {why}; first: {lines[0][:90]}")
    for p in problems:
        print(f"  ! {p}")
    if n_unit + n_excl + n_unc != total:
        print(f"  ! internal count mismatch ({n_unit}+{n_excl}+{n_unc} != {total})")

    if a.check:
        sys.exit(1 if n_unc else 0)

    # ---- write ---------------------------------------------------------------
    existing = read_existing()
    UNITS.mkdir(parents=True, exist_ok=True)
    changed_under_shaped = []
    for uid in sorted(units, key=lambda x: int(x[1:])):
        u = units[uid]
        old = existing.get(uid)
        ed = {"chapter": None, "order": None, "lead_in": None,
              "break_before": True, "status": "separated"}
        extra = {}
        shaped, notes = "", ""
        source = "\n\n".join(u["src"])
        if old:
            path, fm, shaped, notes, old_src = old
            for k in EDITORIAL:
                if k in fm and fm[k] not in (None, ""):
                    ed[k] = fm[k]
            # keep any field added by hand (lead_in_approved, date_display, ...)
            generated = {"id", "title", "part", "section", "tier", "era", "spans", "timeline_events",
                         "people", "places", "flags", *EDITORIAL}
            extra = {k: v for k, v in fm.items() if k not in generated}
            # flags: keep any written into the unit by hand, plus those from boundaries.csv
            u = dict(u, flags=list(dict.fromkeys(list(u["flags"]) + list(fm.get("flags") or []))))
            if shaped and old_src.strip() != source.strip():
                changed_under_shaped.append(uid)
        fm = ["---", f"id: {uid}", f"title: {ys(u['title'])}", f"part: {ys(u['part'])}"]
        if u["part"] == "family":
            fm += [f"section: {ys(u['section'])}", f"tier: {ys(u['tier'])}"]
        else:
            fm += [f"era: {ys(u['section'])}"]
        fm += [f"spans: {ylist(u['spans'])}",
               f"timeline_events: {ylist(u['events'])}",
               f"people: {ylist(u['people'])}",
               f"places: {ylist(u['places'])}",
               f"chapter: {ys(ed['chapter'])}".rstrip(),
               f"order: {ys(ed['order'])}".rstrip(),
               f"lead_in: {ys(ed['lead_in'])}".rstrip(),
               f"break_before: {ys(bool(ed['break_before']))}",
               f"flags: {ylist(u['flags'])}",
               f"status: {ys(ed['status'])}"]
        if extra:
            import yaml
            fm += yaml.safe_dump(extra, sort_keys=False, allow_unicode=True,
                                 default_flow_style=None).rstrip().splitlines()
        fm += ["---"]
        text = ("\n".join(fm) + "\n\n## Source\n" + source + "\n\n## Shaped\n"
                + (f"\n{shaped}\n" if shaped else "") + "\n## Notes\n"
                + (f"\n{notes}\n" if notes else ""))
        dest = UNITS / f"{uid}-{slugify(u['title'])}.md"
        if old and old[0] != dest:
            old[0].unlink()  # title changed: rename, content carried over above
        dest.write_text(text, encoding="utf-8")

    # apparatus units (descent box, THE RECORDS, photographs page) have no transcript span
    stale = [uid for uid in existing if uid not in units
             and existing[uid][1].get("kind") != "apparatus"]
    for uid in stale:
        path = existing[uid][0]
        if a.prune:
            (UNITS / "_stale").mkdir(exist_ok=True)
            shutil.move(str(path), str(UNITS / "_stale" / path.name))
            print(f"  moved stale {path.name} -> content/units/_stale/")
        else:
            print(f"  ! {path.name}: id not in boundaries.csv (left in place; --prune moves it)")
    for uid in changed_under_shaped:
        print(f"  ! {uid}: Source changed under existing Shaped text -- re-check it")

    out = ["# Excluded spans", "",
           "Transcript deliberately not used as raw material for the book, with the reason.", ""]
    for span, why, body in excluded:
        out.append(f"- **{span}** -- {why}")
        for ln in body:
            out.append(f"  > {ln[:160]}")
        out.append("")
    EXCLUDED.parent.mkdir(parents=True, exist_ok=True)
    EXCLUDED.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(units)} unit file(s) written to {UNITS}/, {len(excluded)} span(s) to {EXCLUDED}")
    sys.exit(1 if n_unc else 0)


if __name__ == "__main__":
    main()
