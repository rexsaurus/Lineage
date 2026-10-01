#!/usr/bin/env python3
"""Extract photos (in document order) from a photos document into photos/source/ and
seed photos/photo_index.csv.

Accepts: .docx, .pdf, .zip, or a folder of images. Google Docs: export to .docx first.
Usage: extract_photos.py <input> [--start 1] [--out photos]
Existing index rows are kept; new photos get the next free IDs.
"""
import argparse, csv, io, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".heic"}
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
FIELDS = ["id", "kind", "source_file", "source_position", "original_caption", "px_width", "px_height",
          "exif_date", "holder", "catalogue_ref", "subject", "people", "people_basis",
          "people_confidence", "date", "date_basis", "date_confidence", "location",
          "location_basis", "rendering_basis", "caption", "comment", "chapter",
          "placement_anchor", "print_file", "max_print_width_in", "print_permission",
          "needs_attention", "status"]
# kind: photograph | illustration | map  (illustration = AI-generated or artist's rendering;
# map = drawn by script from sourced positions). rendering_basis: for illustrations, the
# scene in the material and the likeness/source it was based on; for maps, script + CSV.


def para_text(p):
    return "".join(t.text or "" for t in p.iter(f"{{{NS['w']}}}t")).strip()


def from_docx(path):
    z = zipfile.ZipFile(path)
    rels = {r.get("Id"): r.get("Target") for r in
            ET.fromstring(z.read("word/_rels/document.xml.rels")).findall("pr:Relationship", NS)}
    body = ET.fromstring(z.read("word/document.xml")).find("w:body", NS)
    paras = list(body.iter(f"{{{NS['w']}}}p"))
    texts = [para_text(p) for p in paras]
    out = []
    for i, p in enumerate(paras):
        for blip in p.iter(f"{{{NS['a']}}}blip"):
            rid = blip.get(f"{{{NS['r']}}}embed")
            target = rels.get(rid)
            if not target:
                continue
            data = z.read("word/" + target.lstrip("/").replace("word/", "", 1))
            near = [t for t in (texts[i], *texts[i + 1:i + 3], *texts[max(0, i - 2):i][::-1]) if t]
            out.append((Path(target).suffix.lower(), data, f"paragraph {i + 1}", " | ".join(near[:3])))
    return out


def from_pdf(path):
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["pdfimages", "-all", "-p", str(path), str(tmp / "img")], check=True)
    out = []
    for f in sorted(tmp.iterdir()):
        m = re.match(r"img-(\d+)-(\d+)", f.stem)
        page = int(m.group(1)) if m else 0
        if f.stat().st_size < 15_000:   # skip icons, rules, masks
            continue
        text = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
                              capture_output=True, text=True).stdout
        text = " ".join(text.split())[:300]
        out.append((f.suffix.lower(), f.read_bytes(), f"page {page}", text))
    return out


def from_folder(path):
    return [(f.suffix.lower(), f.read_bytes(), f.name, "")
            for f in sorted(path.rglob("*")) if f.suffix.lower() in IMG_EXT]


def exif_info(data):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        date = (im.getexif() or {}).get(36867) or (im.getexif() or {}).get(306) or ""
        return im.width, im.height, str(date)
    except Exception:
        return "", "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("--out", default="photos")
    a = ap.parse_args()
    src = Path(a.input)
    if src.is_dir():
        items = from_folder(src)
    elif src.suffix.lower() == ".docx":
        items = from_docx(src)
    elif src.suffix.lower() == ".pdf":
        items = from_pdf(src)
    elif src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp()); zipfile.ZipFile(src).extractall(tmp); items = from_folder(tmp)
    else:
        sys.exit(f"Unsupported input: {src}")

    out = Path(a.out); (out / "source").mkdir(parents=True, exist_ok=True)
    index = out / "photo_index.csv"
    rows = list(csv.DictReader(open(index))) if index.exists() else []
    extra = [k for r in rows[:1] for k in r if k not in FIELDS]   # keep any columns added by hand
    fields = FIELDS + extra
    seen = {r["source_file"] + "::" + r["source_position"] for r in rows}
    n = max([int(r["id"][1:]) for r in rows] or [0])
    added = 0
    for ext, data, pos, near in items:
        key = f"{src.name}::{pos}"
        if key in seen:
            continue
        n += 1; added += 1
        pid = f"P{n:03d}"
        (out / "source" / f"{pid}{ext}").write_bytes(data)
        w, h, d = exif_info(data)
        row = {k: "" for k in fields}
        row.update(id=pid, source_file=src.name, source_position=pos, original_caption=near,
                   px_width=w, px_height=h, exif_date=d, status="extracted")
        rows.append(row)
    with open(index, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, restval=""); wr.writeheader(); wr.writerows(rows)
    print(f"{added} new photos; {len(rows)} total in {index}. Fill `kind` for each (photograph, illustration or map).")


if __name__ == "__main__":
    main()
