#!/usr/bin/env python3
"""Generate front matter, back matter and book/main.typ, then compile. Run from project root.

  build_book.py front      # book/front/title.typ + copyright.typ from book.yaml
  build_book.py glossary   # chapters/92-glossary.typ from data/reader_glossary.csv
  build_book.py sources    # chapters/93-about-the-recordings.typ from transcript/sessions.csv
  build_book.py main       # book/main.typ from data/chapters.csv + existing back matter
  build_book.py compile [--final]
  build_book.py all [--final]
  build_book.py sync       # copy $BOOKASSEMBLER/book/template.typ and missing front files into book/
"""
import csv, datetime, json, shutil, subprocess, sys
from pathlib import Path
import os
import yaml

HOME = Path(os.environ.get("BOOKASSEMBLER") or Path(__file__).resolve().parents[4])

BACK = [  # (file, label) in print order; included only if the file exists
    ("chapters/90-timeline.typ", "timeline"),
    ("chapters/92-glossary.typ", "glossary"),
    ("chapters/91-where-the-records-are.typ", "records"),
    ("chapters/93-about-the-recordings.typ", "sources"),
    ("chapters/94-acknowledgments.typ", "acknowledgments"),
]


def cfg():
    return yaml.safe_load(open("book.yaml")) or {}


def t(s):  # escape for Typst markup
    s = "" if s is None else str(s)
    for a in "\\#[]*_@$<`":
        s = s.replace(a, "\\" + a)
    return s


def q(s):  # escape for a Typst string literal
    return ("" if s is None else str(s)).replace("\\", "\\\\").replace('"', '\\"')


def cmd_sync():
    """The template lives in the BookAssembler repo; each project gets a fresh copy at build
    time. Front-matter pages are copied only if the project doesn't have its own yet."""
    src = HOME / "book"
    if not (src / "template.typ").exists():
        sys.exit(f"template not found at {src}; set BOOKASSEMBLER to the repo path")
    Path("book/front").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "template.typ", "book/template.typ")
    for f in (src / "front").glob("*.typ"):
        if not (Path("book/front") / f.name).exists():
            shutil.copy2(f, Path("book/front") / f.name)
    print(f"template synced from {src}")


def cmd_front():
    c = cfg(); n = c.get("narrator", {}); i = c.get("interviewer", {})
    title = c.get("title") or "Untitled"; sub = c.get("subtitle") or ""
    Path("book/front").mkdir(parents=True, exist_ok=True)
    Path("book/front/title.typ").write_text(f'''#import "/book/template.typ": *
#plain-page[
  #v(2.2in)
  #align(center)[
    #text(font: display-font, size: 30pt)[{t(title)}] \\
    #v(0.4em)
    #text(size: 13pt, style: "italic")[{t(sub)}]
    #v(1.6in)
    #text(size: 12pt, tracking: 0.1em)[#upper[{t(i.get("name"))}]]
  ]
]
''')
    year = datetime.date.today().year
    Path("book/front/copyright.typ").write_text(f'''#import "/book/template.typ": *
#plain-page[
  #v(1fr)
  #set text(size: 8.5pt)
  #set par(first-line-indent: 0pt, justify: false)
  Copyright © {year} {t(i.get("name"))}. All rights reserved.

  Written from recorded interviews with {t(n.get("name"))}. Every fact and quotation
  traces to the original recordings, which are preserved by the family.

  Set in EB Garamond.
]
''')
    if not Path("book/front/dedication.typ").exists():
        Path("book/front/dedication.typ").write_text('#import "/book/template.typ": *\n#plain-page[\n  #v(2.5in)\n  #align(center, text(style: "italic")[#note[dedication — write book/front/dedication.typ]])\n]\n')
    print("front matter written")


def cmd_glossary():
    p = Path("data/reader_glossary.csv")
    if not p.exists():
        print("no data/reader_glossary.csv — skipped"); return
    rows = sorted(csv.DictReader(open(p, encoding="utf-8")), key=lambda r: r["term"].lower())
    L = ['#import "/book/template.typ": *', '#show: chapter.with("Glossary", columns: 2)', "",
         "#set par(first-line-indent: 0pt, hanging-indent: 1.2em, spacing: 0.6em)", ""]
    for r in rows:
        L += [f"*{t(r['term'])}* — {t(r['definition'])}", ""]
    Path("chapters/92-glossary.typ").write_text("\n".join(L))
    print(f"glossary: {len(rows)} terms")


