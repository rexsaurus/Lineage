#!/usr/bin/env python3
"""Classical digital restoration of real photographs. Nothing is generated, so faces and details stay the
photograph's own: dust and scratch specks inpainted, noise reduced (non-local means), contrast evened (CLAHE),
levels set, a gentle unsharp mask. Printed halftones (newspaper or yearbook pictures) are descreened instead.

    python restore_photos.py --project DIR photos/print/P014.jpg [...]      # needs opencv-python-headless, numpy
    python restore_photos.py --project DIR --halftone photos/print/P020.jpg

Each original is kept untouched at <dir>/_orig/<name> (made once, never overwritten); the restored image takes the
original's place, so the stories print it. Restoring again always starts from the _orig/ copy. Every run is logged
in data/image_restorations.json ({path: {orig, model, prompt, date}}); r2_sync.py files the result under
restorations/ and the _orig/ copy under originals/.
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402


def descreen(cv2, np, img):
    """Printed halftones: dissolve the dot screen instead of sharpening it."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if g.shape[1] < 1400:
        f = 1400 / g.shape[1]
        g = cv2.resize(g, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    out = cv2.GaussianBlur(g, (0, 0), 2.2)
    out = cv2.bilateralFilter(out, 9, 25, 7)
    out = cv2.createCLAHE(clipLimit=1.3, tileGridSize=(8, 8)).apply(out)
    bl = cv2.GaussianBlur(out, (0, 0), 3)
    out = cv2.addWeighted(out, 1.35, bl, -0.35, 0)
    lo, hi = np.percentile(out, 0.5), np.percentile(out, 99.6)
    return np.clip((out.astype(np.float32) - lo) * 255 / max(hi - lo, 1), 0, 255).astype(np.uint8), 0, 0.0, True


def restore(cv2, np, img):
    mono = img.ndim == 2 or (np.abs(img[..., 0].astype(int) - img[..., 1]).mean() < 3
                             and np.abs(img[..., 1].astype(int) - img[..., 2]).mean() < 3)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    if g.shape[1] < 1400:                                   # small scans: enlarge so cleanup works at detail scale
        f = 1400 / g.shape[1]
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    med = cv2.medianBlur(g, 5)                              # dust and scratches: small specks unlike their surroundings
    diff = cv2.absdiff(g, med)
    thr = max(18, np.percentile(diff, 99.6))
    mask = (diff > thr).astype(np.uint8) * 255
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] <= 40:
            keep[lab == i] = 255
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
    sigma = float(np.median(np.abs(g.astype(float) - cv2.GaussianBlur(g, (0, 0), 1.5)))) * 1.48
    h = float(np.clip(sigma * 1.2, 4, 12))
    if mono:
        out = cv2.inpaint(g, keep, 3, cv2.INPAINT_TELEA)
        out = cv2.fastNlMeansDenoising(out, None, h=h, templateWindowSize=7, searchWindowSize=21)
        out = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(out)
        bl = cv2.GaussianBlur(out, (0, 0), 1.6)
        out = cv2.addWeighted(out, 1.55, bl, -0.55, 0)
        lo, hi = np.percentile(out, 0.4), np.percentile(out, 99.7)
        out = np.clip((out.astype(np.float32) - lo) * 255 / max(hi - lo, 1), 0, 255).astype(np.uint8)
    else:
        out = cv2.inpaint(img, keep, 3, cv2.INPAINT_TELEA)
        out = cv2.fastNlMeansDenoisingColored(out, None, h, h, 7, 21)
        lab_ = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
        lab_[..., 0] = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(lab_[..., 0])
        out = cv2.cvtColor(lab_, cv2.COLOR_LAB2BGR)
        bl = cv2.GaussianBlur(out, (0, 0), 1.6)
        out = cv2.addWeighted(out, 1.5, bl, -0.5, 0)
    return out, int((keep > 0).sum()), round(h, 1), mono


def main():
    ap = argparse.ArgumentParser(description="classical photo restoration; originals kept in _orig/")
    add_project_arg(ap)
    ap.add_argument("--halftone", action="store_true", help="descreen printed halftones instead")
    ap.add_argument("images", nargs="+", help="project-relative image paths")
    a = ap.parse_args()
    enter_project(a.project)
    try:
        import cv2
        import numpy as np
    except ImportError:
        sys.exit("needs OpenCV and numpy: pip install opencv-python-headless numpy")
    log_p = Path("data/image_restorations.json")
    log = json.loads(log_p.read_text()) if log_p.exists() else {}
    for rel in a.images:
        p = Path(rel)
        if not p.is_file():
            print("skip (not found)", rel)
            continue
        orig = p.parent / "_orig" / p.name
        if not orig.exists():
            orig.parent.mkdir(exist_ok=True)
            shutil.copy2(p, orig)                            # the raw file, untouched
        img = cv2.imread(str(orig), cv2.IMREAD_COLOR)
        if img is None:
            print("skip (unreadable)", rel)
            continue
        out, specks, h, mono = descreen(cv2, np, img) if a.halftone else restore(cv2, np, img)
        params = [cv2.IMWRITE_JPEG_QUALITY, 92] if p.suffix.lower() in (".jpg", ".jpeg") else []
        cv2.imwrite(str(p), out, params)
        model = ("classical (OpenCV): halftone descreen, bilateral, CLAHE 1.3, light unsharp" if a.halftone else
                 "classical (OpenCV): speck inpainting, NL-means denoise (h=%s), CLAHE 1.5, unsharp, levels%s"
                 % (h, "; mono" if mono else ""))
        log[p.as_posix()] = {"orig": orig.as_posix(), "model": model, "prompt": "", "date": date.today().isoformat()}
        print(f"restored {rel}  ({specks} speck px, h={h}, {'mono' if mono else 'colour'})")
    log_p.parent.mkdir(exist_ok=True)
    log_p.write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
