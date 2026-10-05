#!/usr/bin/env python3
"""Generate the illustrations a project has planned, in a consistent period style.

    python $LINEAGE/scripts/generate_images.py                 # every planned image not yet made
    python $LINEAGE/scripts/generate_images.py IMG-03-1 IMG-03-2
    python $LINEAGE/scripts/generate_images.py --dry-run       # print the full prompts, call nothing
    python $LINEAGE/scripts/generate_images.py --force IMG-03-1  # make it again (the old file is kept)

Run from the project folder (or --project DIR). Reads photos/images-plan.yaml:

    model: gpt-image-1            # optional; the OpenAI image model
    quality: high                 # optional
    lock: "No text, no caption, no watermark."     # appended to EVERY prompt (IMAGE-STYLE.md)
    styles:                       # period presets: the look, never the people
      ww1: "Authentic First World War photograph, 1916-1917: true black-and-white
            silver-gelatin print, fine grain, faded midtones. Photorealistic, NOT illustration."
      forties: "Documentary photograph, 1940s snapshot, vintage black-and-white print."
    likeness:                     # optional: reference photographs that lock a face
      grandfather:
        refs: photos/reference/grandfather/*.png   # real photos, used only as references
        describe: "heavy straight brows, deep-set eyes, square jaw"
    images:
      - id: IMG-03-1
        size: 1536x1024           # 1024x1024 | 1536x1024 | 1024x1536
        style: forties
        likeness: grandfather     # optional; runs the model in edit mode with the refs
        prompt: "Winter 1946, a back porch at night ..."
        scene: "[S2 01:41:30]"    # where the material describes this scene (required)

Writes photos/generated/<id>.png (the original, never edited) and a grayscale print copy
photos/generated/print/<id>.jpg (Pillow), and appends nothing to photo_index.csv: index each
result yourself as kind: illustration, with rendering_basis = the scene citation plus the
style and likeness used (photo-processor §4). Every result is an ILLUSTRATION: the book says
so in the chapter's note and in the front-matter line.

The key comes from OPENAI_API_KEY, or from ~/.openai_api_key (a file outside every repo,
chmod 600). It is never printed, logged or written anywhere by this script. Nothing else
leaves the machine but the prompt and, with a likeness, the reference images.
"""
import argparse
import base64
import glob
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

API = "https://api.openai.com/v1/images/"
PLAN = Path("photos/images-plan.yaml")
OUT = Path("photos/generated")


def api_key():
    k = os.environ.get("OPENAI_API_KEY")
    if k:
        return k.strip()
    p = Path("~/.openai_api_key").expanduser()
    if p.exists():
        mode = p.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            print(f"warning: {p} is readable by other users; run: chmod 600 {p}", file=sys.stderr)
        return p.read_text().strip()
    sys.exit("No OpenAI key: set OPENAI_API_KEY for this command, or keep it in ~/.openai_api_key "
             "(chmod 600, outside every repo). Never put it in the project.")


def full_prompt(plan, img):
    style = (plan.get("styles") or {}).get(img.get("style"), "") if img.get("style") else ""
    if img.get("style") and not style:
        sys.exit(f"{img['id']}: unknown style {img['style']!r}")
    like = ""
    if img.get("likeness"):
        L = (plan.get("likeness") or {}).get(img["likeness"])
        if not L:
            sys.exit(f"{img['id']}: unknown likeness {img['likeness']!r}")
        like = ("The face derives from the reference photographs: " + L.get("describe", "")).strip().rstrip(".") + ". "
    parts = [style.strip(), like.strip(), str(img["prompt"]).strip(), str(plan.get("lock", "")).strip()]
    return " ".join(p for p in parts if p)


def refs_for(plan, img):
    if not img.get("likeness"):
        return []
    pattern = (plan["likeness"][img["likeness"]] or {}).get("refs", "")
    return [Path(f) for f in sorted(glob.glob(pattern))][:16]


def call(endpoint, fields, files, key):
    if not files:
        body = json.dumps({**fields, "n": 1}).encode()
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    else:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in {**fields, "n": "1"}.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for f in files:
            mime = "image/png" if f.suffix.lower() == ".png" else "image/jpeg"
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="{f.name}"\r\n'
                     f"Content-Type: {mime}\r\n\r\n").encode() + f.read_bytes() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers = {"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    req = urllib.request.Request(API + endpoint, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def print_copy(png, jpg):
    from PIL import Image, ImageOps
    jpg.parent.mkdir(parents=True, exist_ok=True)
    ImageOps.grayscale(Image.open(png)).save(jpg, "JPEG", quality=92, dpi=(300, 300))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="image ids from the plan (default: all not yet made)")
    P.add_project_arg(ap)
    ap.add_argument("--plan", default=str(PLAN))
    ap.add_argument("--dry-run", action="store_true", help="print prompts; call nothing")
    ap.add_argument("--force", action="store_true", help="make again; the old file is renamed, not deleted")
    a = ap.parse_args()
    P.enter_project(a.project)
    if not Path(a.plan).exists():
        sys.exit(f"no {a.plan}: plan the images first (photo-processor §4)")
    plan = yaml.safe_load(open(a.plan)) or {}
    images = {i["id"]: i for i in plan.get("images") or []}
    for i in images.values():
        if not i.get("scene"):
            sys.exit(f"{i['id']}: no 'scene' citation. An illustration depicts a scene the material describes.")
    ids = a.ids or list(images)
    unknown = [i for i in ids if i not in images]
    if unknown:
        sys.exit(f"not in the plan: {', '.join(unknown)}")
    key = None if a.dry_run else api_key()
    for i in ids:
        img, png = images[i], OUT / f"{i}.png"
        prompt, refs = full_prompt(plan, img), refs_for(plan, img)
        if a.dry_run:
            print(f"--- {i} ({img.get('size', '1024x1024')}, {'edit with ' + str(len(refs)) + ' refs' if refs else 'text only'})\n{prompt}\n")
            continue
        if png.exists() and not a.force:
            print(f"skip {i} (exists)")
            continue
        if png.exists():
            png.rename(png.with_name(f"{i}.{time.strftime('%Y%m%d-%H%M%S')}.png"))
        if img.get("likeness") and not refs:
            print(f"warning: {i}: no reference photographs match; generating from text only", file=sys.stderr)
        fields = {"model": plan.get("model", "gpt-image-1"), "prompt": prompt,
                  "size": img.get("size", "1024x1024"), "quality": plan.get("quality", "high")}
        try:
            data = call("edits" if refs else "generations", fields, refs, key)
        except urllib.error.HTTPError as e:
            print(f"FAIL {i}: HTTP {e.code} {e.read()[:300]!r}")
            continue
        OUT.mkdir(parents=True, exist_ok=True)
        png.write_bytes(base64.b64decode(data["data"][0]["b64_json"]))
        print_copy(png, OUT / "print" / f"{i}.jpg")
        print(f"ok {i} ({'edit with ' + str(len(refs)) + ' refs' if refs else 'text only'}) -> {png}")
        time.sleep(2)


if __name__ == "__main__":
    main()