def cmd_sources():
    p = Path("transcript/sessions.csv")
    if not p.exists():
        print("no transcript/sessions.csv — skipped"); return
    c = cfg(); n = c.get("narrator", {}); i = c.get("interviewer", {})
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    pron = {"she": {"sub": "she", "pos": "her"}, "he": {"sub": "he", "pos": "his"},
            "they": {"sub": "they", "pos": "their"}}.get(str(n.get("pronoun", "they")).lower(),
                                                         {"sub": "they", "pos": "their"})
    L = ['#import "/book/template.typ": *', '#show: chapter.with("About the Recordings")', "",
         "#set par(first-line-indent: 0pt)", "",
         f"This book was made from recorded conversations between {t(n.get('name'))} and "
         f"{t(i.get('name'))}. The recordings were transcribed word for word, and every passage "
         "in the book was checked against them. Every fact in the narrative comes from what "
         f"{pron['sub']} said, and every quotation is in {pron['pos']} own words, with only filler words "
         "and false starts removed.", "",
         "#table(columns: (auto, 1fr, auto, auto), stroke: none, column-gutter: 1em, row-gutter: 0.4em,",
         "  [*Session*], [*Recording*], [*Date*], [*Length*],"]
    for r in rows:
        name = Path(r.get("file", "")).stem
        L.append(f"  [{t(r.get('session'))}], [{t(name)}], [{t(r.get('recorded', ''))}], [{t(r.get('duration', ''))}],")
    L += [")", "", "The original recordings are kept by the family; see Where the Records Are."]
    Path("chapters/93-about-the-recordings.typ").write_text("\n".join(L) + "\n")
    print(f"sources page: {len(rows)} sessions")


def cmd_main():
    c = cfg()
    chapters = list(csv.DictReader(open("data/chapters.csv", encoding="utf-8")))
    chapters.sort(key=lambda r: float(r["chapter"]))
    L = ['// GENERATED by book-generator. Edit data/chapters.csv and book.yaml instead.',
         '#import "/book/template.typ": *', "",
         f'#show: book.with(title: "{q(c.get("title"))}", subtitle: "{q(c.get("subtitle"))}",',
         f'  author: "{q(c.get("interviewer", {}).get("name"))}", trim: "{q(c.get("print", {}).get("trim", "7x10"))}")', "",
         '#include "/book/front/title.typ"', '#include "/book/front/copyright.typ"',
         '#include "/book/front/dedication.typ"', '#include "/book/front/contents.typ"']
    for extra in ("foreword", "introduction"):  # foreword (by someone else) precedes the author's introduction
        if Path(f"book/front/{extra}.typ").exists():
            L.append(f'#include "/book/front/{extra}.typ"')
    L += ["",
          "#show: main-matter", ""]
    part, missing = None, []
    for ch in chapters:
        if ch.get("part") and ch["part"] != part:
            part = ch["part"]; L.append(f'#part("{q(part)}")')
        if Path(ch["file"]).exists():
            L.append(f'#include "/{ch["file"]}"')
        else:
            missing.append(ch["file"]); L.append(f'// missing: {ch["file"]}')
    L.append("")
    back = [f for f, _ in BACK if Path(f).exists()]
    if back:
        L.append('#part("Notes and Records")')
        L += [f'#include "/{f}"' for f in back]
    L += ["", "#make-index()",
          "// Printers need an even page count. build_book.py compiles once, counts the pages",
          "// and, if odd, recompiles with pad=true to add one truly blank last page.",
          '#if sys.inputs.at("pad", default: "false") == "true" { page(header: none, footer: none)[] }', ""]
    Path("book/main.typ").write_text("\n".join(L))
    print(f"main.typ: {len(chapters) - len(missing)} chapters, back matter: {', '.join(back) or 'none'}")
    if missing: print("MISSING chapter files:", ", ".join(missing))


FONT_DIR = HOME / "fonts"


def typst_compile(out, final, pad):
    cmd = ["typst", "compile", "--root", "."]
    if FONT_DIR.exists(): cmd += ["--font-path", str(FONT_DIR)]
    cmd += ["--input", f"draft={'false' if final else 'true'}", "--input", f"pad={'true' if pad else 'false'}",
            "book/main.typ", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr)
    return r.stderr


def pdf_pages(out):
    info = subprocess.run(["pdfinfo", out], capture_output=True, text=True).stdout if shutil.which("pdfinfo") else ""
    for l in info.splitlines():
        if l.startswith("Pages:"): return int(l.split()[1])
    import re  # no pdfinfo: count page objects
    return len(re.findall(rb"/Type\s*/Page[^s]", Path(out).read_bytes()))


def cmd_compile(final=False):
    if not shutil.which("typst"): sys.exit("typst not found: run `make install` or see docs/HOWTO.md")
    out = "output/book-final.pdf" if final else "output/book-draft.pdf"
    Path("output").mkdir(exist_ok=True)
    warn = typst_compile(out, final, pad=False)
    n = pdf_pages(out)
    if n % 2:
        warn = typst_compile(out, final, pad=True); n = pdf_pages(out)
    for line in warn.splitlines():
        if line.startswith("warning:") and "unknown font family" not in line: print(line)
    print(f"compiled {out} Pages: {n}")


if __name__ == "__main__":
    a = sys.argv[1:] or [""]
    final = "--final" in a
    cmds = {"sync": cmd_sync, "front": cmd_front, "glossary": cmd_glossary, "sources": cmd_sources,
            "main": cmd_main, "compile": lambda: cmd_compile(final)}
    if a[0] == "all":
        for k in ("sync", "front", "glossary", "sources", "main", "compile"): cmds[k]()
    elif a[0] in cmds:
        cmds[a[0]]()
    else:
        sys.exit(__doc__)
