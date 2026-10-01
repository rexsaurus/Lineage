#!/usr/bin/env python3
"""Story-unit utilities. Run from the project root.

  units.py coverage   # every subject paragraph in transcript/clean is in a unit or content/excluded.md
  units.py table      # content/units.csv summary of all unit frontmatter
  units.py check      # frontmatter fields, spans, citations inside Shaped text
"""
import csv, re, sys
from pathlib import Path
import yaml

UNITS = Path("content/units")
PARA = re.compile(r"^\*\*(?P<spk>[^*]+)\*\* \[(?P<s>S\d+) (?P<t>\d{2}:\d{2}:\d{2})\]")
SPAN = re.compile(r"(S\d+) (\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})")
REQUIRED = ["id", "title", "part", "spans", "status"]


def secs(t):
    h, m, s = map(int, t.split(":")); return h * 3600 + m * 60 + s


def read_unit(p):
    text = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def all_units():
    for p in sorted(UNITS.glob("U*.md")):
        fm, body = read_unit(p)
        yield p, fm, body


def spans_of(text):
    return [(s, secs(a), secs(b)) for s, a, b in SPAN.findall(text)]


def narrator_label():
    """The subject's speaker label in the transcripts (book.yaml -> narrator.label)."""
    try:
        label = yaml.safe_load(open("book.yaml"))["narrator"]["label"]
    except Exception:
        label = None
    if not label:
        sys.exit("book.yaml -> narrator.label is not set (the subject's speaker label, e.g. Grandma)")
    return label


def is_apparatus(fm):
    """Units that carry chapter apparatus (THE RECORDS, photo addendum, descent box)
    rather than transcript content: no spans needed, ignored by coverage."""
    return (fm or {}).get("kind") == "apparatus"


def cmd_coverage():
    label = narrator_label()
    covered = []
    for p, fm, _ in all_units():
        if fm and not is_apparatus(fm): covered += [(s, a, b, fm["id"]) for s, a, b in spans_of(" ".join(map(str, fm.get("spans", []))))]
    excl = Path("content/excluded.md")
    if excl.exists():
        covered += [(s, a, b, "excluded") for s, a, b in spans_of(excl.read_text())]
    missing, multi = [], []
    for f in sorted(Path("transcript/clean").glob("S*.md")):
        for line in f.read_text().splitlines():
            m = PARA.match(line)
            if not m or m["spk"] != label:
                continue
            t = secs(m["t"])
            hits = {u for s, a, b, u in covered if s == m["s"] and a <= t <= b}
            if not hits:
                missing.append(f"[{m['s']} {m['t']}] {line[len(m.group(0)):][:70].strip()}")
            elif len(hits - {"excluded"}) > 1:
                multi.append(f"[{m['s']} {m['t']}] in {sorted(hits)}")
    print(f"UNCOVERED {label} paragraphs: {len(missing)}")
    for x in missing: print("  ", x)
    print(f"In more than one unit (retellings are fine if intended): {len(multi)}")
    for x in multi: print("  ", x)


def cmd_table():
    cols = ["id", "title", "part", "section", "era", "chapter", "order", "date_display",
            "people", "places", "timeline_events", "spans", "words", "flags", "status"]
    rows = []
    for p, fm, body in all_units():
        if not fm: continue
        shaped = body.split("## Shaped", 1)[-1] if "## Shaped" in body else ""
        prose = "\n".join(l for l in shaped.splitlines() if not l.strip().startswith(("//", "#")))
        r = {c: fm.get(c, "") for c in cols}
        for c in ("people", "places", "timeline_events", "spans", "flags"):
            if isinstance(r[c], list): r[c] = "; ".join(map(str, r[c]))
        r["words"] = len(re.findall(r"[A-Za-z0-9’']+", prose))
        rows.append(r)
    with open("content/units.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} units, {sum(r['words'] for r in rows)} shaped words -> content/units.csv")


def cmd_check():
    bad, ids = 0, set()
    for p, fm, body in all_units():
        if fm is None:
            print(f"{p.name}: no frontmatter"); bad += 1; continue
        for k in REQUIRED:
            if k == "spans" and is_apparatus(fm): continue
            if not fm.get(k): print(f"{p.name}: missing {k}"); bad += 1
        if fm.get("id") in ids: print(f"{p.name}: duplicate id {fm['id']}"); bad += 1
        ids.add(fm.get("id"))
        if not is_apparatus(fm) and not spans_of(" ".join(map(str, fm.get("spans", [])))):
            print(f"{p.name}: spans must look like 'S1 00:22:10-00:25:40'"); bad += 1
        if "## Source" not in body and not is_apparatus(fm): print(f"{p.name}: no ## Source section"); bad += 1
        if fm.get("status") in ("shaped", "approved"):
            shaped = body.split("## Shaped", 1)[-1]
            paras = [b for b in re.split(r"\n\s*\n", shaped) if b.strip() and not b.strip().startswith(("#", "//", "=="))]
            uncited = [b for b in paras if "// src:" not in b]
            if uncited: print(f"{p.name}: {len(uncited)} shaped paragraph(s) without // src:"); bad += 1
            if "#asked" in shaped or re.search(r"^\s*\*\*\w+\*\*\s*\[S\d", shaped, re.M):
                print(f"{p.name}: interview format in Shaped text (questions or speaker labels) — rewrite as narrative"); bad += 1
    print(f"{bad} problems")


if __name__ == "__main__":
    {"coverage": cmd_coverage, "table": cmd_table, "check": cmd_check}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
