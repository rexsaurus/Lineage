#!/usr/bin/env python3
"""Generate front matter, back matter and book/main.typ, then compile. Run from project root.

  build_book.py front      # book/front/title.typ + copyright.typ from book.yaml
  build_book.py glossary   # chapters/92-glossary.typ from data/reader_glossary.csv
  build_book.py sources    # chapters/93-about-the-recordings.typ from transcript/sessions.csv
  build_book.py main       # book/main.typ from data/chapters.csv + existing back matter
  build_book.py compile [--final] [--pages [--ppi N]]
  build_book.py all [--final]
  build_book.py sync       # copy $LINEAGE/book/template.typ and missing front files into book/
  build_book.py chapter chapters/NN-x.typ [--final] [--pages [--ppi N]]
                           # preview one chapter alone: output/preview-NN-x.pdf

--pages also writes one image per page to output/pages/<name>/ (JPEG if Pillow is
installed, else PNG), for sharing pages outside the PDF. --ppi defaults to the largest
whole value that keeps the long side within 2048 px (204 for 7x10); use --final with it
so the images carry no draft highlighting. Uses the typst CLI, or the `typst` Python
package when the CLI is missing.
"""
import csv, datetime, json, math, shutil, subprocess, sys
from pathlib import Path
import os
import yaml

# The plugin root (it holds book/ and fonts/): plugins/lineage, or wherever Claude Code
# installed the plugin. A repo checkout also works via its top-level symlinks.
HOME = Path(os.environ.get("LINEAGE") or Path(__file__).resolve().parents[3])

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
    """The template lives in the Lineage repo; each project gets a fresh copy at build
    time. Front-matter pages are copied only if the project doesn't have its own yet."""
    src = HOME / "book"
    if not (src / "template.typ").exists():
        sys.exit(f"template not found at {src}; set LINEAGE to the repo path")
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


def typst_compile(src, out, inputs, fmt=None, ppi=None):
    """Compile with the typst CLI, or the `typst` Python package when the CLI is missing.
    `out` may hold {0p} (page number) for one image per page."""
    if shutil.which("typst"):
        cmd = ["typst", "compile", "--root", "."]
        if FONT_DIR.exists(): cmd += ["--font-path", str(FONT_DIR)]
        for k, v in inputs.items(): cmd += ["--input", f"{k}={v}"]
        if fmt: cmd += ["--format", fmt]
        if ppi: cmd += ["--ppi", str(ppi)]
        r = subprocess.run(cmd + [src, out], capture_output=True, text=True)
        if r.returncode: sys.exit(r.stderr)
        return r.stderr
    try:
        import typst
    except ImportError:
        sys.exit("typst not found: run `make install` (or `pip install typst`), or see docs/HOWTO.md")
    kw = {"root": ".", "sys_inputs": inputs, "font_paths": [str(FONT_DIR)] if FONT_DIR.exists() else []}
    if fmt: kw["format"] = fmt
    if ppi: kw["ppi"] = ppi
    try:
        if "{0p}" in out:  # the package returns one image per page instead of naming files
            pages = typst.compile(src, **kw)
            pages = pages if isinstance(pages, list) else [pages]
            w = len(str(len(pages)))
            for i, b in enumerate(pages, 1): Path(out.replace("{0p}", str(i).zfill(w))).write_bytes(b)
        else:
            typst.compile(src, output=out, **kw)
    except Exception as e:  # the package raises on compile errors instead of returning a code
        sys.exit(str(e))
    return ""


def pdf_pages(out):
    info = subprocess.run(["pdfinfo", out], capture_output=True, text=True).stdout if shutil.which("pdfinfo") else ""
    for l in info.splitlines():
        if l.startswith("Pages:"): return int(l.split()[1])
    import re  # no pdfinfo: count page objects
    return len(re.findall(rb"/Type\s*/Page[^s]", Path(out).read_bytes()))


def inputs_for(final, pad=False):
    return {"draft": "false" if final else "true", "pad": "true" if pad else "false"}


