#!/usr/bin/env python3
"""The versioned edition of the whole book: a full-resolution PDF for print and a compressed copy (Ghostscript
/ebook, 150 dpi images) for the website, Drive and email.

    python book_edition.py --project DIR           # rebuild at the current VERSION
    python book_edition.py --project DIR --bump    # next version first (1.0 -> 1.1, 1.9 -> 1.10)

The project's VERSION file holds the version (created as 1.0 if missing). The book is compiled from
settings.publish.book_entry when set (any Typst file in the project; it gets --input updated=<date>
--input version=<VERSION>), otherwise with Lineage's normal build (book-generator build_book.py compile, from
book/main.typ). Out: output/<slug of the title>-v<VERSION>.pdf; older <slug>-v*.pdf files in output/ are removed.
r2_sync.py uploads the edition as <prefix>/book/<slug>-v<VERSION>.pdf and <prefix>/book/<slug>.pdf.
"""
import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402
import _publish  # noqa: E402


def bump(v):
    head, _, last = v.rpartition(".")
    return f"{head}.{int(last) + 1}" if head and last.isdigit() else (f"{int(v) + 1}" if v.isdigit() else v + ".1")


def main():
    ap = argparse.ArgumentParser(description="versioned, compressed edition of the book")
    add_project_arg(ap)
    ap.add_argument("--bump", action="store_true", help="increase VERSION before building")
    a = ap.parse_args()
    root = enter_project(a.project)
    cfg = _publish.settings(root)
    if not cfg.get("book_entry"):
        print("no book/main.typ and no settings.publish.book_entry: nothing to build (make draft first)")
        return
    vp = Path("VERSION")
    v = vp.read_text().strip() if vp.exists() else ""
    if not v:
        v = "1.0"
        vp.write_text(v + "\n")
    if a.bump:
        v = bump(v)
        vp.write_text(v + "\n")
        print(f"VERSION -> {v}")
    updated = date.today().strftime("%-d %B %Y")
    Path("output").mkdir(exist_ok=True)
    full = Path("output") / f"{cfg['slug']}-full.pdf"
    entry = cfg.get("book_entry") or ""
    custom = entry and entry != "book/main.typ"
    if custom:
        if not Path(entry).is_file():
            sys.exit(f"settings.publish.book_entry {entry} not found")
        if not shutil.which("typst"):
            sys.exit("typst is not installed (brew install typst)")
        _, fonts = _publish.book_template()
        cmd = ["typst", "compile", "--root", "."] + (["--font-path", str(fonts)] if fonts else [])
        cmd += ["--input", f"updated={updated}", "--input", f"version={v}", entry, str(full)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit("typst failed: " + (r.stderr.strip().splitlines() or [""])[0])
    elif Path("book/main.typ").exists():
        bb = _publish.lineage_home() / "plugins" / "lineage" / "skills" / "book-generator" / "scripts" / "build_book.py"
        r = subprocess.run([sys.executable, str(bb), "compile"])
        if r.returncode or not Path("output/book-draft.pdf").exists():
            sys.exit("the book build failed (see above)")
        shutil.copy2("output/book-draft.pdf", full)
    else:
        sys.exit("book/main.typ is missing")
    out = Path("output") / f"{cfg['slug']}-v{v}.pdf"
    if not _publish.gs_compress(full, out):
        shutil.copy2(full, out)
        print("Ghostscript not found (brew install ghostscript): the edition is uncompressed")
    for old in Path("output").glob(f"{cfg['slug']}-v*.pdf"):
        if old != out:
            old.unlink()
    print(f"Version {v}, updated {updated}")
    print(f"  print: {full} ({full.stat().st_size // 1024} KB)")
    print(f"  web:   {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
