#!/usr/bin/env python3
"""Write a unit's ## Shaped section and set its status.

    python $BOOKASSEMBLER/scripts/shape.py U002 shaped/U002.md
    python $BOOKASSEMBLER/scripts/shape.py U002 - < text.md          # text on stdin
    python $BOOKASSEMBLER/scripts/shape.py U002 text.md --lead-in "Years later," --break-before
    python $BOOKASSEMBLER/scripts/shape.py --json batch.json          # many units at once
    python $BOOKASSEMBLER/scripts/shape.py U002 --status approved     # status only

Run from the book project folder (or --project DIR). Operates on
content/units/U###-*.md. Replaces everything between "## Shaped" and
"## Notes" with the new text; ## Source and ## Notes are never touched.
Status defaults to "shaped" when text is given.

batch.json maps unit id -> text, or -> {"text": ..., "lead_in": ...,
"break_before": true, "status": "shaped"}.

Importable: `from shape import set_shaped` (after chdir to the project).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

UNITS = Path("content/units")


def unit_path(uid):
    hits = [p for p in UNITS.glob(f"{uid}-*.md")] + [p for p in UNITS.glob(f"{uid}.md")]
    if len(hits) != 1:
        raise SystemExit(f"{uid}: expected one file in {UNITS}/, found {len(hits)}")
    return hits[0]


def _set_field(head, key, value):
    """Set `key: value` inside the frontmatter only (never in ## Source)."""
    end = head.index("\n---", 3)
    fm, body = head[:end], head[end:]
    line = f"{key}: {value}".rstrip()
    pat = re.compile(rf"^{key}:.*$", re.M)
    fm = pat.sub(lambda _m: line, fm, count=1) if pat.search(fm) else fm + "\n" + line
    return fm + body


def set_shaped(uid, text=None, lead_in=None, break_before=None, status=None):
    p = unit_path(uid)
    s = p.read_text(encoding="utf-8")
    if "## Shaped" not in s:
        raise SystemExit(f"{p.name}: no ## Shaped section")
    head, rest = s.split("## Shaped", 1)
    shaped, notes = (rest.split("## Notes", 1) + [""])[:2] if "## Notes" in rest else (rest, "\n")
    if text is not None:
        shaped = "\n\n" + text.strip() + "\n\n"
        status = status or "shaped"
    if status:
        head = _set_field(head, "status", status)
    if lead_in is not None:
        head = _set_field(head, "lead_in", json.dumps(lead_in, ensure_ascii=False) if lead_in else "")
    if break_before is not None:
        head = _set_field(head, "break_before", "true" if break_before else "false")
    p.write_text(head + "## Shaped" + shaped + "## Notes" + notes, encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser(description="Write a unit's ## Shaped section.")
    P.add_project_arg(ap)
    ap.add_argument("unit", nargs="?", help="unit id, e.g. U002")
    ap.add_argument("text_file", nargs="?", help="file with the shaped text, or - for stdin")
    ap.add_argument("--json", help="batch file: {unit id: text or {text, lead_in, ...}}")
    ap.add_argument("--lead-in")
    ap.add_argument("--break-before", action="store_true", default=None)
    ap.add_argument("--no-break-before", dest="break_before", action="store_false")
    ap.add_argument("--status", help="separated | shaped | approved (default with text: shaped)")
    a = ap.parse_args()
    if a.json:
        a.json = str(Path(a.json).expanduser().resolve())
    if a.text_file and a.text_file != "-":
        a.text_file = str(Path(a.text_file).expanduser().resolve())
    P.enter_project(a.project)

    if a.json:
        data = json.loads(Path(a.json).read_text(encoding="utf-8"))
        for uid, v in data.items():
            if isinstance(v, str):
                set_shaped(uid, v)
            else:
                set_shaped(uid, v.get("text"), v.get("lead_in"), v.get("break_before"),
                           v.get("status"))
        print(f"shaped {len(data)} unit(s)")
        return
    if not a.unit:
        ap.error("give a unit id (and a text file), or --json")
    text = None
    if a.text_file == "-":
        text = sys.stdin.read()
    elif a.text_file:
        text = Path(a.text_file).read_text(encoding="utf-8")
    if text is None and not (a.status or a.lead_in is not None or a.break_before is not None):
        ap.error("nothing to do: give a text file, - for stdin, or --status/--lead-in")
    p = set_shaped(a.unit, text, a.lead_in, a.break_before, a.status)
    print(f"{p.name}: updated")


if __name__ == "__main__":
    main()
