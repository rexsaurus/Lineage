#!/usr/bin/env python3
"""Where the face is in each picture, so round portraits and cropped cards on a published site centre on it.

    python face_focus.py --project DIR        # needs opencv-python-headless

Reads data/r2_manifest.csv (r2_sync.py) and writes data/image_focus.json: {project path: "x% y%"} for every image
in which a face is found (OpenCV Haar cascades, frontal then profile); the largest face wins, aimed a little above
its centre for headroom. Images without a face are left out (the site falls back to a top-weighted crop).
Already-checked files are remembered by path and content hash under "_seen", so a rerun only looks at new or
changed pictures. site/build_instance.py --assets reads the file from beside the manifest.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _project import add_project_arg, enter_project  # noqa: E402


def cascades(cv2):
    return [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
            ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml", "haarcascade_profileface.xml")]


def focus(cv2, cs, path):
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    h, w = img.shape
    s = 800 / max(h, w) if max(h, w) > 800 else 1.0
    g = cv2.equalizeHist(cv2.resize(img, None, fx=s, fy=s) if s != 1 else img)
    mins = max(16, int(min(g.shape) * 0.06))
    for c in cs:
        faces = c.detectMultiScale(g, scaleFactor=1.08, minNeighbors=6, minSize=(mins, mins))
        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            cx, cy = (x + fw / 2) / g.shape[1], (y + fh * 0.42) / g.shape[0]
            return f"{cx * 100:.0f}% {cy * 100:.0f}%"
    return None


def main():
    ap = argparse.ArgumentParser(description="face focus points for cropped pictures")
    add_project_arg(ap)
    a = ap.parse_args()
    enter_project(a.project)
    man = Path("data/r2_manifest.csv")
    if not man.exists():
        print("no data/r2_manifest.csv yet (run r2_sync.py first): skipping face focus")
        return
    try:
        import cv2
    except ImportError:
        print("OpenCV is not installed (pip install opencv-python-headless): skipping face focus")
        return
    cs = cascades(cv2)
    out_p = Path("data/image_focus.json")
    out = json.loads(out_p.read_text()) if out_p.exists() else {}
    n = 0
    for r in csv.DictReader(open(man, encoding="utf-8")):
        if r.get("category") not in ("originals", "restorations", "illustrations"):
            continue
        p = Path(r["path"])
        if not p.is_file():
            continue
        key = r["path"] + "@" + (r.get("sha256") or "")[:12]
        if key in out.get("_seen", {}):
            continue
        f = focus(cv2, cs, p)
        out.setdefault("_seen", {})[key] = 1
        if f:
            out[r["path"]] = f
            n += 1
    out_p.write_text(json.dumps(out, indent=0, sort_keys=True))
    print(f"faces: {n} new focus points; {sum(1 for k in out if not k.startswith('_'))} images with a face")


if __name__ == "__main__":
    main()
