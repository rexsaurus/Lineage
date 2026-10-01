#!/usr/bin/env python3
"""Chapter map and index utilities. Run from the project root.

  index_tools.py wordcount   # update word_count + photo_count in data/chapters.csv
  index_tools.py terms       # scan #idx marks per chapter -> data/chapter_index.csv
  index_tools.py backindex   # compile and pull resolved page numbers -> data/back_index.csv
  index_tools.py xlsx        # build output/chapters.xlsx (all tabs)
"""
import csv, json, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

CH = Path("data/chapters.csv")
IDX_CALL = re.compile(r'#idx\(((?:\s*"[^"]*"\s*,?)+)\)')
IDX_TERM = re.compile(r'"([^"]*)"')
SRC = re.compile(r"\[S\d+ [^\]]+\]")


def chapter_files():
    return sorted(p for p in Path("chapters").glob("*.typ") if not p.name.startswith("9"))


def strip_calls(text, names=("chapter", "show: chapter.with", "photo", "plate", "plate-pair",
                                    "descent", "records", "photo-addendum", "part")):
    """Remove whole calls (possibly spanning lines) such as the chapter header,
    plates and THE RECORDS, so only the narrative is counted."""
    out, i = [], 0
    starts = tuple("#" + n + "(" for n in names)
    while i < len(text):
        hit = next((st for st in starts if text.startswith(st, i)), None)
        if not hit:
            out.append(text[i]); i += 1; continue
        depth, j = 0, i + len(hit) - 1
        while j < len(text):
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
            if depth == 0: break
        i = j
    return "".join(out)


def prose_words(text):
    text = strip_calls(text)
    lines = [l for l in text.splitlines() if not l.strip().startswith(("//", "#import"))]
    t = "\n".join(lines)
    t = re.sub(r"#idx(-see)?\([^)]*\)", "", t)
    t = re.sub(r"#\w+(\.\w+)?", "", t)
    return len(re.findall(r"[A-Za-z0-9’']+", t))


def cmd_wordcount():
    rows = list(csv.DictReader(open(CH)))
    fields = list(rows[0].keys())
    for k in ("word_count", "photo_count"):
        if k not in fields: fields.append(k)
    by_file = {r["file"]: r for r in rows}
    total = 0
    for f in chapter_files():
        t = f.read_text()
        r = by_file.get(f"chapters/{f.name}")
        if r is None:
            print(f"not in chapters.csv: {f}"); continue
        r["word_count"] = prose_words(t); r["photo_count"] = t.count("#photo(") + t.count("#plate(") + 2 * t.count("#plate-pair(")
        total += r["word_count"]
    with open(CH, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"{total} words across {len(rows)} chapters")


def cmd_terms():
    out = []
    for f in sorted(Path("chapters").glob("*.typ")):
        counts, srcs = defaultdict(int), defaultdict(set)
        pending = []  # terms in the current paragraph; its // src: line comes after it
        for line in f.read_text().splitlines():
            for call in IDX_CALL.findall(line):
                for term in IDX_TERM.findall(call):
                    counts[term] += 1
                    pending.append(term)
            m = SRC.findall(line) if line.strip().startswith("//") else []
            if m:
                for term in pending:
                    srcs[term].update(m)
                pending = []
        for term in sorted(counts, key=str.lower):
            main, _, sub = term.partition("!")
            out.append({"chapter_file": f.name, "term": main, "subentry": sub,
                        "mentions": counts[term], "sources": "; ".join(sorted(srcs[term]))})
    Path("data").mkdir(exist_ok=True)
    with open("data/chapter_index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["chapter_file", "term", "subentry", "mentions", "sources"])
        w.writeheader(); w.writerows(out)
    print(f"{len(out)} chapter-index rows")


def cmd_backindex():
    try:
        res = subprocess.run(["typst", "query", "--root", ".", "book/main.typ", "<idx-resolved>",
                              "--field", "value"], capture_output=True, text=True)
        if res.returncode:
            sys.exit(res.stderr)
        data = json.loads(res.stdout)[0]
    except FileNotFoundError:  # no CLI: fall back to the Python binding (pip install typst)
        import typst
        data = json.loads(typst.query("book/main.typ", "<idx-resolved>", field="value", root="."))[0]
    rows = [{"term": k.partition("!")[0], "subentry": k.partition("!")[2],
             "pages": ", ".join(map(str, sorted(v))), "see": ""} for k, v in data["entries"].items()]
    rows += [{"term": k, "subentry": "", "pages": "", "see": v} for k, v in data["see"].items()]
    rows.sort(key=lambda r: (r["term"].lower(), r["subentry"].lower()))
    with open("data/back_index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["term", "subentry", "pages", "see"]); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} back-index entries")


def cmd_xlsx():
    here = Path(__file__).parent
    sheets = [("Chapters", "data/chapters.csv"), ("Key Events", "facts/timeline.csv"),
              ("Chapter Index", "data/chapter_index.csv"), ("Back Index", "data/back_index.csv")]
    args = [f"{n}={p}" for n, p in sheets if Path(p).exists()]
    subprocess.run([sys.executable, str(here / "csv_to_xlsx.py"), "output/chapters.xlsx", *args], check=True)


if __name__ == "__main__":
    {"wordcount": cmd_wordcount, "terms": cmd_terms, "backindex": cmd_backindex, "xlsx": cmd_xlsx}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
