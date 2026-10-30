#!/usr/bin/env python3
"""Keep story paragraphs readable: split prose paragraphs longer than --max words into shorter ones, at sentence
ends that fall outside quotation marks. Nothing is reworded, added or dropped; only paragraph breaks are inserted.

    python split_paragraphs.py --project DIR                  # report paragraphs over the limit (default 130 words)
    python split_paragraphs.py --project DIR --fix            # split them in place
    python split_paragraphs.py --project DIR --fix --max 110 --only cabin

Works on the Typst story files listed in data/chapters.csv. Only plain prose paragraphs are touched: a paragraph that
contains layout code with brackets (#opening[...], #verbatim[...], #records(...), tables) or starts with '#', '//', '[',
'(' or ')' is left alone. Index markers such as #idx("Name") are kept attached to their word. A source note
(// src:, // context:, // record:) after a paragraph stays after its last part.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

SENT_END = re.compile(r'(?<=[.!?])(["”’)]*)\s+(?=["“(]?[A-Z0-9_])')
MARKER = re.compile(r'#\w[\w.-]*\([^()]*\)')          # #idx("…") and similar inline calls
WRAP = 100


def words(t):
    return len(re.findall(r"[A-Za-z0-9’']+", MARKER.sub("", t)))


def boundaries(text):
    """Offsets just after sentence ends that are outside any quotation."""
    masked = MARKER.sub(lambda m: "x" * len(m.group(0)), text)
    out, depth_straight, depth_curly = [], 0, 0
    quote_state = []
    for i, ch in enumerate(masked):
        if ch == '"':
            depth_straight ^= 1
        elif ch == "“":
            depth_curly += 1
        elif ch == "”":
            depth_curly = max(0, depth_curly - 1)
        quote_state.append(depth_straight == 0 and depth_curly == 0)
    for m in SENT_END.finditer(masked):
        cut = m.start() + len(m.group(1))            # after the closing quote/bracket, before the space
        if cut < len(quote_state) and quote_state[cut - 1] and not re.search(r"\b(?:Mr|Mrs|Dr|St|Jr|Sr|No|Co|Pte|Lt|Capt|Gen|Rev|vol|pp?|ed)\.$", masked[:cut - len(m.group(1))]):
            out.append(cut)
    return out


def split_text(text, mx):
    if words(text) <= mx:
        return [text]
    cuts = boundaries(text)
    if not cuts:
        return [text]
    parts, start = [], 0
    target = max(60, mx * 2 // 3)
    acc_cut = None
    for c in cuts:
        if words(text[start:c]) >= target:
            # choose this cut, or the previous one if it lands closer to the target
            if acc_cut is not None and abs(words(text[start:acc_cut]) - target) < abs(words(text[start:c]) - target) \
                    and words(text[start:acc_cut]) >= 40:
                c = acc_cut
            if words(text[c:]) >= 35:
                parts.append(text[start:c].strip()); start = c
            acc_cut = None
            continue
        acc_cut = c
    parts.append(text[start:].strip())
    return [p for p in parts if p]


# a line must not begin with something Typst reads as markup at the start of a line:
# "/ " (term list), "- " (list), "+ " (enumeration), "= " (heading), "12. " (numbered list)
LINE_START_MARKUP = re.compile(r"^(?:[/+=-]|\d+\.)$")


def wrap(t):
    lines, cur = [], ""
    for w in t.split(" "):
        if cur and len(cur) + 1 + len(w) > WRAP and not LINE_START_MARKUP.match(w):
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        lines.append(cur)
    return lines


def process(path, mx, fix):
    lines = path.read_text(encoding="utf-8").split("\n")
    out, buf, found = [], [], []

    def flush():
        if not buf:
            return
        text = " ".join(l.strip() for l in buf)
        plain = not re.search(r"[\[\]]", text) and not re.match(r"[#/\[\(\)]", text)
        if plain and words(text) > mx:
            parts = split_text(text, mx)
            found.append((words(text), len(parts), text[:70]))
            if fix and len(parts) > 1:
                for i, p in enumerate(parts):
                    if i:
                        out.append("")
                    out.extend(wrap(p))
                buf.clear()
                return
        out.extend(buf)
        buf.clear()

    for line in lines:
        t = line.strip()
        if not t or t.startswith("//") or t.startswith("#") or line.startswith((" ", "\t")) and not buf:
            flush(); out.append(line); continue
        buf.append(line)
    flush()
    if fix:
        path.write_text("\n".join(out), encoding="utf-8")
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".")
    ap.add_argument("--max", type=int, default=130, help="longest paragraph allowed, in words (default 130)")
    ap.add_argument("--fix", action="store_true", help="split in place (default: report only)")
    ap.add_argument("--only", default="", help="only story files whose name contains this text")
    a = ap.parse_args()
    root = Path(a.project).expanduser().resolve()
    cs = root / "data" / "chapters.csv"
    files = [r["file"] for r in csv.DictReader(open(cs, encoding="utf-8"))] if cs.exists() else \
        [p.relative_to(root).as_posix() for p in sorted((root / "chapters").glob("*.typ"))]
    total = 0
    for rel in files:
        if not rel.endswith(".typ") or a.only not in rel or not (root / rel).is_file():
            continue
        found = process(root / rel, a.max, a.fix)
        total += len(found)
        if found:
            print(f"{rel}: {len(found)} paragraph(s) over {a.max} words" + (" — split" if a.fix else ""))
    print(f"{total} long paragraph(s){' split' if a.fix else ' found'} (limit {a.max} words)")


if __name__ == "__main__":
    sys.exit(main())