def print_warnings(warn):
    for line in warn.splitlines():
        if line.startswith("warning:") and "unknown font family" not in line: print(line)


def default_ppi():
    """Largest whole ppi that keeps the page's long side within 2048 px."""
    trim = str((cfg().get("print") or {}).get("trim", "7x10"))
    try: h = max(float(x) for x in trim.lower().split("x"))
    except ValueError: h = 10.0
    return math.floor(2048 / h)


def export_pages(src, name, inputs, ppi=None):
    """One image per page in output/pages/<name>/; JPEG (quality 90) when Pillow is available."""
    d = Path("output/pages") / name
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    ppi = ppi or default_ppi()
    typst_compile(src, str(d / "page-{0p}.png"), inputs, fmt="png", ppi=ppi)
    pngs = sorted(d.glob("page-*.png"))
    try:
        from PIL import Image
        for p in pngs:
            Image.open(p).convert("RGB").save(p.with_suffix(".jpg"), quality=90); p.unlink()
        kind = "JPEG"
    except ImportError:
        kind = "PNG"
    print(f"{len(pngs)} page images ({kind}, {ppi} ppi) in {d}/")


def cmd_compile(final=False, pages=False, ppi=None):
    out = "output/book-final.pdf" if final else "output/book-draft.pdf"
    Path("output").mkdir(exist_ok=True)
    warn = typst_compile("book/main.typ", out, inputs_for(final))
    n, pad = pdf_pages(out), False
    if n % 2:
        pad = True
        warn = typst_compile("book/main.typ", out, inputs_for(final, pad)); n = pdf_pages(out)
    print_warnings(warn)
    print(f"compiled {out} Pages: {n}")
    if pages: export_pages("book/main.typ", "book", inputs_for(final, pad), ppi)


def cmd_chapter(file, final=False, pages=False, ppi=None):
    """Preview one chapter on its own, in the book's template, trim and folios, without
    rebuilding the whole book. Writes output/preview.typ (generated) and the PDF."""
    if not file or not Path(file).exists(): sys.exit(f"chapter file not found: {file}")
    if not Path("book/template.typ").exists(): cmd_sync()
    c = cfg(); name = Path(file).stem
    Path("output").mkdir(exist_ok=True)
    Path("output/preview.typ").write_text("\n".join([
        "// GENERATED by build_book.py chapter: a one-chapter preview. Not part of the book.",
        '#import "/book/template.typ": *',
        f'#show: book.with(title: "{q(c.get("title"))}", subtitle: "{q(c.get("subtitle"))}",',
        f'  author: "{q(c.get("interviewer", {}).get("name"))}", trim: "{q(c.get("print", {}).get("trim", "7x10"))}")',
        "#show: main-matter",
        f'#include "/{Path(file).as_posix().lstrip("/")}"', ""]))
    out = f"output/preview-{name}.pdf"
    print_warnings(typst_compile("output/preview.typ", out, inputs_for(final)))
    print(f"compiled {out} Pages: {pdf_pages(out)}")
    if pages: export_pages("output/preview.typ", name, inputs_for(final), ppi)


if __name__ == "__main__":
    a = sys.argv[1:] or [""]
    final, pages = "--final" in a, "--pages" in a
    ppi = int(a[a.index("--ppi") + 1]) if "--ppi" in a and a.index("--ppi") + 1 < len(a) else None
    args = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--ppi")]
    cmds = {"sync": cmd_sync, "front": cmd_front, "glossary": cmd_glossary, "sources": cmd_sources,
            "main": cmd_main, "compile": lambda: cmd_compile(final, pages, ppi),
            "chapter": lambda: cmd_chapter(args[1] if len(args) > 1 else "", final, pages, ppi)}
    if a[0] == "all":
        for k in ("sync", "front", "glossary", "sources", "main", "compile"): cmds[k]()
    elif a[0] in cmds:
        cmds[a[0]]()
    else:
        sys.exit(__doc__)
