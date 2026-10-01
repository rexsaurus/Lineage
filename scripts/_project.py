"""Shared helpers for the BookAssembler scripts. Not run directly.

Every script runs with a book PROJECT folder as the working directory (or is
given --project DIR). Nothing here ever works out the project from where the
script file lives: the scripts live in the BookAssembler checkout, the book
lives somewhere else.
"""
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

AUDIO_EXTS = {".wav", ".m4a", ".mp3", ".aac", ".flac", ".aiff", ".aif", ".ogg",
              ".opus", ".wma", ".mp4", ".mov"}
SESSIONS_CSV = Path("transcript/sessions.csv")
SESSION_COLS = ["session", "file", "recorded", "duration"]


def add_project_arg(ap):
    ap.add_argument("--project", default=".",
                    help="book project folder (default: the current directory)")


def enter_project(path="."):
    """chdir into the project folder and return it as an absolute Path."""
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        sys.exit(f"project folder not found: {p}")
    os.chdir(p)
    if not Path("book.yaml").exists():
        print(f"warning: no book.yaml in {p} -- is this a book project folder?",
              file=sys.stderr)
    return p


def load_book():
    """book.yaml as a dict ({} if missing). Requires pyyaml."""
    p = Path("book.yaml")
    if not p.exists():
        return {}
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is not installed; run `make install` in the BookAssembler "
                 "checkout and use $BOOKASSEMBLER/.venv/bin/python")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def labels(book=None):
    """(narrator_label, interviewer_label) from book.yaml, with neutral defaults."""
    book = load_book() if book is None else book
    n = (book.get("narrator") or {}).get("label") or "Narrator"
    i = (book.get("interviewer") or {}).get("label") or "Interviewer"
    return n, i


def subject_names(book=None):
    """Every name the subject may be called in the prose."""
    book = load_book() if book is None else book
    out = []
    nar = book.get("narrator") or {}
    for v in (nar.get("name"), nar.get("label"),
              (book.get("narration") or {}).get("subject_name")):
        if v and v not in out:
            out.append(str(v))
    return out


def transcription_locked(book=None):
    book = load_book() if book is None else book
    return bool(book.get("transcription_locked"))


def speaker_bounds(book=None):
    """(min, max) speakers: narrator + interviewer + other_speakers, env-overridable."""
    book = load_book() if book is None else book
    n = 2 + len(book.get("other_speakers") or [])
    return (int(os.environ.get("MIN_SPEAKERS", n)), int(os.environ.get("MAX_SPEAKERS", n)))


def session_key(sid):
    """Natural sort: S2 before S10."""
    m = re.match(r"([A-Za-z]*)(\d+)$", sid)
    return (m.group(1), int(m.group(2))) if m else (sid, 0)


def secs(t):
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def hms(x):
    x = int(x or 0)
    return f"{x // 3600:02d}:{x % 3600 // 60:02d}:{x % 60:02d}"


def read_sessions():
    """Rows of transcript/sessions.csv in session order. Falls back to the
    session IDs found in transcript/raw/ if the CSV does not exist yet."""
    if SESSIONS_CSV.exists():
        with open(SESSIONS_CSV, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if (r.get("session") or "").strip()]
        return sorted(rows, key=lambda r: session_key(r["session"]))
    raw = sorted(Path("transcript/raw").glob("*.json"), key=lambda p: session_key(p.stem))
    return [dict(session=p.stem, file="", recorded="", duration="") for p in raw]


def write_sessions(rows):
    SESSIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    tmp = SESSIONS_CSV.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SESSION_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: session_key(r["session"])))
    tmp.replace(SESSIONS_CSV)


def probe(path):
    """(duration_seconds, creation_date 'YYYY-MM-DD' or '') via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:format_tags=creation_time", "-of", "json", str(path)],
            capture_output=True, text=True, check=True).stdout
        fmt = json.loads(out).get("format", {})
        dur = float(fmt.get("duration") or 0)
        created = (fmt.get("tags") or {}).get("creation_time", "")[:10]
        return dur, created
    except Exception:
        return 0.0, ""


def audio_files(audio_dir=Path("audio")):
    return sorted((p for p in audio_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXTS
                   and not p.name.startswith(("._", "."))),
                  key=lambda p: [int(t) if t.isdigit() else t.lower()
                                 for t in re.split(r"(\d+)", p.name)])
