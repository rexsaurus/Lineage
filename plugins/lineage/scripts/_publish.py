"""Publish settings for the site/publish scripts. Not run directly.

A project's publish settings live in its lineage.json, under "settings" -> "publish":

    {
      "settings": {
        "publish": {
          "site_url": "https://family.example.org",   # no default: SEO pages and absolute links need it
          "title": "The Book of the Family",           # default: lineage.json "title", then book.yaml title
          "subtitle": "An oral history",              # default: settings.subtitle, then book.yaml subtitle
          "author": "A. Compiler",                     # default: book.yaml interviewer.name
          "chapters_dir": "output/chapters",           # where chapter_pdfs.py writes one PDF per story
          "book_entry": "book/main.typ",               # the Typst file the whole-book edition compiles
          "chapter_entry": "",                         # optional Typst wrapper for one chapter (see chapter_pdfs.py)
          "image": "",                                 # absolute URL of the default share (Open Graph) image
          "app_path": "/lineage/",                     # where the dashboard snapshot is published on the site
          "include_living": false,                     # SEO pages for people marked living (default: none)
          "hidden_aliases": [],                        # aliases never printed on public pages (nicknames)
          "changelog_commit_messages": false,          # list the project's commit messages on /changelog/
          "posts_dir": "posts",                        # news posts (posts/*.md) published under /updates/<slug>/
          "digest": {                                  # the weekly email digest (api/digest.js); off until configured
            "sender_line": "",                         # who sends it and why the reader gets it (footer of every email)
            "postal_address": "",                      # postal address for the footer (or env DIGEST_POSTAL_ADDRESS)
            "schedule": "0 15 * * 1"                   # Vercel cron, UTC (default: Mondays 15:00)
          },
          "r2": {
            "env_file": "~/.config/lineage/r2.env",    # R2 credentials (never in git)
            "prefix": "<slug of the title>",           # key prefix inside the bucket
            "scan": ["photos", "sources", "output/chapters"],
            "extra_documents": [{"path": "records/x.pdf", "key": "records/x.pdf"}],   # key is under <prefix>/
            "illustration_globs": [],                  # extra project-relative globs that are illustrations
            "skip": []                                 # path fragments never uploaded, e.g. "/private/"
          }
        }
      }
    }

Every key is optional. A script that needs a value that is missing says so and skips that step;
nothing here raises on a missing or partial block.
"""
import json
import os
import re
from pathlib import Path

DEFAULTS = {
    "site_url": "",
    "title": "",
    "subtitle": "",
    "author": "",
    "chapters_dir": "output/chapters",
    "book_entry": "",
    "chapter_entry": "",
    "image": "",
    "app_path": "/lineage/",
    "include_living": False,
    "hidden_aliases": [],
    "changelog_commit_messages": False,
    "posts_dir": "posts",
    "digest": {
        "sender_line": "",
        "postal_address": "",
        "schedule": "0 15 * * 1",
    },
    "r2": {
        "env_file": "~/.config/lineage/r2.env",
        "prefix": "",
        "scan": ["photos", "sources", "output/chapters"],
        "extra_documents": [],
        "illustration_globs": [],
        "skip": [],
    },
}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _book_yaml(root):
    p = Path(root) / "book.yaml"
    if not p.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def lineage_json(root="."):
    p = Path(root) / "lineage.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        return {}


def settings(root="."):
    """The publish settings with every default filled in (see the module docstring)."""
    lj = lineage_json(root)
    st = lj.get("settings") or {}
    pub = st.get("publish") or {}
    by = _book_yaml(root)
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS.items()}
    for k, v in pub.items():
        if k in ("r2", "digest") and isinstance(v, dict):
            out[k].update({a: b for a, b in v.items() if b not in (None, "")})
        elif k not in ("r2", "digest") and v not in (None, ""):
            out[k] = v
    out["site_url"] = (out["site_url"] or "").rstrip("/")
    out["title"] = out["title"] or lj.get("title") or by.get("title") or ""
    out["subtitle"] = out["subtitle"] or st.get("subtitle") or by.get("subtitle") or ""
    out["author"] = out["author"] or ((by.get("interviewer") or {}).get("name")) or ""
    out["slug"] = slug(out["title"]) or "book"
    out["r2"]["prefix"] = (out["r2"]["prefix"] or out["slug"]).strip("/")
    out["r2"]["env_file"] = str(Path(out["r2"]["env_file"]).expanduser())
    if not out["book_entry"] and (Path(root) / "book" / "main.typ").exists():
        out["book_entry"] = "book/main.typ"
    return out


def lineage_home():
    """The Lineage checkout (the folder holding app/ and plugins/), from this script's location."""
    here = Path(__file__).resolve().parent            # plugins/lineage/scripts
    for cand in (here.parent.parent.parent, Path(os.environ.get("LINEAGE", "")) if os.environ.get("LINEAGE") else None):
        if cand and (cand / "app").is_dir():
            return cand
    return here.parent.parent.parent


def book_template():
    """Lineage's book template (book/template.typ) and the fonts folder, or (None, None)."""
    home = lineage_home()
    for d in (home / "plugins" / "lineage", home):
        if (d / "book" / "template.typ").exists():
            fonts = d / "fonts" if (d / "fonts").is_dir() else (home / "fonts" if (home / "fonts").is_dir() else None)
            return d / "book" / "template.typ", fonts
    return None, None


def version(root="."):
    p = Path(root) / "VERSION"
    return p.read_text().strip() if p.exists() else ""


def gs_compress(src, out):
    """Ghostscript /ebook, 150 dpi images: the web/Drive/email edition. Returns True on success."""
    import shutil
    import subprocess
    if not shutil.which("gs"):
        return False
    r = subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
                        "-dPDFSETTINGS=/ebook", "-dColorImageResolution=150", "-dGrayImageResolution=150",
                        "-dDetectDuplicateImages=true", f"-sOutputFile={out}", str(src)], capture_output=True, text=True)
    return r.returncode == 0 and Path(out).exists()
