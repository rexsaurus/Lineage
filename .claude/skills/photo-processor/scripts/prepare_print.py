#!/usr/bin/env python3
"""Make print copies of photos: photos/source/P001.* -> photos/print/P001.jpg

Only safe, reversible adjustments: EXIF orientation, colour -> sRGB or grayscale,
optional crop box, 300 ppi tag. Never upscales, sharpens, colourises or "restores".
Updates print_file and max_print_width_in in photos/photo_index.csv.

Usage: prepare_print.py [--color bw|color] [--only P001,P002] [--crop P001=l,t,r,b]
"""
import argparse, csv
from pathlib import Path
from PIL import Image, ImageOps

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", default="bw"); ap.add_argument("--only", default="")
    ap.add_argument("--crop", action="append", default=[], help="P001=left,top,right,bottom px")
    ap.add_argument("--dir", default="photos")
    a = ap.parse_args()
    root = Path(a.dir); (root / "print").mkdir(exist_ok=True)
    crops = {c.split("=")[0]: tuple(int(v) for v in c.split("=")[1].split(",")) for c in a.crop}
    only = set(filter(None, a.only.split(",")))
    index = root / "photo_index.csv"
    rows = list(csv.DictReader(open(index))); fields = list(rows[0].keys()) if rows else []
    for r in rows:
        pid = r["id"]
        if only and pid not in only:
            continue
        src = next((root / "source").glob(pid + ".*"), None)
        if not src:
            print(f"{pid}: source missing"); continue
        im = ImageOps.exif_transpose(Image.open(src))
        if pid in crops:
            im = im.crop(crops[pid])
        im = im.convert("L") if a.color == "bw" else im.convert("RGB")
        out = root / "print" / f"{pid}.jpg"
        im.save(out, quality=95, dpi=(300, 300), subsampling=0)
        r["print_file"] = f"/{out.as_posix()}"
        r["max_print_width_in"] = f"{im.width / 300:.2f}"
        if im.width / 300 < 2.5 and "low-res" not in r.get("needs_attention", ""):
            r["needs_attention"] = (r.get("needs_attention", "") + " low-res: better scan wanted").strip()
        # 300 ppi at printed size is the target; 200 ppi (width / 200 in) is the hard floor.
        print(f"{pid}: {im.width}x{im.height}px -> max {im.width/300:.2f} in wide at 300 ppi")
    with open(index, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    main()
