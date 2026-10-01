#!/usr/bin/env python3
"""Print-readiness checks for a BookAssembler PDF.

Usage: preflight.py output/book-final.pdf --trim 7x10 [--printer kdp] [--color bw]
Run from the project root (it scans chapters/*.typ for #photo and #plate calls).
Uses poppler (pdfinfo, pdffonts, pdftotext) when installed; without it, page count and size
are read from the PDF directly and the font and draft-marker checks are skipped.
"""
import argparse, re, shutil, subprocess, sys
from pathlib import Path

TRIMS = {"6x9": (6, 9), "7x10": (7, 10), "8x10": (8, 10), "8.5x11": (8.5, 11)}
TEXT_MARGINS = 0.875 + 0.625  # inside + outside, inches (must match template.typ)
MIN_PAGES = {"kdp": 24, "ingramspark": 18, "lulu": 32, "blurb": 20}
PHOTO = re.compile(r'#photo\(\s*"([^"]+)"(.*?)\)\s*$', re.S | re.M)
PLATE = re.compile(r'#plate(?:-pair)?\(\s*"([^"]+)"(.*?)\)\s*$', re.S | re.M)
WIDTH = re.compile(r'width:\s*(\d+)%')
WIDTH_IN = re.compile(r'width:\s*([\d.]+)in')
POPPLER = bool(shutil.which("pdfinfo"))

def run(cmd):
    if not shutil.which(cmd[0]):
        return ""
    return subprocess.run(cmd, capture_output=True, text=True).stdout

def pdf_basics(path):
    """(pages, width_pt, height_pt) without poppler: count page objects, read the first MediaBox."""
    data = Path(path).read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    mb = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", data)
    w = float(mb.group(3)) - float(mb.group(1)) if mb else 0
    h = float(mb.group(4)) - float(mb.group(2)) if mb else 0
    return pages, w, h

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--trim", default="7x10")
    ap.add_argument("--printer", default="kdp"); ap.add_argument("--color", default="bw")
    a = ap.parse_args()
    problems, notes = [], []

    if POPPLER:
        info = run(["pdfinfo", a.pdf])
        pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        size = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info)
        w_in, h_in = float(size.group(1)) / 72, float(size.group(2)) / 72
    else:
        pages, wpt, hpt = pdf_basics(a.pdf)
        w_in, h_in = wpt / 72, hpt / 72
        notes.append("poppler not installed: font-embedding and draft-marker checks skipped")
    tw, th = TRIMS[a.trim]
    if abs(w_in - tw) > 0.01 or abs(h_in - th) > 0.01:
        problems.append(f"Page size {w_in:.2f}x{h_in:.2f}in does not match trim {a.trim}")
    if pages % 2:
        problems.append(f"Odd page count ({pages}); add a blank final page")
    if pages < MIN_PAGES.get(a.printer, 24):
        problems.append(f"{pages} pages is under the {a.printer} minimum of {MIN_PAGES[a.printer]}")
    notes.append(f"Pages: {pages}  Trim: {a.trim}")

    for line in run(["pdffonts", a.pdf]).splitlines()[2:]:
        cols = line.split()
        if len(cols) >= 5 and "no" in cols[-5:-3]:
            problems.append(f"Font not embedded: {cols[0]}")

    text_w = tw - TEXT_MARGINS
    try:
        from PIL import Image
    except ImportError:
        Image = None
        notes.append("Pillow missing: skipped image resolution checks")
    for chap in sorted(Path("chapters").glob("*.typ")):
        text = chap.read_text()
        calls = [(m.group(1), m.group(2)) for m in PHOTO.finditer(text)] + \
                [(m.group(1), m.group(2)) for m in PLATE.finditer(text)]
        for raw_path, args in calls:
            path = Path(raw_path.lstrip("/"))
            if not path.exists():
                problems.append(f"{chap.name}: missing image {path}"); continue
            if Image is None:
                continue
            m_in, m_pct = WIDTH_IN.search(args), WIDTH.search(args)
            if m_in:
                width_in, label = float(m_in.group(1)), f"{m_in.group(1)} in"
            else:
                pct = int(m_pct.group(1)) / 100 if m_pct else 1.0
                width_in, label = text_w * pct, f"{pct:.0%} width"
            with Image.open(path) as im:
                ppi = im.width / width_in
                if ppi < 200:
                    problems.append(f"{chap.name}: {path.name} only {ppi:.0f} ppi at {label} (need 300; 200 absolute floor)")
                elif ppi < 300:
                    notes.append(f"{chap.name}: {path.name} {ppi:.0f} ppi at {label}: acceptable, 300 preferred")
                if a.color == "bw" and im.mode not in ("L", "LA", "1"):
                    notes.append(f"{chap.name}: {path.name} is {im.mode}; convert to grayscale for a B&W interior")

    draft_marks = run(["pdftotext", a.pdf, "-"]).count("⟦")
    if draft_marks:
        problems.append(f"{draft_marks} draft markers (⟦...⟧) visible — compile with --input draft=false")

    print("\n".join(notes))
    print("\nPROBLEMS:" if problems else "\nNo blocking problems found.")
    for p in problems:
        print(" -", p)
    sys.exit(1 if problems else 0)

if __name__ == "__main__":
    main()
