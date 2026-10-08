#!/usr/bin/env python3
"""Lineage — a local dashboard for a family's own record: sources, research, genealogy, timeline,
Familypedia, and stories and a book as exports.

    python3 server.py                                   # http://127.0.0.1:8777
    python3 server.py --port 9000 --project ~/books/grandma
    python3 server.py --command bash --cwd ~/books/grandma   # terminal override

Everything stays on this machine. API keys live in ~/.lineage/config.json (chmod 600),
sources and output in the project folder. The server binds to 127.0.0.1 only; there is no
option to change that.

The file has three layers:

  ENGINE              what the book pipeline knows: sources, pages, approvals, stage jobs.
                      Plain vocabulary, no dashboard terms, so a simpler front end can use
                      the same /api/engine/* calls later.
  AUTHOR-ONLY SURFACE terminal, paths and keys, connectors. Powerful and technical; kept
                      together so a non-technical face can leave it out entirely.
  HTTP                routing, the session token, static files.

Stages that need a model are PROTOTYPE: they write realistic artifacts on a timed job and
leave a clearly named hook where the Lineage skills get wired in.
"""
import argparse, base64, csv, fcntl, hashlib, http.server, json, mimetypes, os, pty, queue, re
import random, secrets, shlex, shutil, signal, socketserver, struct, subprocess, termios, threading, time
import urllib.error, urllib.parse, urllib.request, uuid, warnings
from html import escape as html_escape, unescape as html_unescape
from datetime import datetime, timezone
from pathlib import Path
import sys

warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*fork.*")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import familypedia  # noqa: E402  (the Familypedia engine; reads helpers from this module)
familypedia.HOST = sys.modules[__name__]
STATIC = HERE / "static"
CONFIG_DIR = Path.home() / ".lineage"
CONFIG_FILE = CONFIG_DIR / "config.json"
GOOGLE_TOKEN_FILE = CONFIG_DIR / "google_token.json"
TOKEN = secrets.token_urlsafe(32)          # minted at start, injected into index.html
PORT = 8777
DEMO = False   # --demo: invented sample results for development, with a banner. Never the default.

# =========================================================================================
# Shared vocabulary for the style choices (used by the engine and shown by the dashboard)
# =========================================================================================
CHAPTER_TEMPLATES = [
    {"id": "ancestor", "name": "Ancestor chapter",
     "blurb": "One relative per chapter. Says what kind of story it is, carries a line of descent, ends with THE RECORDS.",
     "sections": ["Opening: what kind of story this is", "Line of descent", "What was witnessed",
                  "What was told", "Family lore", "The records", "The photographs"]},
    {"id": "life-stage", "name": "Life stage",
     "blurb": "Childhood, college, the move west. Stories in order, joined by narration, opening on a concrete moment.",
     "sections": ["Place and years", "Opening scene", "Stories in order", "Section breaks", "Closing paragraph"]},
    {"id": "theme", "name": "Theme across a life",
     "blurb": "One thread — a trade, a faith, a friendship, a place — followed across decades.",
     "sections": ["The thread", "First appearance", "Turns, by year", "What became of it"]},
    {"id": "album", "name": "Photo album",
     "blurb": "Photographs with evidence-coded captions and little text.",
     "sections": ["Plates", "Captions with their evidence", "What is documented", "What is inferred"]},
]

NARRATIVE_STYLES = [
    {"id": "biographer", "name": "Biographer",
     "blurb": "Third person, past tense, written about them. Their words quoted exactly. The house style."},
    {"id": "as-told-to", "name": "As told to",
     "blurb": "First person, in their voice, lightly edited. Reads like them talking."},
    {"id": "documentary", "name": "Documentary",
     "blurb": "Third person, spare and factual, records foregrounded. Good for research-heavy chapters."},
    {"id": "letter", "name": "Letter to the grandchildren",
     "blurb": "Addressed to the family who will read it. Warmest; use sparingly."},
]

# One passage, four voices — from the invented sample project, so the difference is visible.
VOICE_SAMPLES = {
    "biographer": 'When she was seven or eight, as best she remembered, Ruth walked her father\'s lunch down to the ore dock in a tin pail. The dock was so tall "you had to tip your head all the way back," and the trains ran right out on top of it. Whether it frightened her, she never quite settled: "No. Well, yeah. A little."',
    "as-told-to": "When I was little, maybe seven or eight, I'd walk my dad's lunch down to the ore dock. A tin pail. And the dock was so tall you had to tip your head all the way back. Was I scared of it? No. Well, yeah. A little.",
    "documentary": 'Around 1945 (she gave her age as "maybe seven or eight"), Ruth carried her father\'s lunch to the Duluth ore dock. She described the structure as so tall "you had to tip your head all the way back," with trains running along its top. No photograph of the visit is known.',
    "letter": "You never saw the ore dock, and I only saw it with my head tipped all the way back. I carried your great-great-grandfather's lunch down to it in a tin pail when I was seven or eight. Was I scared? A little. I'll admit that much now.",
}

PHOTO_STYLES = [
    {"id": "tintype", "name": "Tintype", "blurb": "1850s–70s. Plate edges, shallow focus, slight silver bloom."},
    {"id": "silver", "name": "Silver gelatin", "blurb": "1890s–1940s. Grey scale, fine grain, studio lighting."},
    {"id": "kodachrome", "name": "Kodachrome", "blurb": "1950s–70s. Warm saturated color, soft contrast."},
    {"id": "polaroid", "name": "Instant print", "blurb": "1970s–80s. Square, cool cast, soft corners."},
    {"id": "line", "name": "Pen and ink", "blurb": "Drawn, not photographic. Never mistaken for a record."},
]

WRITING_OPTIONS = {
    "quote_density": [("sparse", "Sparse — a quote every few pages"), ("standard", "Standard — one or two a page"),
                      ("rich", "Rich — let them talk")],
    "ornament": [("❧", "❧  fleuron"), ("* * *", "* * *  asterisks"), ("⁂", "⁂  asterism"), ("—", "—  a rule")],
    "opener": [("dropcap", "Red drop cap, opening words in small caps"), ("smallcaps", "Small caps only"),
               ("plain", "Plain")],
}

TRIMS = ["6x9", "7x10", "8x10", "8.5x11"]
PRINTERS = ["kdp", "ingramspark", "lulu", "blurb"]

STAGES = [
    ("setup", "Settings"), ("sources", "Sources"), ("research", "Public records"),
    ("genealogy", "Genealogy"), ("chapters", "Chapter map"), ("style", "Style"),
    ("generate", "Chapters"), ("podcast", "Podcast"),
]

DEFAULT_SETTINGS = {
    "narrative_style": "biographer", "chapter_template": "ancestor", "photo_style": "silver",
    "quote_density": "standard", "ornament": "❧", "bridges_in_drafts": True, "opener": "dropcap",
    "trim": "7x10", "printer": "kdp", "drive_folder": "", "sync_sources": False, "sync_outputs": False,
    "terminal_command": "", "terminal_cwd": "", "voice_id": "", "voice_name": "",
    "family_name": "", "subtitle": "", "summary": "", "subject_short": "", "covers_override": "",
    "crest_mode": "none", "crest_show": False,
    "crest_surfaces": {"header": True, "familypedia": True, "title_page": True, "exports": True, "invitations": True},
}
# Changing these marks the pages built from them stale (never rewritten silently).
IDENTITY_DEPENDENTS = {"title": ["title page", "introduction draft", "Familypedia front page"],
                       "summary": ["introduction draft", "Familypedia front page"],
                       "family_name": ["Familypedia front page", "records appendix"]}


# ---------------------------------------------------------------- config (machine level)
def load_config():
    cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    cfg.setdefault("keys", {})
    cfg.setdefault("google", {})
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    os.chmod(CONFIG_FILE, 0o600)


def mask(key):
    return (key[:7] + "…" + key[-4:]) if key and len(key) > 14 else ("set" if key else "")


# ---------------------------------------------------------------- project (book level)
class Project:
    """The book folder. Settings and stage status live in <project>/lineage.json."""
    LAYOUT = ("sources", "transcript", "content/units", "data", "chapters", "photos/print", "output", ".lineage")

    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        for sub in self.LAYOUT:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.state_file = self.root / "lineage.json"
        self.lock = threading.Lock()
        if not self.state_file.exists():
            self.write({"title": "", "subject": "", "stages": {k: "todo" for k, _ in STAGES},
                        "settings": dict(DEFAULT_SETTINGS), "artifacts": {}})

    def read(self):
        s = json.loads(self.state_file.read_text())
        s.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            s["settings"].setdefault(k, v)
        s.setdefault("stages", {k: "todo" for k, _ in STAGES})
        s.setdefault("artifacts", {})
        s.setdefault("title", "")
        s.setdefault("subject", "")
        return s

    def write(self, state):
        with self.lock:
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
            tmp.replace(self.state_file)
        return state

    def mark(self, stage, status, **artifacts):
        s = self.read()
        s["stages"][stage] = status
        s["artifacts"].update(artifacts)
        return self.write(s)

    def inside(self, rel):
        """Resolve a project-relative path; refuse anything outside the project."""
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError("outside the project")
        return p


# =========================================================================================
# ENGINE — sources, pages, approvals, stage jobs. No dashboard vocabulary in this section.
# =========================================================================================
KINDS = {
    "audio": {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".aiff", ".aif", ".opus"},
    "video": {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"},
    "image": {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".heic", ".webp", ".bmp"},
    "pdf": {".pdf"},
    "text": {".txt", ".md", ".rtf", ".doc", ".docx", ".csv", ".json", ".html", ".odt"},
}
_DURATIONS = {}


def kind_of(path):
    ext = Path(path).suffix.lower()
    return next((k for k, exts in KINDS.items() if ext in exts), "other")


def media_duration(path):
    """Seconds, via ffprobe if installed; None when unknown or ffprobe is missing."""
    key = (str(path), path.stat().st_mtime)
    if key in _DURATIONS:
        return _DURATIONS[key]
    dur = None
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=15)
            dur = round(float(out.stdout.strip()), 1) if out.stdout.strip() else None
        except Exception:
            dur = None
    _DURATIONS[key] = dur
    return dur


def session_map(project):
    """basename of a recording -> session id, from transcript/sessions.csv."""
    p = project.root / "transcript" / "sessions.csv"
    out = {}
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r.get("file") and r.get("session"):
                out[Path(r["file"]).name] = r["session"]
    return out


def drive_map(project):
    p = project.root / ".lineage" / "drive_map.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _texts(project, globs):
    for g in globs:
        for p in project.root.glob(g):
            if p.is_file():
                try:
                    yield p, p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue


def engine_sources(project):
    """Every source file with what the pipeline has done with it."""
    sessions = session_map(project)
    drive = drive_map(project)
    units = list(_texts(project, ["content/units/*.md"]))
    chapters = list(_texts(project, ["chapters/*.typ", "chapters/*.md"]))
    by_path = {r["path"]: r for r in intake_load(project).values() if not r.get("trashed")}
    rows = []
    for folder in ("sources", "audio"):
        d = project.root / folder
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            st = f.stat()
            kind = kind_of(f)
            sid = sessions.get(f.name)
            transcribed = bool(sid and (project.root / "transcript" / "clean" / f"{sid}.md").exists())
            if sid:
                n_units = sum(1 for _, t in units if f'"{sid} ' in t or f"[{sid} " in t)
                cited = sum(1 for _, t in chapters if f"[{sid} " in t)
            else:
                n_units = sum(1 for _, t in units if f.name in t)
                cited = sum(1 for _, t in chapters if f.name in t)
            if cited:
                status = f"cited in {cited} chapter{'s' if cited != 1 else ''}"
            elif n_units:
                status = "has units"
            elif transcribed:
                status = "transcribed"
            else:
                status = "unused"
            rel = f.relative_to(project.root).as_posix()
            ir = by_path.get(rel)
            eff = effective(ir) if ir else None
            rows.append({
                "rid": ir["id"] if ir else None, "indexed": bool(ir and (ir.get("stages") or {}).get("index", {}).get("state") == "done"),
                "stages": (ir or {}).get("stages", {}), "thumb": (ir or {}).get("thumb"),
                "display_name": (eff or {}).get("accepted_name") or f.name, "renamed": bool(eff and eff.get("accepted_name")),
                "summary": (eff or {}).get("summary") or "", "summary_by": (eff or {}).get("by", {}).get("summary"),
                "doc_kind": (eff or {}).get("doc_kind"), "content_date": (eff or {}).get("date_range") or "",
                "people": (eff or {}).get("people") or [], "added_by": (ir or {}).get("added_by", "me"),
                "transcription": (ir or {}).get("transcription"), "in_drive": bool((ir or {}).get("drive_id")),
                "notes": (ir or {}).get("notes", ""), "illustration": bool(ir and is_illustration(ir)),
                "places": (eff or {}).get("places") or [], "provenance": ((ir or {}).get("fields") or {}).get("provenance", ""),
                "id": rel, "name": f.name, "kind": kind, "bytes": st.st_size,
                "added": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "duration": media_duration(f) if kind in ("audio", "video") else None,
                "session": sid, "transcribed": transcribed, "units": n_units, "cited_in": cited,
                "status": status, "file_url": f.as_uri(),
                "drive_url": (ir or {}).get("drive_url") or (f"https://drive.google.com/file/d/{drive[f.name]}/view" if f.name in drive else None),
            })
    return rows


PARA = re.compile(r"^\*\*(?P<spk>[^*]+)\*\* \[(?P<sid>S\d+) (?P<ts>\d{2}:\d{2}:\d{2})\] (?P<text>.*)$")


def engine_source_detail(project, source_id):
    """A transcribed source's header, topic outline and timestamped paragraphs."""
    src = project.inside(source_id)
    sid = session_map(project).get(src.name)
    if not sid:
        return {"id": source_id, "transcribed": False, "kind": kind_of(src)}
    clean = project.root / "transcript" / "clean" / f"{sid}.md"
    if not clean.exists():
        return {"id": source_id, "session": sid, "transcribed": False, "kind": kind_of(src)}
    text = clean.read_text(encoding="utf-8")
    header = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, _, v = line.partition(":")
                header[k.strip()] = v.split("  #")[0].strip().strip('"')
    topics = []
    if "## Topics" in text:
        block = text.split("## Topics", 1)[1].split("\n**", 1)[0]
        for line in block.splitlines():
            t = re.match(r"^- (\d{2}:\d{2}:\d{2}) (.*)$", line.strip())
            if t:
                topics.append({"t": t.group(1), "title": t.group(2)})
    paras = []
    for line in text.splitlines():
        pm = PARA.match(line)
        if pm:
            h, mi, s = map(int, pm["ts"].split(":"))
            paras.append({"speaker": pm["spk"], "t": pm["ts"], "seconds": h * 3600 + mi * 60 + s,
                          "text": pm["text"][:160] + ("…" if len(pm["text"]) > 160 else "")})
    return {"id": source_id, "session": sid, "transcribed": True, "header": header,
            "topics": topics, "paragraphs": paras, "kind": kind_of(src)}


def engine_approvals(project):
    """Everything waiting on a human: bridges, REVIEW notes, proposed stages."""
    items = []
    for p, text in _texts(project, ["chapters/*.typ", "chapters/*.md", "content/units/*.md"]):
        rel = p.relative_to(project.root).as_posix()
        for i, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"#bridge\[(.*?)\]|⟦BRIDGE: (.*?)⟧|\[\[bridge [^:]+:\s*(.*?)\]\]", line):
                items.append({"kind": "bridge", "where": f"{rel}:{i}", "text": next(g for g in m.groups() if g)})
            if "// REVIEW:" in line:
                items.append({"kind": "review", "where": f"{rel}:{i}", "text": line.split("// REVIEW:", 1)[1].strip()})
        if rel.startswith("content/units/"):
            fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            if fm and re.search(r"^lead_in:[ \t]*\S", fm.group(1), re.M) and not re.search(r"^lead_in_approved:[ \t]*true", fm.group(1), re.M):
                lead = re.search(r"^lead_in:[ \t]*(.*)$", fm.group(1), re.M).group(1).strip().strip('"')
                items.append({"kind": "bridge", "where": rel, "text": lead})
    labels = dict(STAGES)
    for stage, status in project.read()["stages"].items():
        if status == "proposed":
            items.append({"kind": "decision", "where": stage, "text": f"{labels.get(stage, stage)} is proposed and waiting for approval"})
    return items


def engine_make_page(project, source_id):
    """Draft one page from one source: its own words, cited, nothing added. Returns the page path.
    PROTOTYPE hook: the shaped narrative comes from the content-separator skill; this writes the
    verbatim excerpt and citations that the shaping step starts from."""
    detail = engine_source_detail(project, source_id)
    src = project.inside(source_id)
    out = project.root / "data" / "pages" / f"{src.stem}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {src.stem}", "", f"_Draft page from `{source_id}`. Exact words only; nothing added._", ""]
    if detail.get("transcribed"):
        for p in detail["paragraphs"][:12]:
            lines += [f"> {p['text']}", f"> — {p['speaker']}, [{detail['session']} {p['t']}]", ""]
    else:
        lines += [f"This source has not been transcribed yet ({kind_of(src)}). Transcribe it, then make the page again."]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out.relative_to(project.root).as_posix()



# ---------------------------------------------------------------- source intake
# Every file runs ingest → extract → understand → index (→ Drive). Each stage writes to
# data/sources.json; a failed stage never loses the file. My edits (row["mine"]) always win and
# survive a re-scan. The original file is never modified or renamed on disk.
INTAKE_LOCK = threading.Lock()
INTAKE_STAGES = ("ingest", "extract", "understand", "index", "drive")
STRUCTURED = ("what", "who", "about", "provenance")
DOC_KINDS = ("letter", "photo", "illustration", "certificate", "record", "transcript", "recording", "notes", "other")
ILLUSTRATION = re.compile(r"\b(illustration|generated|artist'?s rendering|ai[- ]made|reconstruction)\b", re.I)


def is_illustration(row):
    """A generated or drawn picture, never a photograph of the real thing. It may illustrate a story; it is
    never anyone's portrait, and never counted as a photograph of them."""
    e = effective(row)
    if e.get("doc_kind") == "illustration":
        return True
    text = " ".join(str(x or "") for x in (e.get("summary"), e.get("accepted_name"), row.get("original_name"),
                                           (row.get("fields") or {}).get("what"), (row.get("fields") or {}).get("provenance")))
    return bool(ILLUSTRATION.search(text))
INTAKE_MODEL = "claude-haiku-4-5-20251001"


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _index_path(project):
    return project.root / "data" / "sources.json"


def intake_load(project):
    p = _index_path(project)
    return json.loads(p.read_text()) if p.exists() else {}


def intake_save_row(project, row):
    with INTAKE_LOCK:
        data = intake_load(project)
        data[row["id"]] = row
        tmp = _index_path(project).with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        tmp.replace(_index_path(project))


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def intake_find_hash(project, sha):
    return next((r for r in intake_load(project).values() if r.get("sha256") == sha and not r.get("trashed")), None)


def _stage(row, name, state, detail=""):
    row.setdefault("stages", {})[name] = {"state": state, "detail": detail, "at": _now()}


def _docx_text(path):
    import zipfile
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return html_unescape(re.sub(r"<[^>]+>", "", xml))


def _anthropic(messages, max_tokens=900):
    key = load_config()["keys"].get("anthropic")
    if not key:
        return None
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST",
                                 data=json.dumps({"model": INTAKE_MODEL, "max_tokens": max_tokens, "messages": messages}).encode(),
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


def _thumbnail(project, row, src):
    """A cached thumbnail in <project>/.thumbs/: image, PDF first page, video poster, audio waveform."""
    out = project.root / ".thumbs" / f"{row['id']}.png"
    out.parent.mkdir(exist_ok=True)
    kind = row["kind"]
    try:
        if kind == "pdf" and shutil.which("pdftoppm"):
            subprocess.run(["pdftoppm", "-png", "-f", "1", "-l", "1", "-scale-to", "320", "-singlefile", str(src),
                            str(out.with_suffix(""))], capture_output=True, timeout=60)
        elif kind in ("image", "video") and shutil.which("ffmpeg"):
            args = ["-ss", "1"] if kind == "video" else []
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-i", str(src), "-frames:v", "1",
                            "-vf", "scale=320:-2", str(out)], capture_output=True, timeout=60)
        elif kind == "audio" and shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex",
                            "aformat=channel_layouts=mono,showwavespic=s=320x90:colors=#C96F4A", "-frames:v", "1", str(out)],
                           capture_output=True, timeout=120)
    except Exception:
        pass
    return out.relative_to(project.root).as_posix() if out.exists() else None


def _known_entities(project):
    people, places = set(), set()
    for a in engine_familypedia(project):
        (people if a["type"] == "person" else places if a["type"] == "place" else set()).add(a["title"])
    return people, places


def _heuristic_understanding(project, row, text):
    people, places = _known_entities(project)
    found_people = sorted(p for p in people if p.split(",")[0] in text)
    found_places = sorted(p for p in places if p.split(",")[0] in text)
    years = sorted(set(YEAR.findall(text)))
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    summary = " ".join(sentences[:2])[:400] if text.strip() else ""
    return {"summary": summary, "people": found_people, "places": found_places, "organizations": [],
            "date_range": (f"{years[0]}–{years[-1]}" if len(years) > 1 else years[0]) if years else "",
            "doc_kind": {"audio": "recording", "video": "recording", "image": "photo"}.get(row["kind"], "other"),
            "confidence": {"summary": "low", "people": "medium", "places": "medium", "date_range": "low", "doc_kind": "low"},
            "method": "basic (no Anthropic key): first sentences and names the project already knows. "
                      "Add a key in Connectors, then Re-ingest, for a real summary and name"}


def _model_understanding(project, row, text):
    people, places = _known_entities(project)
    prompt = (
        "You are cataloguing one item for a family-history archive. Read the extracted text and answer ONLY with JSON:\n"
        '{"summary": "2-3 plain factual sentences, no adjectives doing work", '
        '"title": "a short descriptive title, lower-case words", "content_date": "YYYY-MM-DD or YYYY-MM or YYYY ONLY if the text states it, else empty", '
        '"people": [], "places": [], "organizations": [], "date_range": "", '
        f'"doc_kind": "one of {", ".join(DOC_KINDS)}", '
        '"confidence": {"summary": "high|medium|low", "people": "...", "places": "...", "date_range": "...", "doc_kind": "..."}}\n'
        "Never invent a date, a name or a relationship the text does not support. List only people and places the text "
        "actually names: don't map an unnamed reference ('the lake', 'Father') to a known person or place. "
        f"People already known in this project: {', '.join(sorted(people)[:60]) or 'none'}. "
        f"Places already known: {', '.join(sorted(places)[:60]) or 'none'}.\n\n"
        f"File name: {row['original_name']}\nKind: {row['kind']}\n\nEXTRACTED TEXT:\n{text[:12000]}")
    out = _anthropic([{"role": "user", "content": prompt}])
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        raise ValueError("the model did not return JSON")
    d = json.loads(m.group(0))
    d["method"] = f"model ({INTAKE_MODEL})"
    return d


def _suggested_name(row, title, content_date, text):
    """lower-case-hyphenated, dated only when the content supports the date; extension kept."""
    ext = Path(row["original_name"]).suffix.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", (title or Path(row["original_name"]).stem).lower()).strip("-")[:70] or "untitled"
    date, basis = "", ""
    if content_date and (content_date in text or content_date[:4] in text):
        date, basis = content_date, "date from the content"
    else:
        date, basis = row["date_added"][:10], "no date in the content: prefix is the date added"
    return f"{date}-{slug}{ext}", basis


def _links_to(project, row):
    """Existing sources, timeline events and stories this one bears on (by shared people/places/years)."""
    links = []
    people, places = set(row.get("people") or []), set(row.get("places") or [])
    years = set(YEAR.findall(row.get("date_range") or ""))
    tl = project.root / "facts" / "timeline.csv"
    for e in (csv.DictReader(open(tl, encoding="utf-8")) if tl.exists() else []):
        ep = set(x.strip() for x in (e.get("people") or "").split(";") if x.strip())
        if ep & people or (e.get("place") and e["place"] in places) or (years and (e.get("date_start") or "")[:4] in years):
            links.append({"type": "event", "id": e["event_id"], "label": e["event"]})
    for other in intake_load(project).values():
        if other["id"] != row["id"] and not other.get("trashed") and (set(other.get("people") or []) & people or set(other.get("places") or []) & places):
            links.append({"type": "source", "id": other["id"], "label": other.get("accepted_name") or other["original_name"]})
    for st in engine_stories(project):
        f = project.root / st["file"]
        if f.is_file():
            t = f.read_text(encoding="utf-8", errors="ignore")
            if any(p.split(",")[0] in t for p in people | places):
                links.append({"type": "story", "id": st["id"], "label": st["title"]})
    return links[:40]


def intake_run(project, row_id, rescan=False):
    """Stages 2–5 for one row. Stage 1 (ingest) happened on upload. Never raises: failures are rows."""
    data = intake_load(project)
    row = data.get(row_id)
    if not row:
        return
    src = project.root / row["path"]
    # ---- 2. extract
    try:
        _stage(row, "extract", "running"); intake_save_row(project, row)
        text, source, conf = "", "none", None
        kind = row["kind"]
        if kind == "pdf":
            if shutil.which("pdftotext"):
                r = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True, text=True, timeout=120)
                text = r.stdout
                source = "pdf text layer" if text.strip() else "none"
            if not text.strip():
                if shutil.which("tesseract") and shutil.which("pdftoppm"):
                    tmp = project.root / ".lineage" / f"ocr-{row_id}"
                    subprocess.run(["pdftoppm", "-png", "-r", "200", str(src), str(tmp)], capture_output=True, timeout=300)
                    parts = []
                    for img in sorted(tmp.parent.glob(f"ocr-{row_id}*.png")):
                        parts.append(subprocess.run(["tesseract", str(img), "-"], capture_output=True, text=True, timeout=300).stdout)
                        img.unlink()
                    text, source, conf = "\n".join(parts), "ocr", "unknown"
                else:
                    row["extract_note"] = "no text layer, and OCR (tesseract) is not installed: paste the text in the Edit drawer"
        elif kind == "image":
            if shutil.which("tesseract"):
                text = subprocess.run(["tesseract", str(src), "-"], capture_output=True, text=True, timeout=180).stdout
                source, conf = ("ocr" if text.strip() else "none"), "unknown"
            else:
                row["extract_note"] = "OCR (tesseract) is not installed; the vision pass below describes the image instead"
            if load_config()["keys"].get("anthropic") and src.stat().st_size < 4_500_000 and src.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                media = mimetypes.guess_type(src.name)[0] or "image/jpeg"
                desc = _anthropic([{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": base64.b64encode(src.read_bytes()).decode()}},
                    {"type": "text", "text": "Describe what is pictured in 2-3 plain sentences, and transcribe any handwriting or printing exactly. "
                                             "Never name a person from how they look; name someone only if writing on the item names them."}]}])
                if desc:
                    row["vision"] = {"text": desc.strip(), "by": "derived", "model": INTAKE_MODEL}
                    text = (text + "\n\n[vision description, inferred]\n" + desc).strip()
                    source = source if source != "none" else "vision (inferred)"
        elif kind in ("audio", "video"):
            row["duration"] = media_duration(src)
            sid = session_map(project).get(src.name)
            row["transcription"] = "done" if sid and (project.root / "transcript" / "clean" / f"{sid}.md").exists() else (row.get("transcription") or "queued")
            if row["transcription"] == "done":
                text, source = (project.root / "transcript" / "clean" / f"{sid}.md").read_text(encoding="utf-8"), "transcript"
        elif src.suffix.lower() == ".docx":
            text, source = _docx_text(src), "direct"
        elif kind == "text" and src.suffix.lower() in (".txt", ".md", ".csv", ".json", ".html"):
            text, source = src.read_text(encoding="utf-8", errors="replace"), "direct"
        else:
            row["extract_note"] = (f"can't read {src.suffix or 'this'} files yet: open it, copy the text, and paste it under "
                                   "Edit details → Extracted text; the rest of intake runs from there")
        if (row.get("mine") or {}).get("text") is not None:
            text, source = row["mine"]["text"], "edited by me"
        ex = project.root / "data" / "extracted" / f"{row_id}.txt"
        ex.parent.mkdir(parents=True, exist_ok=True)
        ex.write_text(text, encoding="utf-8")
        row.update(text_source=source, text_confidence=conf, extracted=ex.relative_to(project.root).as_posix(), text_chars=len(text))
        row["thumb"] = _thumbnail(project, row, src)
        _stage(row, "extract", "done", row.get("extract_note") or source)
    except Exception as e:
        text = ""
        _stage(row, "extract", "failed", f"{type(e).__name__}: {e}")
    intake_save_row(project, row)
    # ---- 3. understand
    try:
        _stage(row, "understand", "running"); intake_save_row(project, row)
        if row["kind"] in ("audio", "video") and row.get("transcription") != "done" and not text.strip():
            u = {"summary": "", "people": [], "places": [], "organizations": [], "date_range": "", "doc_kind": "recording",
                 "confidence": {}, "method": "waiting for transcription"}
        else:
            try:
                u = _model_understanding(project, row, text) if load_config()["keys"].get("anthropic") and text.strip() else _heuristic_understanding(project, row, text)
            except Exception as e:
                u = _heuristic_understanding(project, row, text)
                u["method"] += f" (model call failed: {type(e).__name__})"
        name, basis = _suggested_name(row, u.get("title"), u.get("content_date", ""), text)
        derived = {"summary": u.get("summary", ""), "people": u.get("people", []), "places": u.get("places", []),
                   "organizations": u.get("organizations", []), "date_range": u.get("date_range", ""),
                   "doc_kind": u.get("doc_kind") if u.get("doc_kind") in DOC_KINDS else "other",
                   "suggested_name": name, "suggested_name_basis": basis,
                   "confidence": u.get("confidence", {}), "method": u.get("method", "")}
        row["derived"] = derived
        _stage(row, "understand", "done", derived["method"])
    except Exception as e:
        _stage(row, "understand", "failed", f"{type(e).__name__}: {e}")
    intake_save_row(project, row)
    # ---- 4. index
    try:
        eff = effective(row)
        row["links_to"] = _links_to(project, eff)
        idx = project.root / "data" / "search_index.json"
        with INTAKE_LOCK:
            index = json.loads(idx.read_text()) if idx.exists() else {}
            index[row_id] = " ".join([eff.get("accepted_name") or "", row["original_name"], eff.get("summary") or "",
                                      " ".join(eff.get("people") or []), " ".join(eff.get("places") or []),
                                      row.get("notes") or "", " ".join((row.get("fields") or {}).values()), text[:50000]])
            idx.write_text(json.dumps(index, ensure_ascii=False))
        _stage(row, "index", "done")
    except Exception as e:
        _stage(row, "index", "failed", f"{type(e).__name__}: {e}")
    intake_save_row(project, row)
    # ---- 5. drive
    st = project.read()["settings"]
    want = row.get("store_in_drive", st.get("store_in_drive", False))
    if not drive_status()["connected"]:
        _stage(row, "drive", "skipped", "Enable the Google Drive connector in Connectors")
    elif not want:
        _stage(row, "drive", "skipped", "not stored in Drive")
    elif not drive_folder_id(st.get("drive_folder")):
        _stage(row, "drive", "skipped", "no Drive folder set in Settings")
    else:
        try:
            folder = _drive_subfolder(_drive_subfolder(drive_folder_id(st["drive_folder"]), "sources", create=True) or "", row["kind"], create=True)
            name = effective(row).get("accepted_name") or row["original_name"]
            boundary = "lineage" + secrets.token_hex(8)
            meta = json.dumps({"name": name, "parents": [folder]})
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                    f"--{boundary}\r\nContent-Type: {row.get('mime') or 'application/octet-stream'}\r\n\r\n").encode() \
                + src.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            res = drive_api("/upload/drive/v3/files", {"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id,webViewLink"},
                            "POST", body, {"Content-Type": f"multipart/related; boundary={boundary}"})
            row["drive_id"], row["drive_url"] = res.get("id"), res.get("webViewLink")
            _stage(row, "drive", "done", name)
        except Exception as e:
            _stage(row, "drive", "failed", f"{type(e).__name__}: {e}")
    intake_save_row(project, row)


def effective(row):
    """The row as the book sees it: my edits win over anything derived."""
    out = dict(row)
    d = row.get("derived") or {}
    for k in ("summary", "people", "places", "organizations", "date_range", "doc_kind"):
        out[k] = d.get(k)
    for k, v in (row.get("mine") or {}).items():
        out[k] = v
    out["by"] = {k: ("me" if k in (row.get("mine") or {}) else "derived") for k in
                 ("summary", "people", "places", "organizations", "date_range", "doc_kind", "accepted_name", "text")}
    return out


def intake_ingest(project, name, data, added_by="me"):
    """Stage 1. Returns (row, duplicate_of)."""
    sha = _sha256_bytes(data)
    dup = intake_find_hash(project, sha)
    if dup:
        return None, dup
    out = project.root / "sources" / Path(name).name
    if out.exists():
        out = out.with_name(f"{out.stem} ({datetime.now().strftime('%Y%m%d-%H%M%S')}){out.suffix}")
    out.write_bytes(data)
    row = {"id": sha[:12], "path": out.relative_to(project.root).as_posix(), "original_name": Path(name).name,
           "sha256": sha, "bytes": len(data), "mime": mimetypes.guess_type(out.name)[0] or "application/octet-stream",
           "kind": kind_of(out), "date_added": _now(), "added_by": added_by, "mine": {}, "fields": {}, "notes": "",
           "history": [{"at": _now(), "by": added_by, "event": "added"}]}
    _stage(row, "ingest", "done", f"sha256 {sha[:12]}…")
    intake_save_row(project, row)
    return row, None


def intake_adopt(project, path):
    """Index a file that is already in the project (dropped in by hand, or synced from Drive)."""
    p = project.root / path
    sha = _sha256_file(p)
    dup = intake_find_hash(project, sha)
    if dup:
        return dup
    row = {"id": sha[:12], "path": path, "original_name": p.name, "sha256": sha, "bytes": p.stat().st_size,
           "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream", "kind": kind_of(p),
           "date_added": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
           "added_by": "me", "mine": {}, "fields": {}, "notes": "", "history": [{"at": _now(), "by": "me", "event": "indexed"}]}
    _stage(row, "ingest", "done", f"sha256 {sha[:12]}… (already in the project)")
    intake_save_row(project, row)
    return row


def intake_start(project, row_id):
    threading.Thread(target=intake_run, args=(project, row_id), daemon=True).start()


def intake_edit(project, row_id, patch):
    """My edits: stored apart from the derived values, timestamped, and never overwritten by a re-scan."""
    data = intake_load(project)
    row = data[row_id]
    changed = []
    for k in ("summary", "people", "places", "organizations", "date_range", "doc_kind", "accepted_name", "text"):
        if k in patch:
            row.setdefault("mine", {})[k] = patch[k]
            changed.append(k)
    for k in STRUCTURED:
        if k in patch:
            row.setdefault("fields", {})[k] = patch[k]
            changed.append(k)
    for k in ("notes", "rotation", "store_in_drive"):
        if k in patch:
            row[k] = patch[k]
            changed.append(k)
    if patch.get("forget"):
        for k in patch["forget"]:
            row.get("mine", {}).pop(k, None)
            changed.append(f"reset {k}")
    row.setdefault("history", []).append({"at": _now(), "by": "me", "event": "edited", "fields": changed})
    intake_save_row(project, row)
    return row


def source_citations(project, row):
    """Stories that cite this source (by session timestamp or by name) and people it's tagged on."""
    sid = session_map(project).get(Path(row["path"]).name)
    names = {Path(row["path"]).name, (row.get("mine") or {}).get("accepted_name") or ""} - {""}
    stories = []
    for st in engine_stories(project):
        f = project.root / st["file"]
        if f.is_file():
            t = f.read_text(encoding="utf-8", errors="ignore")
            if (sid and f"[{sid} " in t) or any(n in t for n in names):
                stories.append({"id": st["id"], "title": st["title"]})
    tags = [t.get("person") for t in (row.get("tags") or []) if t.get("state") in ("accepted", "unsure")]
    return {"stories": stories, "people": tags}


def mark_stories_stale(project, story_ids, reason):
    p = project.root / "data" / "stale_stories.json"
    cur = json.loads(p.read_text()) if p.exists() else {}
    for sid in story_ids:
        cur[str(sid)] = {"reason": reason, "at": _now()}
    p.write_text(json.dumps(cur, indent=1))


def _unindex(project, row_id):
    idx = project.root / "data" / "search_index.json"
    with INTAKE_LOCK:
        if idx.exists():
            index = json.loads(idx.read_text())
            index.pop(row_id, None)
            idx.write_text(json.dumps(index, ensure_ascii=False))


def intake_trash(project, row_id, restore=False, delete_drive=False):
    data = intake_load(project)
    row = data[row_id]
    trash = project.root / ".trash"
    trash.mkdir(exist_ok=True)
    if restore:
        src = trash / Path(row["path"]).name
        dest = project.root / row["path"]
        if src.exists() and not dest.exists():
            shutil.move(str(src), str(dest))
        row["trashed"] = False
        row["history"].append({"at": _now(), "by": "me", "event": "restored"})
    else:
        src = project.root / row["path"]
        cites = source_citations(project, row)
        if src.exists():
            shutil.move(str(src), str(trash / src.name))
        (trash / f"{Path(row['path']).name}.lineage.json").write_text(json.dumps(row, indent=1, ensure_ascii=False))
        row["trashed"] = True
        _unindex(project, row_id)
        if cites["stories"]:
            mark_stories_stale(project, [c["id"] for c in cites["stories"]], f"source deleted: {row['original_name']}")
        drive_note = "Drive copy untouched"
        if delete_drive and row.get("drive_id"):
            try:
                drive_api(f"/drive/v3/files/{row['drive_id']}", {"supportsAllDrives": "true"}, "DELETE", raw=True)
                row["drive_id"], row["drive_url"], drive_note = None, None, "Drive copy deleted"
            except Exception as e:
                drive_note = f"Drive copy NOT deleted ({type(e).__name__})"
        row["history"].append({"at": _now(), "by": "me", "event": f"moved to .trash ({drive_note})"})
    intake_save_row(project, row)
    if restore:
        intake_start(project, row_id)      # back into the index
    return row


def intake_purge(project, row_id):
    """Delete permanently: the file in .trash and its row. Only from the trash."""
    data = intake_load(project)
    row = data.get(row_id)
    if not row or not row.get("trashed"):
        raise ValueError("only files in the trash can be deleted permanently")
    trash = project.root / ".trash"
    for f in (trash / Path(row["path"]).name, trash / f"{Path(row['path']).name}.lineage.json"):
        if f.exists():
            f.unlink()
    with INTAKE_LOCK:
        data = intake_load(project)
        data.pop(row_id, None)
        _index_path(project).write_text(json.dumps(data, indent=1, ensure_ascii=False))
    thumb = project.root / ".thumbs" / f"{row_id}.png"
    if thumb.exists():
        thumb.unlink()


def engine_search(project, q):
    idx = project.root / "data" / "search_index.json"
    if not idx.exists() or not q.strip():
        return []
    index = json.loads(idx.read_text())
    terms = [t.lower() for t in q.split() if t.strip()]
    rows = intake_load(project)
    hits = []
    for rid, text in index.items():
        low = text.lower()
        if all(t in low for t in terms) and rid in rows and not rows[rid].get("trashed"):
            pos = low.find(terms[0])
            hits.append({"id": rid, "name": rows[rid].get("mine", {}).get("accepted_name") or rows[rid]["original_name"],
                         "snippet": text[max(0, pos - 60): pos + 140]})
    return hits[:50]

# ---------------------------------------------------------------- identity of the lineage
def engine_covers(project):
    """Date range and places, from the timeline: '1834–1974 · Connecticut, Massachusetts'."""
    tl = project.root / "facts" / "timeline.csv"
    if not tl.exists():
        return {"years": None, "places": [], "text": ""}
    rows = list(csv.DictReader(open(tl, encoding="utf-8")))
    years = sorted(int(y) for r in rows for y in YEAR.findall((r.get("date_start") or "") + " " + (r.get("date_end") or "")))
    places = []
    for r in sorted(rows, key=lambda r: r.get("date_start") or "9999"):
        p = (r.get("place") or "").split(",")[-1].strip()
        if p and p not in places:
            places.append(p)
    yr = (f"{years[0]}–{years[-1]}" if years[0] != years[-1] else str(years[0])) if years else ""
    return {"years": yr, "places": places, "text": " · ".join(x for x in (yr, ", ".join(places[:6])) if x)}


def engine_identity(project):
    s = project.read()
    st = s["settings"]
    cs = crest_state(project)
    crest_path = cs["current"] if (cs["mode"] != "none" and cs["show"]) else None
    auto = engine_covers(project)
    return {"family_name": st.get("family_name", ""), "title": s.get("title", ""), "subtitle": st.get("subtitle", ""),
            "summary": st.get("summary", ""), "subject": s.get("subject", ""), "subject_short": st.get("subject_short", ""),
            "covers_auto": auto["text"], "covers": st.get("covers_override") or auto["text"],
            "covers_overridden": bool(st.get("covers_override")),
            "crest": crest_path, "crest_surfaces": cs["surfaces"], "crest_provenance": cs["provenance"],
            "display_title": s.get("title") or "Untitled lineage", "stale": s.get("stale", [])}


def engine_draft_summary(project):
    """A plain first draft of the summary, from counts in the project. Derived: the author edits it."""
    s = project.read()
    sessions = list(csv.DictReader(open(project.root / "transcript" / "sessions.csv", encoding="utf-8"))) \
        if (project.root / "transcript" / "sessions.csv").exists() else []
    stories = [x for x in engine_stories(project) if x["exists"]]
    people = [a for a in engine_familypedia(project) if a["type"] == "person"]
    cov = engine_covers(project)
    subject = s.get("subject") or "the subject"
    bits = [f"This collection holds {len(sessions)} recorded conversation{'s' if len(sessions) != 1 else ''} with {subject}"
            + (f", and {len(stories)} stor{'y' if len(stories) == 1 else 'ies'} written from them" if stories else "") + "."]
    if people:
        bits.append(f"It names {len(people)} people, among them {', '.join(a['title'] for a in people[:4])}.")
    if cov["text"]:
        bits.append(f"It covers {cov['text'].replace(' · ', ', in ')}.")
    bits.append("Everything in it comes from what was said on the recordings and from the records cited alongside.")
    return " ".join(bits)

# ---------------------------------------------------------------- crest / symbol
# Generate (OpenAI images, 4 candidates, attempts kept), Upload (original kept; optional
# background removal and a one-colour version), or None. Hidden everywhere until switched on;
# hiding never deletes. Provenance travels with the mark, so a generated one never reads as inherited.
CREST_STYLES = {
    "engraved": "engraved line art, fine black hatching on white, like a nineteenth-century book plate",
    "woodcut": "a woodcut print, bold black carved lines on white",
    "heraldic": "a heraldic shield, flat colours with a thin black outline, simple charges",
    "monogram": "a letterpress monogram, one colour, set in a round seal",
    "botanical": "a botanical mark, a single plant drawn in fine line, one colour",
}
IMAGE_MODEL = "gpt-image-1"


def _crest_dir(project):
    d = project.root / ".lineage" / "crest"
    (d / "attempts").mkdir(parents=True, exist_ok=True)
    return d


def crest_state(project):
    d = _crest_dir(project)
    cur = d / "current.png"
    prov = json.loads((d / "current.json").read_text()) if (d / "current.json").exists() else None
    attempts = []
    for meta in sorted((d / "attempts").glob("*.json"), reverse=True):
        m = json.loads(meta.read_text())
        img = meta.with_suffix(".png")
        if img.exists():
            attempts.append({**m, "image": img.relative_to(project.root).as_posix(), "name": img.stem})
    variants = {k: (d / f"current-{k}.png").relative_to(project.root).as_posix()
                for k in ("transparent", "mono") if (d / f"current-{k}.png").exists()}
    st = project.read()["settings"]
    return {"mode": st.get("crest_mode", "none"), "show": bool(st.get("crest_show")),
            "surfaces": st.get("crest_surfaces") or DEFAULT_SETTINGS["crest_surfaces"],
            "current": cur.relative_to(project.root).as_posix() if cur.exists() else None,
            "provenance": prov, "attempts": attempts[:40], "variants": variants,
            "styles": {k: v for k, v in CREST_STYLES.items()}, "openai": bool(load_config()["keys"].get("openai"))}


def crest_prompt_fill(project):
    """A starting point from the project's own material, to be edited."""
    st = project.read()["settings"]
    tl = engine_timeline(project)
    places = list(dict.fromkeys(e["place"].split(",")[0] for e in tl["events"] if e["place"]))[:5]
    trades = list(dict.fromkeys(e["type"] for e in tl["events"] if e["type"] in ("employment", "migration", "military service", "journey")))
    words = re.findall(r"ore boats|whal\w+|mill\w*|tobacco|farm\w*|cabin|lake|river|ship\w*|dock\w*|school|church", " ".join(e["title"] for e in tl["events"]), re.I)
    return ", ".join(x for x in [st.get("family_name") or "", ", ".join(places), ", ".join(dict.fromkeys(w.lower() for w in words))] if x)


def crest_generate(project, prompt, style):
    key = load_config()["keys"].get("openai")
    if not key:
        raise RuntimeError("Add an OpenAI key in Connectors")
    full = (f"A family symbol for a family history book: {prompt}. Style: {CREST_STYLES.get(style, style)}. "
            "Centered on a plain white background, no text, no letters unless it is a monogram, reads clearly at small sizes.")
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", method="POST",
                                 data=json.dumps({"model": IMAGE_MODEL, "prompt": full, "n": 4, "size": "1024x1024"}).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI said {e.code}: {e.read().decode(errors='replace')[:200]}")
    d = _crest_dir(project)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    made = []
    for i, item in enumerate(body.get("data", [])):
        if item.get("b64_json"):
            img = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            with urllib.request.urlopen(item["url"], timeout=120) as r:
                img = r.read()
        else:
            continue
        name = f"{stamp}-{i + 1}"
        (d / "attempts" / f"{name}.png").write_bytes(img)
        (d / "attempts" / f"{name}.json").write_text(json.dumps({"kind": "generated", "model": IMAGE_MODEL, "prompt": prompt,
                                                                  "style": style, "full_prompt": full, "date": _now()}, indent=1))
        made.append(name)
    return {"made": made, **crest_state(project)}


def crest_choose(project, name):
    d = _crest_dir(project)
    src = d / "attempts" / f"{name}.png"
    if not src.exists():
        raise FileNotFoundError("no such attempt")
    shutil.copy2(src, d / "current.png")
    shutil.copy2(src.with_suffix(".json"), d / "current.json")
    for v in d.glob("current-*.png"):
        v.unlink()
    s = project.read()
    s["settings"]["crest_mode"] = "generate"
    s["stale"] = sorted(set(s.get("stale", [])) | {"title page", "Familypedia front page"})
    project.write(s)
    return crest_state(project)


def crest_upload(project, filename, data, provenance_kind, note):
    ext = Path(filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".svg"):
        raise ValueError("use a PNG, JPG or SVG")
    d = _crest_dir(project)
    (d / f"original{ext}").write_bytes(data)                       # the original is always kept
    if ext == ".svg":
        (d / "current.svg").write_bytes(data)
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-w", "1024", "-o", str(d / "current.png"), str(d / "current.svg")], timeout=60)
    elif shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(d / f"original{ext}"), str(d / "current.png")], timeout=60)
    else:
        (d / "current.png").write_bytes(data)
    for v in d.glob("current-*.png"):
        v.unlink()
    (d / "current.json").write_text(json.dumps({"kind": "uploaded", "provenance": provenance_kind, "note": note,
                                                "original": f"original{ext}", "date": _now()}, indent=1))
    s = project.read()
    s["settings"]["crest_mode"] = "upload"
    s["stale"] = sorted(set(s.get("stale", [])) | {"title page", "Familypedia front page"})
    project.write(s)
    return crest_state(project)


def crest_variant(project, kind):
    """Optional print helpers from the current mark; the original stays untouched."""
    d = _crest_dir(project)
    src = d / "current.png"
    if not src.exists() or not shutil.which("ffmpeg"):
        raise RuntimeError("needs a current crest and ffmpeg")
    out = d / f"current-{kind}.png"
    vf = {"transparent": "format=rgba,colorkey=white:0.25:0.1",
          "mono": "format=gray,lutyuv=y='if(lt(val,140),0,255)',format=rgba,colorkey=white:0.2:0.05"}[kind]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf, str(out)], timeout=120)
    return crest_state(project)

# ---------------------------------------------------------------- stories
# A story is one written piece (a chapter file on disk). The UI says "story"; the files keep
# their names (chapters/, data/chapters.csv) so the Lineage skills downstream don't change.
STORY_STATES = ("draft", "in the book", "kept aside")
YEAR = re.compile(r"(1[5-9]\d\d|20\d\d)")


def _story_states(project):
    p = project.root / "data" / "story_states.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _plain_words(text):
    text = re.sub(r"(?m)^\s*//.*$", " ", text)               # comments
    text = re.sub(r"#\w[\w.-]*(\.with)?\(.*?\)\s*$", " ", text, flags=re.M)
    text = re.sub(r"[#\[\]{}*_]", " ", text)
    return len(re.findall(r"[A-Za-z’'-]+", text))


def engine_stories(project):
    """Every story with its dates, size, bridges, state and place in the book, oldest first."""
    rows = []
    csv_path, json_path = project.root / "data" / "chapters.csv", project.root / "data" / "chapters.json"
    if csv_path.exists():
        for r in csv.DictReader(open(csv_path, encoding="utf-8")):
            rows.append({"id": r.get("chapter"), "file": r.get("file", ""), "title": r.get("title", ""),
                         "part": r.get("part", ""), "dates": r.get("dates") or r.get("date_range") or "",
                         "summary": r.get("summary", ""), "map_status": r.get("status", "")})
    elif json_path.exists():
        for c in json.loads(json_path.read_text()):
            slug = re.sub(r"[^a-z0-9]+", "-", c["title"].lower()).strip("-")
            rows.append({"id": str(c["n"]), "file": f"chapters/{int(c['n']):02d}-{slug}.md", "title": c["title"],
                         "part": c.get("part", ""), "dates": c.get("years", ""), "summary": c.get("summary", ""),
                         "map_status": "proposed"})
    states = _story_states(project)
    sp = project.root / "data" / "stale_stories.json"
    stale = json.loads(sp.read_text()) if sp.exists() else {}
    parts, chapter_no = [], 0
    for r in rows:
        f = project.root / r["file"] if r["file"] else None
        text = f.read_text(encoding="utf-8", errors="ignore") if f and f.is_file() else ""
        years = [int(y) for y in YEAR.findall(r["dates"])]
        state = states.get(r["id"], "in the book" if text else "draft")
        if state == "in the book":
            chapter_no += 1
            if r["part"] and r["part"] not in parts:
                parts.append(r["part"])
        words = _plain_words(text) if text else 0
        rows_extra = {
            "exists": bool(text), "words": words, "reading_minutes": max(1, round(words / 230)) if words else 0,
            "bridges": len(re.findall(r"#bridge\[|⟦BRIDGE", text)),
            "quotes": len(re.findall(r'"[^"\n]{12,}"|“[^”\n]{12,}”', text)),
            "photos": len(re.findall(r"#(?:plate|photo|plate-pair)\(", text)),
            "citations": len(re.findall(r"// src:", text)),
            "year": years[0] if years else None, "state": state,
            "book_position": (f"{'Part ' + str(len(parts)) + ', ' if r['part'] else ''}Chapter {chapter_no}"
                              if state == "in the book" else ("kept aside" if state == "kept aside" else "not in the book yet")),
            "mtime": f.stat().st_mtime if f and f.is_file() else None,
            "stale": stale.get(r["id"]),
        }
        r.update(rows_extra)
    voices = story_voices(project)
    for r in rows:
        r.update(story_audio_info(project, r) if r["exists"] else {"has_audio": False})
        r["voice_override"] = voices.get(r["id"])
        r["narration_chars"] = None
    return rows


CITE_TOKEN = re.compile(r"\[S\d+ \d\d:\d\d:\d\d\]|\bR\d{3,}\b|https?://\S+")
PLATE = re.compile(r'#(?:plate|photo|plate-pair)\(\s*"([^"]+)"(.*?)\)\s*$')


def story_apparatus(project, story_id):
    """What a story rests on: each cited paragraph with its citation chips, and each image with its
    caption, provenance and whether it is an illustration. Read from the generated story file."""
    st = _story_by_id(project, story_id)
    if not st:
        raise KeyError("no such story")
    f = project.root / st["file"]
    if not f.is_file():
        raise KeyError("this story has no draft yet")
    photos = {r.get("id"): r for r in csv.DictReader(open(project.root / "photos" / "photo_index.csv", encoding="utf-8"))} \
        if (project.root / "photos" / "photo_index.csv").exists() else {}
    paras, images, buf = [], [], []
    for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        t = line.strip()
        if t.startswith("// src:"):
            src = t[len("// src:"):].strip()
            text = re.sub(r"#\w[\w.-]*\(\s*\"[^\"]*\"\s*\)", "", " ".join(buf)).replace("][", " ")
            text = re.sub(r"#\w+\[|[\[\]]|#\w+", "", text)
            chips = CITE_TOKEN.findall(src)
            rest = CITE_TOKEN.sub("", src).strip(" ;,-")
            paras.append({"excerpt": re.sub(r"\s+", " ", text).strip()[:220], "cites": chips, "note": rest})
            buf = []
            continue
        m = PLATE.match(t)
        if m:
            path, args = m.group(1).lstrip("/"), m.group(2)
            cap = re.search(r'caption:\s*"([^"]*)"', args)
            pid = re.search(r'id:\s*"([^"]*)"', args)
            row = photos.get(pid.group(1) if pid else "", {})
            caption = cap.group(1) if cap else row.get("subject", "")
            illus = bool(ILLUSTRATION.search(" ".join([caption, row.get("subject", ""), row.get("kind", ""), row.get("needs_attention", "")])))
            images.append({"path": path, "id": pid.group(1) if pid else "", "caption": caption, "illustration": illus,
                           "exists": (project.root / path).is_file(), "people": row.get("people", ""),
                           "people_basis": row.get("people_basis", ""), "date": row.get("date", ""),
                           "date_basis": row.get("date_basis", ""), "location": row.get("location", ""),
                           "holder": row.get("holder", ""), "source_file": row.get("source_file", ""),
                           "placeholder": "placeholder" in (caption + row.get("kind", "")).lower()})
            buf = []
            continue
        if t.startswith("//") or t.startswith("#show") or t.startswith("#import"):
            continue
        if t:
            buf.append(t)
    return {"id": st["id"], "title": st["title"], "paragraphs": paras, "images": images}


def engine_set_story_state(project, story_id, state):
    if state not in STORY_STATES:
        raise ValueError(f"state must be one of {STORY_STATES}")
    states = _story_states(project)
    states[str(story_id)] = state
    (project.root / "data" / "story_states.json").write_text(json.dumps(states, indent=1))
    return states


def lineage_home():
    """The Lineage plugin folder (book template and fonts), from a repo checkout."""
    for cand in (HERE.parent / "plugins" / "lineage", Path(os.environ.get("LINEAGE", "")) if os.environ.get("LINEAGE") else None):
        if cand and (cand / "book" / "template.typ").exists():
            return cand
    return None


def engine_render_story(project, story_id, ppi=110):
    """Compile one story on its own into real book pages (PNG). Returns the page paths."""
    story = next((s for s in engine_stories(project) if s["id"] == str(story_id)), None)
    if not story or not story["exists"]:
        raise RuntimeError("this story has no text yet")
    if not story["file"].endswith(".typ"):
        raise RuntimeError("only Typst story files can be rendered as pages (this one is a draft in Markdown)")
    if not shutil.which("typst"):
        raise RuntimeError("typst is not installed")
    home = lineage_home()
    tpl = project.root / "book" / "template.typ"
    if home and (not tpl.exists() or tpl.read_bytes() != (home / "book" / "template.typ").read_bytes()):
        tpl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(home / "book" / "template.typ", tpl)
    if not tpl.exists():
        raise RuntimeError("no book/template.typ in the project")
    out = project.root / ".lineage" / "render" / str(story_id)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    title = (project.read().get("title") or "").replace('"', "'")
    main = out / "main.typ"
    main.write_text(f'#import "/book/template.typ": *\n#show: book.with(title: "{title}", trim: "{project.read()["settings"].get("trim", "7x10")}")\n'
                    f'#show: main-matter\n#include "/{story["file"]}"\n', encoding="utf-8")
    cmd = ["typst", "compile", "--root", str(project.root)]
    if home and (home / "fonts").exists():
        cmd += ["--font-path", str(home / "fonts")]
    cmd += ["--format", "png", "--ppi", str(ppi), str(main), str(out / "page-{0p}.png")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise RuntimeError(r.stderr.strip().splitlines()[0] if r.stderr.strip() else "typst failed")
    pages = sorted(p.relative_to(project.root).as_posix() for p in out.glob("page-*.png"))
    return {"pages": pages, "story": story}


# ---------------------------------------------------------------- timeline
PIVOTAL = re.compile(r"\b(born|birth|died|death|dies|married|marri|wedding|moved|moves|emigrat|immigrat|crossed|enlist|"
                     r"war|discharg|graduat|retir|buil[dt]|bought|sold|fire|flood)\w*", re.I)
EVENT_TYPES = [("birth", r"\bborn|birth"), ("death", r"\bdied|death|dies|buried"), ("marriage", r"marri|wedding"),
               ("migration", r"emigrat|immigrat|crossed|moved|moves|sailed"), ("military service", r"enlist|regiment|war|discharg"),
               ("disaster", r"fire|flood|storm|snow|wreck"), ("employment", r"work|job|mill|ore boats|school|nursing"),
               ("journey", r"journey|voyage|trip|drove|walk")]


def _tier_of(e):
    basis = " ".join(e.get(k, "") or "" for k in ("date_basis", "event", "source")).lower()
    if "family account" in basis or "lore" in basis:
        return "lore"
    if re.search(r"\bR\d+\b|https?://|record|roster|census|certificate|manifest|ledger", basis, re.I):
        return "documented"
    if "told" in basis:
        return "told"
    return "witnessed"


def _event_type(text):
    return next((t for t, rx in EVENT_TYPES if re.search(rx, text, re.I)), "event")


def _timeline_rows(project):
    tl = project.root / "facts" / "timeline.csv"
    return list(csv.DictReader(open(tl, encoding="utf-8"))) if tl.exists() else []


def _transcript_line(project, cite):
    """The transcript paragraph a citation like [S1 00:00:29] points at."""
    m = re.search(r"(S\d+) (\d\d:\d\d:\d\d)", cite or "")
    if not m:
        return None
    f = project.root / "transcript" / "clean" / f"{m.group(1)}.md"
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        pm = PARA.match(line)
        if pm and pm["sid"] == m.group(1) and pm["ts"] == m.group(2):
            return {"speaker": pm["spk"], "text": pm["text"], "cite": f"[{pm['sid']} {pm['ts']}]"}
    return None


def engine_timeline(project):
    """Every event, oldest first, with tier, people, places, citations, stories, highlights, conflicts and gaps."""
    stars = set(json.loads((project.root / "data" / "timeline_stars.json").read_text())) \
        if (project.root / "data" / "timeline_stars.json").exists() else set()
    stories = {s["id"]: s["title"] for s in engine_stories(project)}
    slugs = {a["title"]: a["slug"] for a in engine_familypedia(project)}
    ev_subjects = familypedia.event_subjects(project)
    photos = {}
    for r in intake_load(project).values():
        if r.get("kind") == "image" and r.get("thumb") and not r.get("trashed"):
            for e in (r.get("mine") or {}).get("events", []) or []:
                photos[e] = r["thumb"]
    events, undated = [], []
    for e in _timeline_rows(project):
        years = YEAR.findall(e.get("date_start") or "")
        people = [x.strip() for x in (e.get("people") or "").split(";") if x.strip()]
        quote = (e.get("quote") or "").strip()
        cites = [c.strip() for c in re.split(r";\s*", e.get("source") or "") if c.strip()]
        ev = {"id": e["event_id"], "year": int(years[0]) if years else None, "date": e.get("date_display") or e.get("date_start") or "",
              "precision": e.get("precision") or "", "derived": (e.get("precision") or "") not in ("day", "exact", "year"),
              "title": e["event"].rstrip("."), "summary": e.get("date_basis") or "", "people": people,
              "place": e.get("place") or "", "cites": cites, "quote": quote, "tier": _tier_of(e),
              "confidence": e.get("confidence") or "", "conflict": (e.get("conflicts") or "").strip(),
              "story": stories.get(str(e.get("chapter") or "")), "story_id": str(e.get("chapter") or "") or None,
              "slug": slugs.get(e["event"].rstrip(".")), "person_slugs": {p: slugs.get(p) for p in people},
              "place_slug": slugs.get(e.get("place") or ""), "type": _event_type(e["event"]),
              "starred": e["event_id"] in stars, "photo": photos.get(e["event_id"]),
              "subjects": [x for x in ev_subjects.get(e["event_id"], []) if x["type"] not in ("person", "event")
                           and x["title"] != (e.get("place") or "")]}
        ev["highlight"] = ev["starred"] or bool(PIVOTAL.search(e["event"]))
        (events if ev["year"] else undated).append(ev)
    events.sort(key=lambda x: (x["year"], x["id"]))
    gaps = []
    for a, b in zip(events, events[1:]):
        if b["year"] - a["year"] >= 6:
            gaps.append({"after": a["id"], "from": a["year"], "to": b["year"]})
    birth = None
    subject = project.read().get("subject") or ""
    for ev in events:
        if subject and subject in ev["people"] and ev["type"] == "birth":
            birth = ev["year"]
    return {"events": events, "undated": undated, "gaps": gaps, "subject_birth": birth,
            "subject_short": project.read()["settings"].get("subject_short") or (subject.split()[0] if subject else "")}


def engine_timeline_svg(project):
    tl = engine_timeline(project)
    rows = tl["events"]
    h = 60 + 46 * len(rows)
    tier_fill = {"documented": "#1C1A17", "witnessed": "#4F7A54", "told": "#FFFDF8", "lore": "#FFFDF8"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{h}" viewBox="0 0 760 {h}" font-family="Georgia, serif">',
             f'<rect width="760" height="{h}" fill="#F7F3EC"/>',
             f'<text x="30" y="34" font-size="20" fill="#1C1A17">{html_escape(project.read().get("title") or "Timeline")}</text>',
             f'<line x1="130" y1="50" x2="130" y2="{h - 10}" stroke="#C96F4A" stroke-width="2"/>']
    for i, ev in enumerate(rows):
        y = 70 + 46 * i
        dash = ' stroke-dasharray="2,2"' if ev["tier"] == "lore" else ""
        parts.append(f'<text x="118" y="{y + 5}" font-size="13" text-anchor="end" fill="#4A443C">{html_escape(ev["date"])}</text>')
        parts.append(f'<circle cx="130" cy="{y}" r="6" fill="{tier_fill.get(ev["tier"], "#FFFDF8")}" stroke="#1C1A17" stroke-width="1.5"{dash}/>')
        parts.append(f'<text x="146" y="{y + 5}" font-size="14" fill="#1C1A17">{html_escape(ev["title"][:90])}</text>')
    parts.append("</svg>")
    return "\n".join(parts).encode()


def add_question(project, text, source):
    p = project.root / "data" / "questions.json"
    cur = json.loads(p.read_text()) if p.exists() else []
    cur.append({"text": text, "source": source, "at": _now(), "by": "me"})
    p.write_text(json.dumps(cur, indent=1, ensure_ascii=False))
    return cur

# ---------------------------------------------------------------- genealogy (derived from sources)
# derived.json: what the last approved rebuild found. mine.json: my corrections, which always win.
# proposed.json: a rebuild waiting for review. No evidence, no link: people without one float free.
REL_TYPES = ("parent", "spouse", "sibling")
G_TIERS = ("documented", "told", "lore", "unconfirmed")


def _gdir(project):
    d = project.root / "data" / "genealogy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gload(project, name, default):
    p = _gdir(project) / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else default


def _gsave(project, name, data):
    (_gdir(project) / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))


def _pid(name):
    return _slug(name) or "unknown"


def _lid(a, rel, b):
    """Link id. Spouse and sibling have no direction, so their ids are order-free."""
    if rel in ("spouse", "sibling"):
        a, b = sorted((a, b))
    return f"{a}-{rel}-{b}"


def genealogy_material(project):
    """What the rebuild reads: transcripts, source summaries and notes, records, the timeline's people."""
    parts = []
    for p, t in _texts(project, ["transcript/clean/*.md"]):
        parts.append(f"=== TRANSCRIPT {p.stem}\n" + t[:60000])
    for r in intake_load(project).values():
        if r.get("trashed"):
            continue
        e = effective(r)
        extra = " ".join(filter(None, [e.get("summary"), r.get("notes"), " ".join((r.get("fields") or {}).values())]))
        if extra.strip():
            parts.append(f"=== SOURCE {r['id']} ({r['original_name']})\n{extra}")
    arch = project.root / "data" / "archives.csv"
    if arch.exists():
        parts.append("=== RECORDS\n" + arch.read_text(encoding="utf-8")[:20000])
    return "\n\n".join(parts)[:150000]


def genealogy_rebuild(project):
    """Derive people and relationships with evidence. Every link must cite a passage that exists."""
    people = {}
    for a in engine_familypedia(project):
        if a["type"] == "person":
            people[_pid(a["title"])] = {"id": _pid(a["title"]), "name": a["title"], "aliases": [], "dates": "", "living": None,
                                        "evidence": []}
    links, note = [], ""
    if load_config()["keys"].get("anthropic"):
        material = genealogy_material(project)
        prompt = ("You are building a family tree for a family-history book, ONLY from the material below. Answer with JSON: "
                  '{"people":[{"name":"","aliases":[],"dates":"","living":true|false|null}], '
                  '"links":[{"a":"name","rel":"parent|spouse|sibling","b":"name","tier":"documented|told|lore|unconfirmed",'
                  '"evidence":[{"cite":"[S1 00:00:05] or SOURCE id or a record id","quote":"the exact words that establish it"}]}]}\n'
                  "\"a parent b\" means a is the parent of b. Rules: include a relationship ONLY when the material states it; "
                  "quote the exact words. Never infer a relationship from a surname, a date, or two people appearing together. "
                  "'told' = the narrator was told it; 'lore' = family story; 'documented' = a record says it.\n\nMATERIAL:\n" + material)
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", method="POST",
                                     data=json.dumps({"model": INTAKE_MODEL, "max_tokens": 4000,
                                                      "messages": [{"role": "user", "content": prompt}]}).encode(),
                                     headers={"x-api-key": load_config()["keys"]["anthropic"], "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            out = "".join(b.get("text", "") for b in json.loads(r.read().decode()).get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0)) if m else {"people": [], "links": []}
        haystack = material
        for pp in data.get("people", []):
            pid = _pid(pp.get("name", ""))
            people.setdefault(pid, {"id": pid, "name": pp.get("name"), "aliases": [], "dates": "", "living": None, "evidence": []})
            people[pid].update({k: pp[k] for k in ("aliases", "dates", "living") if pp.get(k) not in (None, "", [])})
        dropped = 0
        for ln in data.get("links", []):
            ev = [x for x in ln.get("evidence", []) if x.get("quote") and x["quote"][:40] in haystack]
            if not ev or ln.get("rel") not in REL_TYPES:
                dropped += 1
                continue                                   # no evidence, no link
            a, b = _pid(ln["a"]), _pid(ln["b"])
            for pid, nm in ((a, ln["a"]), (b, ln["b"])):
                people.setdefault(pid, {"id": pid, "name": nm, "aliases": [], "dates": "", "living": None, "evidence": []})
            links.append({"id": _lid(a, ln["rel"], b), "a": a, "rel": ln["rel"], "b": b,
                          "tier": ln.get("tier") if ln.get("tier") in G_TIERS else "unconfirmed", "evidence": ev})
        note = f"derived by {INTAKE_MODEL}; {len(links)} relationship(s) with evidence, {dropped} dropped for lack of a quotable passage"
    else:
        note = "no Anthropic key: people listed from the material, no relationships derived (add a key, or ask the Genealogist)"
    proposed = {"people": people, "links": links, "made": _now(), "note": note}
    _gsave(project, "proposed", proposed)
    return genealogy_diff(project)


def genealogy_diff(project):
    cur = _gload(project, "derived", {"people": {}, "links": []})
    new = _gload(project, "proposed", None)
    if not new:
        return {"pending": False}
    cl = {l["id"]: l for l in cur["links"]}
    nl = {l["id"]: l for l in new["links"]}
    pairs_cur = {(l["a"], l["b"]): l for l in cur["links"]}
    contradictions = [{"new": l, "old": pairs_cur[(l["a"], l["b"])]} for l in new["links"]
                      if (l["a"], l["b"]) in pairs_cur and pairs_cur[(l["a"], l["b"])]["rel"] != l["rel"]]
    return {"pending": True, "note": new.get("note"), "made": new.get("made"),
            "new_people": [p for k, p in new["people"].items() if k not in cur["people"]],
            "new_links": [l for k, l in nl.items() if k not in cl],
            "changed_links": [{"old": cl[k], "new": l} for k, l in nl.items() if k in cl and cl[k]["tier"] != l["tier"]],
            "gone_links": [l for k, l in cl.items() if k not in nl],
            "contradictions": contradictions}


def genealogy_apply(project, accept_ids=None):
    """Accept a reviewed rebuild. Contradictions are kept as conflicts, never resolved silently."""
    new = _gload(project, "proposed", None)
    if not new:
        raise ValueError("nothing to apply")
    cur = _gload(project, "derived", {"people": {}, "links": [], "conflicts": []})
    diff = genealogy_diff(project)
    keep = set(accept_ids) if accept_ids is not None else {l["id"] for l in new["links"]}
    links = {l["id"]: l for l in cur["links"]}
    for l in new["links"]:
        if l["id"] in keep:
            links[l["id"]] = l
    conflicts = cur.get("conflicts", []) + [{"a": c["new"]["a"], "b": c["new"]["b"], "versions": [c["old"], c["new"]],
                                              "state": "unresolved", "at": _now()} for c in diff["contradictions"]]
    people = {**cur["people"], **new["people"]}
    _gsave(project, "derived", {"people": people, "links": list(links.values()), "conflicts": conflicts, "applied": _now(),
                                "note": new.get("note")})
    (_gdir(project) / "proposed.json").unlink()
    _ghistory(project, "applied a rebuild", {"links": len(keep), "conflicts": len(diff["contradictions"])})
    return genealogy_graph(project)


def _ghistory(project, event, detail=None):
    h = _gload(project, "history", [])
    h.append({"at": _now(), "by": "me", "event": event, "detail": detail or {}})
    _gsave(project, "history", h)


def genealogy_graph(project):
    """The tree as shown: derived, with my corrections laid over it (they always win)."""
    d = _gload(project, "derived", {"people": {}, "links": [], "conflicts": []})
    mine = _gload(project, "mine", {"people": {}, "links": {}, "merges": [], "notes": {}})
    people = {k: dict(v, by="derived") for k, v in d["people"].items()}
    for pid, p in mine.get("people", {}).items():
        people[pid] = {**people.get(pid, {"id": pid, "aliases": [], "dates": "", "living": None, "evidence": []}), **p, "by": "me"}
    links = {l["id"]: dict(l, by="derived") for l in d["links"]}
    for lid, l in mine.get("links", {}).items():
        if l.get("removed"):
            links.pop(lid, None)
        else:
            links[lid] = {**links.get(lid, {}), **l, "id": lid, "by": "me"}
    for mg in mine.get("merges", []):                     # merged duplicates: alias recorded, links redirected
        keep, gone = mg["keep"], mg["merge"]
        if gone in people and keep in people:
            people[keep]["aliases"] = sorted(set(people[keep].get("aliases", [])) | {people[gone]["name"]} | set(people[gone].get("aliases", [])))
            people.pop(gone)
        for l in links.values():
            l["a"] = keep if l["a"] == gone else l["a"]
            l["b"] = keep if l["b"] == gone else l["b"]
    slugs = {a["slug"] for a in engine_familypedia(project)}
    sources_by_person = {}
    for r in intake_load(project).values():
        if not r.get("trashed"):
            for nm in effective(r).get("people") or []:
                # a person's picture is a real photograph or scan, never an illustration
                sources_by_person.setdefault(_pid(nm), []).append(r.get("thumb") if r.get("kind") == "image" and not is_illustration(r) else None)
    stories = engine_stories(project)
    for pid, p in people.items():
        p["note"] = mine.get("notes", {}).get(pid, "")
        p["article"] = pid if pid in slugs else None
        thumbs = [t for t in sources_by_person.get(pid, []) if t]
        p["photo"] = thumbs[0] if thumbs else None
        p["n_sources"] = len(sources_by_person.get(pid, []))
        p["has_story"] = any(p["name"].split()[0] in (project.root / st["file"]).read_text(encoding="utf-8", errors="ignore")
                             for st in stories if st["exists"]) if p.get("name") else False
    subject = project.read().get("subject") or ""
    return {"people": list(people.values()), "links": list(links.values()), "conflicts": d.get("conflicts", []),
            "subject": _pid(subject) if subject else None, "note": d.get("note", ""), "applied": d.get("applied"),
            "pending": genealogy_diff(project).get("pending", False), "history": _gload(project, "history", [])[-30:],
            "merges": mine.get("merges", [])}


def genealogy_edit(project, op, data):
    mine = _gload(project, "mine", {"people": {}, "links": {}, "merges": [], "notes": {}})
    if op == "person":
        pid = data.get("id") or _pid(data["name"])
        mine["people"][pid] = {k: data[k] for k in ("name", "dates", "living", "aliases") if k in data}
    elif op == "link":
        a, b, rel = _pid(data["a"]), _pid(data["b"]), data["rel"]
        if rel not in REL_TYPES:
            raise ValueError(f"relationship must be one of {REL_TYPES}")
        lid = data.get("id") or _lid(a, rel, b)
        mine["links"][lid] = {"a": a, "b": b, "rel": rel, "tier": data.get("tier", "unconfirmed"),
                              "evidence": [{"cite": "stated by me", "quote": data.get("evidence", "")}], "at": _now()}
    elif op == "link_tier":
        mine["links"].setdefault(data["id"], {}).update({"tier": data["tier"], "at": _now()})
    elif op == "link_remove":
        mine["links"][data["id"]] = {"removed": True, "at": _now()}
    elif op == "merge":
        mine["merges"].append({"keep": data["keep"], "merge": data["merge"], "at": _now()})
    elif op == "split":
        mine["merges"] = [m for m in mine["merges"] if m["merge"] != data["merge"]]
    elif op == "note":
        mine["notes"][data["id"]] = data.get("note", "")
    else:
        raise ValueError("unknown edit")
    _gsave(project, "mine", mine)
    _ghistory(project, op, data)
    return genealogy_graph(project)


def genealogy_gedcom(project):
    g = genealogy_graph(project)
    ids = {p["id"]: f"@I{i + 1}@" for i, p in enumerate(g["people"])}
    out = ["0 HEAD", "1 SOUR LINEAGE", "1 GEDC", "2 VERS 5.5.1", "1 CHAR UTF-8"]
    for p in g["people"]:
        if p.get("living"):                                   # living people stay out of exports
            out += [f"0 {ids[p['id']]} INDI", "1 NAME Living /Person/"]
            continue
        out += [f"0 {ids[p['id']]} INDI", f"1 NAME {p.get('name') or p['id']}"]
        if p.get("dates"):
            out += ["1 NOTE dates as the evidence supports: " + p["dates"]]
        for al in p.get("aliases", []):
            out.append(f"1 NAME {al}")
    fams = {}
    for l in g["links"]:
        if l["rel"] == "spouse":
            fams.setdefault(tuple(sorted((l["a"], l["b"]))), {"spouses": {l["a"], l["b"]}, "children": set(), "notes": []})["notes"].append(l)
    for l in g["links"]:
        if l["rel"] == "parent":
            fam = next((k for k, f in fams.items() if l["a"] in f["spouses"]), None)
            if fam is None:
                fam = (l["a"],)
                fams.setdefault(fam, {"spouses": {l["a"]}, "children": set(), "notes": []})
            fams[fam]["children"].add(l["b"])
            fams[fam]["notes"].append(l)
    for i, (k, f) in enumerate(fams.items()):
        out.append(f"0 @F{i + 1}@ FAM")
        for j, sp in enumerate(sorted(f["spouses"])):
            out.append(f"1 {'HUSB' if j == 0 else 'WIFE'} {ids.get(sp, '@I0@')}")
        for c in sorted(f["children"]):
            out.append(f"1 CHIL {ids.get(c, '@I0@')}")
        for n in f["notes"]:
            out.append(f"1 NOTE {n['rel']} link, tier {n['tier']}: " + "; ".join(e.get('cite', '') for e in n.get("evidence", [])))
    out.append("0 TRLR")
    return ("\n".join(out) + "\n").encode()


def genealogy_import_gedcom(project, text, filename):
    """Imported facts arrive as unconfirmed, tagged with their origin — never as gospel."""
    indi, fams, cur = {}, [], None
    for line in text.splitlines():
        m = re.match(r"^(\d+)\s+(@[^@]+@\s+)?(\w+)\s*(.*)$", line.strip())
        if not m:
            continue
        lvl, xref, tag, val = int(m.group(1)), (m.group(2) or "").strip(), m.group(3), m.group(4)
        if lvl == 0:
            cur = {"x": xref, "tag": tag}
            if tag == "INDI":
                indi[xref] = {"name": ""}
            elif tag == "FAM":
                cur["spouses"], cur["children"] = [], []
                fams.append(cur)
        elif cur and cur["tag"] == "INDI" and tag == "NAME" and not indi[cur["x"]]["name"]:
            indi[cur["x"]]["name"] = val.replace("/", "").strip()
        elif cur and cur["tag"] == "FAM" and tag in ("HUSB", "WIFE"):
            cur["spouses"].append(val)
        elif cur and cur["tag"] == "FAM" and tag == "CHIL":
            cur["children"].append(val)
    mine = _gload(project, "mine", {"people": {}, "links": {}, "merges": [], "notes": {}})
    known = {_lid(l["a"], l["rel"], l["b"]) for l in _gload(project, "derived", {"links": []})["links"]}
    mine["links"] = {**{k: None for k in known}, **mine["links"]}
    origin = f"GEDCOM import: {filename}"
    for x, p in indi.items():
        if p["name"]:
            mine["people"].setdefault(_pid(p["name"]), {"name": p["name"], "origin": origin})
    n = 0
    for f in fams:
        names = lambda xs: [indi[x]["name"] for x in xs if x in indi and indi[x]["name"]]
        sp = names(f["spouses"])
        for a in sp:
            for c in names(f["children"]):
                lid = _lid(_pid(a), "parent", _pid(c))
                mine["links"].setdefault(lid, {"a": _pid(a), "b": _pid(c), "rel": "parent", "tier": "unconfirmed",
                                               "evidence": [{"cite": origin, "quote": "listed as parent and child"}], "at": _now()}); n += 1
        if len(sp) == 2:
            lid = _lid(_pid(sp[0]), "spouse", _pid(sp[1]))
            mine["links"].setdefault(lid, {"a": _pid(sp[0]), "b": _pid(sp[1]), "rel": "spouse", "tier": "unconfirmed",
                                           "evidence": [{"cite": origin, "quote": "listed as a family"}], "at": _now()}); n += 1
    mine["links"] = {k: v for k, v in mine["links"].items() if v is not None}
    _gsave(project, "mine", mine)
    _ghistory(project, "imported GEDCOM", {"file": filename, "people": len(indi), "links": n})
    return genealogy_graph(project)

# ---------------------------------------------------------------- home (surfaces what exists; writes nothing)
def _daily(seq, salt, reroll=0):
    if not seq:
        return None
    base = random.Random(f"{datetime.now().date().isoformat()}:{salt}").randrange(len(seq))
    return seq[(base + reroll) % len(seq)]           # stable all day; each reroll steps to the next


def _lead_photo(project, st):
    raw = (project.root / st["file"]).read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(r'#(?:plate|photo|plate-pair)\(\s*"([^"]+)"', raw):
        rel = m.group(1).lstrip("/")
        if (project.root / rel).is_file():
            return rel
    return None


def _opening(project, st, n=3):
    raw = (project.root / st["file"]).read_text(encoding="utf-8", errors="ignore")
    text = _plain_story(st, raw, drop_bridges=True)
    body = next((para for para in text.split("\n\n") if len(para.split()) > 12), text)
    body = re.sub(r"\s+", " ", body)
    sentences = re.findall(r"[^.!?]+[.!?]+[”\"’']?", body)
    out = sentences[:n]
    while len(out) > 1 and (" ".join(out).count('"') % 2 or " ".join(out).count("“") != " ".join(out).count("”")):
        out = out[:-1]                                # never stop inside a quotation
    return " ".join(x.strip() for x in out) or body[:400]


def home_story(project, reroll=0):
    drafts = [st for st in engine_stories(project) if st["exists"]]
    st = _daily(drafts, "story", reroll)
    if not st:
        return None
    return {"id": st["id"], "title": st["title"], "dates": st["dates"], "photo": _lead_photo(project, st),
            "opening": _opening(project, st), "has_audio": st.get("has_audio"), "audio": st.get("audio"),
            "reading_minutes": st["reading_minutes"], "of": len(drafts)}


def _relationship(graph, subject, pid):
    """Neutral kinship words from the derived tree, or None when no traced path exists."""
    if not subject or subject == pid:
        return "the subject" if subject == pid else None
    up, down, side = {}, {}, {}
    for l in graph["links"]:
        if l["rel"] == "parent":
            up.setdefault(l["b"], []).append(l["a"]); down.setdefault(l["a"], []).append(l["b"])
        else:
            side.setdefault(l["a"], []).append((l["b"], l["rel"])); side.setdefault(l["b"], []).append((l["a"], l["rel"]))
    from collections import deque
    seen, q = {subject: []}, deque([subject])
    while q:
        cur = q.popleft()
        steps = [(n, "u") for n in up.get(cur, [])] + [(n, "d") for n in down.get(cur, [])] + \
                [(n, "s" if r == "spouse" else "b") for n, r in side.get(cur, [])]
        for n, k in steps:
            if n not in seen and len(seen[cur]) < 6:
                seen[n] = seen[cur] + [k]; q.append(n)
    path = "".join(seen.get(pid, [])) if pid in seen else None
    if path is None:
        return None
    def gen(n, word):
        return ("great-" * (n - 2) + "grand" + word) if n >= 2 else word
    if set(path) == {"u"}:
        return gen(len(path), "parent")
    if set(path) == {"d"}:
        return gen(len(path), "child")
    if path in ("s",):
        return "spouse"
    if path in ("b", "ud"):
        return "sibling"
    if re.fullmatch(r"u+b", path) or re.fullmatch(r"u+ud", path):
        return "sibling of a " + gen(len(path) - (1 if path.endswith("b") else 2), "parent") if len(path) > 2 else "aunt or uncle"
    if re.fullmatch(r"u+s", path):
        return "spouse of a " + gen(len(path) - 1, "parent")
    return "relative (" + " → ".join({"u": "parent", "d": "child", "s": "spouse", "b": "sibling"}[c] for c in path) + ")"


def _infobox_get(art, key, default=""):
    """An article's infobox value. Infoboxes are a {field: value} dict in Lineage's own articles and a
    list of [field, value] pairs (or {"k":..., "v":...} rows) in articles imported from older projects."""
    box = (art or {}).get("infobox") or {}
    if isinstance(box, dict):
        return box.get(key, default)
    for row in box:
        if isinstance(row, dict):
            k, v = row.get("k") or row.get("key") or row.get("label"), row.get("v") or row.get("value")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            k, v = row[0], row[1]
        else:
            continue
        if str(k).strip().lower() == key.lower():
            return v
    return default


def home_relative(project, reroll=0):
    graph = genealogy_graph(project)
    people = graph["people"] or [{"id": _pid(a["title"]), "name": a["title"], "dates": "", "article": a["slug"], "photo": None,
                                  "n_sources": 0, "has_story": False}
                                 for a in engine_familypedia(project) if a["type"] == "person"]
    if not people:
        return None
    nudge = [p for p in people if not p.get("has_story") and (p.get("n_sources") or p.get("article"))]
    p = _daily(nudge or people, "relative", reroll)
    art = None
    if p.get("article"):
        try:
            art = engine_article(project, p["article"])
        except KeyError:
            art = None
    photos = sum(1 for r in intake_load(project).values() if not r.get("trashed") and r.get("kind") == "image"
                 and not is_illustration(r) and p.get("name") in (effective(r).get("people") or []))
    return {"id": p["id"], "name": p.get("name"), "dates": p.get("dates") or _infobox_get(art, "dates"),
            "photo": p.get("photo"), "relationship": _relationship(graph, graph.get("subject"), p["id"]),
            "line": (art or {}).get("lead", ""), "article": p.get("article"),
            "counts": {"sources": p.get("n_sources", 0), "mentions": len((art or {}).get("mentions", [])), "photographs": photos},
            "has_story": p.get("has_story"), "nudge": bool(nudge) and p in nudge}


def _questions(project):
    pth = project.root / "data" / "questions.json"
    return json.loads(pth.read_text()) if pth.exists() else []


def home_needs(project):
    """Specific, one-click things, ordered by what they unblock."""
    items = []
    stories = engine_stories(project)
    br = [s for s in stories if s.get("bridges")]
    if br:
        n = sum(s["bridges"] for s in br)
        items.append({"weight": 90, "text": f"{n} bridge{'s' if n != 1 else ''} awaiting approval in {len(br)} stor{'y' if len(br) == 1 else 'ies'}",
                      "action": "review", "go": "#stories?filter=bridges"})
    rows = [r for r in intake_load(project).values() if not r.get("trashed")]
    pending = [r for r in rows if (r.get("stages") or {}).get("index", {}).get("state") != "done"]
    loose = []
    srcdir = project.root / "sources"
    if srcdir.is_dir():
        known = {r["path"] for r in intake_load(project).values()}
        loose = [f for f in srcdir.rglob("*") if f.is_file() and not f.name.startswith(".")
                 and ".trash" not in f.parts and f.relative_to(project.root).as_posix() not in known]
    if pending or loose:
        n = len(pending) + len(loose)
        items.append({"weight": 80, "text": f"{n} source{'s' if n != 1 else ''} not yet ingested", "action": "ingest",
                      "go": "#sources?filter=pending", "op": "ingest-all"})
    queue = family_view(project).get("review_queue") or []
    for q in queue[:3]:
        items.append({"weight": 85, "text": f"{q.get('by', 'A contributor')}'s upload is waiting for review", "action": "review queue",
                      "go": "#/settings/contributors"})
    stale = [s for s in stories if s.get("stale")]
    if stale:
        items.append({"weight": 70, "text": f"{len(stale)} stor{'y is' if len(stale) == 1 else 'ies are'} stale since you added a source",
                      "action": "regenerate", "go": "#stories?filter=stale"})
    if genealogy_diff(project).get("pending"):
        items.append({"weight": 65, "text": "A rebuilt family tree is waiting for your review", "action": "review", "go": "#genealogy?review=1"})
    tl = engine_timeline(project)
    conf = [e for e in tl["events"] if e.get("conflict")]
    if conf:
        items.append({"weight": 50, "text": f"{len(conf)} timeline event{'s' if len(conf) != 1 else ''} with conflicting sources",
                      "action": "review", "go": "#timeline?filter=conflicts"})
    tagged = set()
    for r in rows:
        if r.get("kind") == "image":
            tagged |= set(effective(r).get("people") or [])
    persons = [a["title"] for a in engine_familypedia(project) if a["type"] == "person"]
    nophoto = [x for x in persons if x not in tagged]
    if nophoto:
        items.append({"weight": 30, "text": f"{len(nophoto)} {'person has' if len(nophoto) == 1 else 'people have'} no photograph",
                      "action": "tag photos", "go": "#sources?kind=image"})
    asked = {q["text"] for q in _questions(project)}
    for g in tl["gaps"]:
        text = f"Nothing recorded between {g['from']} and {g['to']}"
        if text not in asked:
            items.append({"weight": 40 - min(g["to"] - g["from"], 30) / 100, "text": text, "action": "add to question list",
                          "op": "question", "question": f"What happened between {g['from']} and {g['to']}?", "source": f"timeline gap {g['from']}–{g['to']}"})
    items.sort(key=lambda x: -x["weight"])
    return items


def _requests(project):
    pth = project.root / "data" / "requests.json"
    return json.loads(pth.read_text()) if pth.exists() else []


def _save_requests(project, data):
    (project.root / "data").mkdir(exist_ok=True)
    (project.root / "data" / "requests.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))


def request_draft(project, kind, about=None, to=None):
    """Assemble a question list from what the project already flags as open. Nothing invented."""
    qs = []
    if kind == "person":
        a = next((x for x in engine_familypedia(project) if x["slug"] == about or x["title"] == about), None)
        if not a:
            raise KeyError("no article for that person")
        art = engine_article(project, a["slug"])
        qs += art.get("open_questions", [])
        g = genealogy_graph(project)
        pid = _pid(a["title"])
        if g["people"] and not any(l["rel"] == "parent" and l["b"] == pid for l in g["links"]):
            qs.append(f"Who were {a['title']}'s parents?")
        for l in g["links"]:
            if pid in (l["a"], l["b"]) and l["tier"] in ("lore", "unconfirmed"):
                other = l["b"] if l["a"] == pid else l["a"]
                other = next((x.get("name") for x in g["people"] if x["id"] == other), other)
                qs.append(f"Is there anything that confirms the {l['rel']} link between {a['title']} and {other}?")
        tl = engine_timeline(project)
        mine = [e for e in tl["events"] if a["title"] in e["people"]]
        for x, y in zip(mine, mine[1:]):
            if y["year"] - x["year"] >= 6:
                qs.append(f"What was {a['title']} doing between {x['year']} and {y['year']}?")
        title = f"More about {a['title']}"
    elif kind == "source":
        tl = engine_timeline(project)
        for e in tl["events"]:
            if e.get("conflict"):
                qs.append(f"A document that settles: {e['title']} ({e['date']}) — {e['conflict']}")
            elif e.get("confidence") == "low":
                qs.append(f"Any record of: {e['title']} ({e['date']})")
        g = genealogy_graph(project)
        nm = {x["id"]: x.get("name") or x["id"] for x in g["people"]}
        for l in g["links"]:
            if l["tier"] in ("lore", "told"):
                qs.append(f"A record of the {l['rel']} link between {nm.get(l['a'], l['a'])} and {nm.get(l['b'], l['b'])} (now {l['tier']})")
        tagged = set()
        for r in intake_load(project).values():
            if r.get("kind") == "image" and not r.get("trashed"):
                tagged |= set(effective(r).get("people") or [])
        for a in engine_familypedia(project):
            if a["type"] == "person" and a["title"] not in tagged:
                qs.append(f"A photograph of {a['title']}")
            elif a["type"] == "place" and not a.get("stub"):
                qs.append(f"A photograph of {a['title']}")
        title = "Missing sources"
    else:
        raise ValueError("kind must be person or source")
    qs = list(dict.fromkeys(qs))[:12]
    member = None
    if to:
        member = next((m for m in family_load(project)["members"] if m["id"] == to or m["name"] == to), None)
    return {"kind": kind, "about": about, "to": member["id"] if member else None, "to_name": member["name"] if member else None,
            "to_email": member.get("email") if member else None, "title": title, "questions": qs}


def request_save(project, draft):
    data = _requests(project)
    draft = {**draft, "id": secrets.token_hex(4), "made": _now(), "status": "asked"}
    data.append(draft)
    _save_requests(project, data)
    return draft


def request_mark(project, rid, status):
    if status not in ("asked", "answered"):
        raise ValueError("status is asked or answered")
    data = _requests(project)
    for r in data:
        if r["id"] == rid:
            r["status"] = status
            r[f"{status}_at"] = _now()
    _save_requests(project, data)
    return data


def _pdf_pages(path):
    if not path.exists():
        return None
    if shutil.which("pdfinfo"):
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        if m:
            return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page[^s]", path.read_bytes())) or None


def home_glance(project):
    rows = [r for r in intake_load(project).values() if not r.get("trashed")]
    stories = engine_stories(project)
    tl = engine_timeline(project)
    arch = project.root / "data" / "archives.csv"
    records = sum(1 for _ in csv.DictReader(open(arch, encoding="utf-8"))) if arch.exists() else 0
    g = genealogy_graph(project)
    people = len(g["people"]) or sum(1 for a in engine_familypedia(project) if a["type"] == "person")
    years = [e["year"] for e in tl["events"]]
    return {"sources": len(rows) or len(engine_sources(project)), "people": people,
            "stories": sum(1 for s in stories if s["exists"]), "photographs": sum(1 for r in rows if r.get("kind") == "image"),
            "records": records, "events": len(tl["events"]) + len(tl["undated"]),
            "words": sum(s["words"] for s in stories), "audio_minutes": round(sum((s.get("audio_duration") or 0) for s in stories) / 60),
            "range": [min(years), max(years)] if years else None,
            "pages": _pdf_pages(project.root / "output" / "book-draft.pdf")}


def home_activity(project, limit=25):
    feed = []
    for r in intake_load(project).values():
        for h in r.get("history", []):
            feed.append({"at": h["at"], "by": h.get("by", "me"), "text": f"{h['event']}: {r['original_name']}",
                         "go": f"#sources?open={r['id']}"})
    for st in engine_stories(project):
        if st.get("mtime"):
            feed.append({"at": datetime.fromtimestamp(st["mtime"], timezone.utc).isoformat(timespec="seconds"), "by": "",
                         "text": f"story written or revised: {st['title']}", "go": f"#stories?read={st['id']}"})
        if st.get("audio_made"):
            feed.append({"at": st["audio_made"], "by": "", "text": f"narrated: {st['title']}", "go": f"#stories?listen={st['id']}"})
    for h in _gload(project, "history", []):
        feed.append({"at": h["at"], "by": h.get("by", "me"), "text": f"family tree: {h['event']}", "go": "#genealogy"})
    for q in _requests(project):
        feed.append({"at": q["made"], "by": "me", "text": f"asked{(' ' + q['to_name']) if q.get('to_name') else ''}: {q['title']}", "go": "#home"})
    for m in family_load(project)["members"]:
        if m.get("joined"):
            feed.append({"at": m["joined"], "by": m["name"], "text": f"{m['name']} joined as {m.get('role', 'contributor')}",
                         "go": "#/settings/contributors"})
    fp = project.root / "data" / "familypedia"
    if fp.is_dir():
        for f in fp.glob("*.json"):
            feed.append({"at": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"), "by": "me",
                         "text": f"edited article: {f.stem.replace('-', ' ')}", "go": f"#familypedia/{f.stem}"})
    feed.sort(key=lambda x: x["at"], reverse=True)
    return feed[:limit]


def attention(project):
    """Why the settings gear shows a dot."""
    out = []
    keys = load_config()["keys"]
    if not keys.get("anthropic"):
        out.append({"section": "connectors", "text": "No Anthropic key: intake and the tree run without the model"})
    drive = (project.read()["settings"].get("drive_folder") or "")
    if drive and not GOOGLE_TOKEN_FILE.exists():
        out.append({"section": "connectors", "text": "Google Drive is set up for this project but not connected"})
    if family_view(project).get("review_queue"):
        out.append({"section": "contributors", "text": "A contributor's upload is awaiting review"})
    return out


def engine_home(project, reroll_story=0, reroll_relative=0):
    glance = home_glance(project)
    transcripts = list((project.root / "transcript").glob("clean/*.md"))
    empty = not (glance["sources"] or glance["stories"] or glance["people"] or transcripts)
    if empty:
        return {"empty": True}
    feed = home_activity(project)
    reqs = _requests(project)
    return {"empty": False, "story": home_story(project, reroll_story), "relative": home_relative(project, reroll_relative),
            "needs": home_needs(project), "glance": glance, "activity": feed, "updated": feed[0]["at"] if feed else None,
            "requests": sorted(reqs, key=lambda r: r["made"], reverse=True)[:10],
            "members": [{"id": m["id"], "name": m["name"], "email": m.get("email")} for m in family_load(project)["members"]],
            "attention": attention(project)}

# ---------------------------------------------------------------- narration (ElevenLabs)
# One story is one episode. The script is the story's own prose; an unapproved bridge is
# never read aloud, so narration refuses until it is approved.
TTS_MODEL = "eleven_multilingual_v2"


def _story_by_id(project, story_id):
    return next((x for x in engine_stories(project) if x["id"] == str(story_id)), None)


def _balanced(text, start):
    """Index just past the bracket group that opens at text[start] ('(' or '[')."""
    pairs = {"(": ")", "[": "]"}
    open_c, close_c, depth, i = text[start], pairs[text[start]], 0, start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2; continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def story_script(project, story_id):
    """Plain spoken text of a story: comments, layout calls, plates, records and descent removed."""
    st = _story_by_id(project, story_id)
    if not st or not st["exists"]:
        raise RuntimeError("this story has no text yet")
    raw = (project.root / st["file"]).read_text(encoding="utf-8")
    if st["bridges"]:
        raise PermissionError(f"approve {st['bridges']} bridge{'s' if st['bridges'] != 1 else ''} first: an unapproved bridge is never narrated")
    return st, _plain_story(st, raw)


def _plain_story(st, raw, drop_bridges=False):
    if st["file"].endswith(".md"):
        if drop_bridges:
            raw = re.sub(r"⟦BRIDGE: .*?⟧", "", raw)
        text = re.sub(r"^#+\s*", "", raw, flags=re.M)
        return re.sub(r"[*_`]", "", text).strip()
    raw = re.sub(r"(?m)^\s*//.*$", "", raw)
    out, i = [], 0
    drop = ("show", "import", "plate", "plate-pair", "photo", "descent", "records", "photo-addendum", "idx", "idx-see", "note", "set", "let") \
        + (("bridge",) if drop_bridges else ())
    while i < len(raw):
        m = re.compile(r"#([a-zA-Z][\w-]*)").match(raw, i)
        if raw[i] == "#" and m:
            name, j = m.group(1), m.end()
            if name == "sectionbreak":
                out.append("\n\n"); i = j; continue
            if name in ("show", "import", "set", "let"):
                nl = raw.find("\n", j); seg_end = len(raw) if nl < 0 else nl
                # a multi-line call: skip its bracket group
                k = raw.find("(", j, seg_end)
                i = _balanced(raw, k) if k >= 0 else seg_end
                continue
            groups = []
            while j < len(raw) and raw[j] in "([":
                end = _balanced(raw, j)
                groups.append(raw[j:end]); j = end
            if name in drop:
                i = j; continue
            out.append(" ".join(g[1:-1] for g in groups if g.startswith("[")))
            i = j; continue
        out.append(raw[i]); i += 1
    text = "".join(out)
    text = re.sub(r"\\([#\[\]*_$@])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text


def _audio_paths(project, st):
    slug = re.sub(r"[^a-z0-9]+", "-", st["title"].lower()).strip("-") or f"story-{st['id']}"
    base = project.root / "output" / "audio" / f"{int(st['id']):02d}-{slug}" if str(st["id"]).isdigit() else project.root / "output" / "audio" / slug
    return base.with_suffix(".mp3"), base.with_suffix(".json")


def story_audio_info(project, st):
    mp3, meta = _audio_paths(project, st)
    if not mp3.exists():
        return {"has_audio": False}
    m = json.loads(meta.read_text()) if meta.exists() else {}
    stale = None
    try:
        _, text = story_script(project, st["id"])
        stale = m.get("text_sha") != _sha256_bytes(text.encode())
    except Exception:
        stale = True
    return {"has_audio": True, "audio": mp3.relative_to(project.root).as_posix(), "audio_duration": m.get("duration"),
            "audio_stale": stale, "audio_voice": m.get("voice_name"), "audio_made": m.get("made")}


def story_voices(project):
    p = project.root / "data" / "story_voices.json"
    return json.loads(p.read_text()) if p.exists() else {}


def engine_narrate(project, story_id, voice_id=None):
    key = load_config()["keys"].get("elevenlabs")
    if not key:
        raise RuntimeError("Add an ElevenLabs key in Connectors to narrate")
    st, text = story_script(project, story_id)
    s = project.read()["settings"]
    voice_id = voice_id or story_voices(project).get(str(story_id)) or s.get("voice_id")
    if not voice_id:
        raise RuntimeError("choose a voice at the top of the Stories tab first")
    paras, chunks, cur = text.split("\n\n"), [], ""
    for para in paras:                                  # requests stay well under the model's limit
        if len(cur) + len(para) > 4500 and cur:
            chunks.append(cur); cur = ""
        cur = (cur + "\n\n" + para).strip()
    if cur:
        chunks.append(cur)
    audio = b""
    for c in chunks:
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                                     data=json.dumps({"text": c, "model_id": TTS_MODEL}).encode(), method="POST",
                                     headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                audio += r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"ElevenLabs said {e.code}: {e.read().decode(errors='replace')[:200]}")
    mp3, meta = _audio_paths(project, st)
    mp3.parent.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(audio)
    voice_name = next((v["name"] for v in list_voices(key)[0] if v["voice_id"] == voice_id), voice_id)
    meta.write_text(json.dumps({"story": st["id"], "title": st["title"], "voice_id": voice_id, "voice_name": voice_name,
                                "chars": len(text), "text_sha": _sha256_bytes(text.encode()), "model": TTS_MODEL,
                                "made": _now(), "duration": media_duration(mp3)}, indent=1))
    return {"audio": mp3.relative_to(project.root).as_posix(), "chars": len(text), "duration": media_duration(mp3)}


def engine_audio_zip(project):
    """Every narrated story as one zip with a simple chapter list, in book order."""
    import io, zipfile
    buf = io.BytesIO()
    lines = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for st in sorted(engine_stories(project), key=lambda x: (x["year"] or 9999, x["id"])):
            info = story_audio_info(project, st)
            if info.get("has_audio"):
                f = project.root / info["audio"]
                z.write(f, f.name)
                lines.append(f"{f.name}\t{st['title']}\t{st['dates']}")
        z.writestr("chapters.txt", "\n".join(lines) + "\n")
    return buf.getvalue()

# ---------------------------------------------------------------- Familypedia
# Articles are built only from the project's own material: units, the timeline, transcripts,
# sources. My edits live in data/familypedia/<slug>.json and always survive a rebuild.
def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _unit_frontmatter(project):
    out = []
    for p, text in _texts(project, ["content/units/*.md"]):
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            continue
        fm = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
        lists = {}
        for k in ("people", "places", "timeline_events"):
            v = fm.get(k, "[]")
            lists[k] = re.findall(r'"([^"]+)"', v)
        shaped = m.group(2).split("## Shaped", 1)[1].split("## Notes", 1)[0] if "## Shaped" in m.group(2) else ""
        out.append({"id": fm.get("id", p.stem), "title": fm.get("title", "").strip('"'), "chapter": fm.get("chapter", ""),
                    "people": lists["people"], "places": lists["places"], "events": lists["timeline_events"], "shaped": shaped})
    return out


def _mention_key(article, transcripts):
    """What to search the transcripts for: the full name, else (for people) the first name."""
    key = article["title"].split(",")[0].strip()
    if article["type"] == "person" and key not in transcripts:
        first = key.split()[0] if key.split() else ""
        key = first if len(first) > 3 else key
    return key if len(key) > 3 else ""


def engine_familypedia(project):
    """Index of every article the project can support, with its type and how much material it has.
    The engine is app/familypedia.py: nine article types, built only from the project's material."""
    return familypedia.summaries(project)


def engine_article(project, slug):
    """One article: lead, infobox by type, tiers, passages, sources, records, photos, stories,
    related articles, backlinks, open questions and "Beyond the family"."""
    return familypedia.article(project, slug)


def engine_save_article(project, slug, patch):
    return familypedia.save_edit(project, slug, patch)

# ---------------------------------------------------------------- jobs (timed, with progress)
JOBS = {}


def run_job(job_id, steps, finish):
    """steps: list of (label, seconds). PROTOTYPE pacing; real work replaces the sleeps."""
    job = JOBS[job_id]
    try:
        for i, (label, secs) in enumerate(steps):
            job["step"] = label
            job["progress"] = int(i / max(len(steps), 1) * 100)
            time.sleep(secs)
        job["result"] = finish()
        job.update(progress=100, step="done", state="done")
    except Exception as e:
        job.update(state="error", step=f"{type(e).__name__}: {e}")


def start_job(steps, finish):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {"id": jid, "state": "running", "progress": 0, "step": steps[0][0], "result": None}
    threading.Thread(target=run_job, args=(jid, steps, finish), daemon=True).start()
    return jid


def demo_records(subject):
    """PROTOTYPE — stands in for the records-archives skill's archive sweep."""
    return [
        {"title": "Museum catalogue — person record", "where": "county historical collection",
         "detail": "Over seventy-five letters, 1862–1865, each with a transcription.", "confidence": "documented"},
        {"title": "Crew list, whaleship, 1851", "where": "American Offshore Whaling Voyages database",
         "detail": "Name entered by a clerk with a different spelling; age 18.", "confidence": "documented"},
        {"title": "Regimental roster, heavy artillery", "where": "state adjutant general, 1889",
         "detail": "Private, Company A — the family remembered a surgeon.", "confidence": "contradicts the family"},
        {"title": "Grave memorial", "where": "town cemetery", "detail": "Died 1921, aged 86.", "confidence": "documented"},
        {"title": "Local newspaper, 2018", "where": "town paper", "detail": "Feature on the letters going on display.", "confidence": "context"},
    ]


def demo_genealogy():
    return [
        {"gen": 1, "name": "The earliest ancestor", "years": "1805–1872", "note": "farmer, river valley", "tier": "documented"},
        {"gen": 2, "name": "The ancestor", "years": "1834–1921", "note": "whaler, policeman, soldier, farmer", "tier": "documented"},
        {"gen": 3, "name": "His daughter", "years": "1860–1933", "note": "married into another family", "tier": "documented"},
        {"gen": 4, "name": "The grandfather", "years": "1894–1967", "note": "heard the stories first-hand", "tier": "told"},
        {"gen": 5, "name": "His children", "years": "b. 1920 and 1921", "note": "", "tier": "told"},
        {"gen": 6, "name": "The narrator", "years": "b. 1943", "note": "the recordings", "tier": "witnessed"},
    ]


def demo_chapters(template):
    base = [
        {"n": 1, "title": "The ancestor", "part": "Those who came before", "years": "1834–1921",
         "summary": "Whaling at seventeen, a bridge in Hong Kong, two enlistments, tobacco.", "units": 7, "words": 2400, "tier": "lore + records"},
        {"n": 2, "title": "The grandfather", "part": "Those who came before", "years": "1894–1967",
         "summary": "The man who heard the stories and passed them down.", "units": 4, "words": 1300, "tier": "told"},
        {"n": 3, "title": "Childhood", "part": "A life", "years": "1943–1955",
         "summary": "The river towns, the mills, the crank phonograph in the front room.", "units": 6, "words": 2100, "tier": "witnessed"},
        {"n": 4, "title": "College", "part": "A life", "years": "1961–1965",
         "summary": "A scholarship, a chemistry major, and a board that wanted an explanation.", "units": 5, "words": 1800, "tier": "witnessed"},
        {"n": 5, "title": "The far north", "part": "A life", "years": "1971–1974",
         "summary": "Teaching in the village, the island, three winters.", "units": 8, "words": 2900, "tier": "witnessed"},
    ]
    if template == "album":
        base.append({"n": 6, "title": "Plates", "part": "A life", "years": "1925–1980",
                     "summary": "Thirty photographs with evidence-coded captions.", "units": 0, "words": 400, "tier": "mixed"})
    return base


def preview_text(style):
    """The preview chapter opening, with one bridge, in the chosen voice."""
    body = VOICE_SAMPLES.get(style, VOICE_SAMPLES["biographer"])
    return body + "\n\n⟦BRIDGE: years later, she still remembered the sound the ore cars made⟧"


STAGE_PROMPTS = {
    "research": "Using the records-archives skill, read every source in this project for names, places and dates, then "
                "search free public archives (census, military rosters, ship registers, newspapers, graves, museum catalogues) "
                "for records that corroborate or contradict the family's version. Cache what you find under facts/records/, "
                "add each to data/archives.csv with its verdict, and never send my personal details to any site.",
    "genealogy": "Using the family-history-chapters skill, build the line of descent from the sources and the records: every "
                 "person, every relationship, each link marked witnessed, told, documented or unconfirmed with its evidence. "
                 "Never infer a relationship from a surname or a date alone. Write it to data/genealogy.json and list the gaps.",
    "chapters": "Using the content-separator and chapter-index-builder skills, cut the transcripts into story units (with "
                "the coverage check) and propose a story map: each story with title, years, the units it uses and a one-line "
                "summary. Write data/chapters.csv with status proposed and stop for my approval. Batch your questions.",
    "generate": "Using the chapter-generator and memoir-style-guide skills, write the approved stories: quotes exact, every "
                "paragraph cited with // src:, anything you add as a #bridge. Build the draft and tell me what needs approval.",
    "podcast": "Write a spoken-word script for one episode from the first approved story, following the memoir-style-guide: "
               "quotes exact, no unapproved bridge read aloud. Save it to output/podcast-episode-01.md.",
}


class StageIsTerminalWork(Exception):
    """Outside --demo, pipeline stages are real work done by the Genealogist in the terminal."""
    def __init__(self, prompt):
        super().__init__(prompt)
        self.prompt = prompt


def engine_run(project, stage):
    """Start a pipeline stage as a job. Returns a job id."""
    if stage in STAGE_PROMPTS and not DEMO:
        raise StageIsTerminalWork(STAGE_PROMPTS[stage])
    state = project.read()
    settings = state["settings"]
    root = project.root
    if stage == "research":
        def finish():
            recs = demo_records(state.get("subject", ""))
            (root / "data" / "records.json").write_text(json.dumps(recs, indent=2))
            project.mark("research", "done", records="data/records.json")
            return {"records": recs}
        return start_job([("Reading the sources", 1.0), ("Pulling names, places and dates", 1.2),
                          ("Searching public archives", 1.6), ("Matching candidates", 1.2),
                          ("Scoring and writing THE RECORDS", 1.0)], finish)
    if stage == "genealogy":
        def finish():
            tree = demo_genealogy()
            (root / "data" / "genealogy.json").write_text(json.dumps(tree, indent=2))
            project.mark("genealogy", "done", genealogy="data/genealogy.json")
            return {"tree": tree}
        return start_job([("Reading the records", 0.8), ("Resolving relationships", 1.4),
                          ("Marking confirmed and unconfirmed links", 1.0), ("Drawing the line of descent", 0.8)], finish)
    if stage == "chapters":
        def finish():
            chs = demo_chapters(settings.get("chapter_template", "ancestor"))
            (root / "data" / "chapters.json").write_text(json.dumps(chs, indent=2))
            project.mark("chapters", "proposed", chapters="data/chapters.json")
            return {"chapters": chs, "preview": preview_text(settings.get("narrative_style", "biographer"))}
        return start_job([("Cutting the source into story units", 1.6), ("Dating what can be dated", 1.2),
                          ("Grouping by person and era", 1.2), ("Drafting a preview chapter", 1.6)], finish)
    if stage == "generate":
        def finish():
            f = root / "data" / "chapters.json"
            chs = json.loads(f.read_text()) if f.exists() else demo_chapters("ancestor")
            style = settings.get("narrative_style", "biographer")
            for ch in chs:
                slug = re.sub(r"[^a-z0-9]+", "-", ch["title"].lower()).strip("-")
                (root / "chapters" / f"{ch['n']:02d}-{slug}.md").write_text(
                    f"# {ch['title']}\n\n_{ch['years']} · {ch['tier']}_\n\n{preview_text(style)}\n")
            project.mark("generate", "done", chapters_dir="chapters/")
            return {"written": len(chs), "bridges": len(chs),
                    "note": "Each chapter carries one unapproved bridge — the final build will refuse until you clear them."}
        return start_job([("Shaping units into prose", 2.0), ("Checking every quote against the transcript", 1.4),
                          ("Citing each paragraph", 1.0), ("Assembling chapters", 1.2), ("Marking index terms", 0.8)], finish)
    if stage == "podcast":
        def finish():
            voice = settings.get("voice_name") or "the selected voice"
            script = root / "output" / "podcast-episode-01.md"
            script.write_text(f"# Episode 1 — {state.get('title') or 'The ancestor'}\n\nVoice: {voice}\n\n"
                              f"{preview_text(settings.get('narrative_style', 'biographer'))}\n")
            project.mark("podcast", "done", podcast_script=str(script.relative_to(root)))
            have_key = bool(load_config()["keys"].get("elevenlabs"))
            return {"script": str(script.relative_to(root)), "audio": None,
                    "note": "Script written. Audio rendering is wired to ElevenLabs here — "
                            + ("key present, add the render call to ship audio." if have_key else "add an ElevenLabs key to render audio.")}
        return start_job([("Selecting the episode's stories", 1.0), ("Writing a spoken-word script", 1.6),
                          ("Marking pauses and emphasis", 0.8), ("Preparing the voice request", 1.0)], finish)
    if stage == "sync":
        return start_job([("Contacting Google Drive", 0.2)], lambda: drive_sync(project))
    raise ValueError(f"unknown stage {stage}")


# =========================================================================================
# AUTHOR-ONLY SURFACE — keys and connectors, repo and Drive settings, agent CLIs, terminal.
# A future non-technical front end should not expose anything in this section.
# =========================================================================================
PROVIDERS = {
    "anthropic": {"label": "Anthropic", "use": "Writing (Claude)", "prefix": "sk-ant-",
                  "check": ("https://api.anthropic.com/v1/models",
                            lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"})},
    "openai": {"label": "OpenAI", "use": "Illustrations", "prefix": "sk-",
               "check": ("https://api.openai.com/v1/models", lambda k: {"Authorization": f"Bearer {k}"})},
    "elevenlabs": {"label": "ElevenLabs", "use": "Podcast voice", "prefix": "",
                   "check": ("https://api.elevenlabs.io/v1/voices", lambda k: {"xi-api-key": k})},
    "github": {"label": "GitHub", "use": "Push the lineage repo", "prefix": "",
               "check": ("https://api.github.com/user",
                         lambda k: {"Authorization": f"Bearer {k}", "Accept": "application/vnd.github+json",
                                    "User-Agent": "Lineage"})},
}

DEMO_VOICES = [
    {"voice_id": "demo-warm", "name": "Marlowe — warm, unhurried (stand-in)", "preview_url": None},
    {"voice_id": "demo-plain", "name": "Hale — plain, documentary (stand-in)", "preview_url": None},
    {"voice_id": "demo-older", "name": "Juniper — older, close-mic (stand-in)", "preview_url": None},
]

AGENT_CLIS = [("claude", "Claude Code"), ("codex", "Codex CLI"), ("gemini", "Gemini CLI"), ("aider", "Aider"),
              ("opencode", "opencode"), ("goose", "Goose"), ("cursor-agent", "Cursor Agent"),
              ("amp", "Amp"), ("qwen", "Qwen Code"), ("crush", "Crush")]
SHELLS = [("bash", "bash"), ("zsh", "zsh")]


def check_key(provider, key):
    spec = PROVIDERS.get(provider)
    if not spec:
        return {"ok": False, "detail": "unknown provider"}
    if spec["prefix"] and not key.startswith(spec["prefix"]):
        return {"ok": False, "detail": f"expected a key starting {spec['prefix']}"}
    url, headers = spec["check"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers(key)), timeout=12) as r:
            body = json.loads(r.read().decode())
        detail = "connected"
        if provider == "github" and isinstance(body, dict) and body.get("login"):
            detail = f"connected as {body['login']}"
        return {"ok": True, "detail": detail, "body": body}
    except urllib.error.HTTPError as e:
        return {"ok": False, "detail": f"rejected ({e.code}) — check the key"}
    except Exception as e:
        return {"ok": None, "detail": f"could not reach the service ({type(e).__name__}); key saved unverified"}


def list_voices(key):
    if not key:
        return (DEMO_VOICES if DEMO else []), False
    res = check_key("elevenlabs", key)
    voices = (res.get("body") or {}).get("voices") if res.get("ok") else None
    if not voices:
        return (DEMO_VOICES if DEMO else []), False
    return [{"voice_id": v.get("voice_id"), "name": v.get("name", "voice"),
             "preview_url": v.get("preview_url")} for v in voices][:60], True


def detect_clis():
    found = []
    for exe, label in AGENT_CLIS:
        p = shutil.which(exe)
        if p:
            found.append({"command": exe, "label": label, "path": p, "kind": "agent"})
    for exe, label in SHELLS:
        p = shutil.which(exe)
        if p:
            found.append({"command": exe, "label": label, "path": p, "kind": "shell"})
    return found


def gh_status():
    if not shutil.which("gh"):
        return {"installed": False}
    try:
        r = subprocess.run(["gh", "auth", "status", "--hostname", "github.com"], capture_output=True, text=True, timeout=10)
        out = r.stdout + r.stderr
        m = re.search(r"account (\S+)", out) or re.search(r"as (\S+)", out)
        return {"installed": True, "logged_in": r.returncode == 0, "account": m.group(1) if m else None}
    except Exception:
        return {"installed": True, "logged_in": False}


def git(path, *args, timeout=15):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=timeout)


def repo_status(path):
    p = Path(path).expanduser()
    if not p.exists():
        return {"exists": False, "path": str(p)}
    if not p.is_dir():
        return {"exists": True, "is_dir": False, "path": str(p)}
    if not shutil.which("git"):
        return {"exists": True, "is_dir": True, "git": None, "detail": "git is not installed", "path": str(p)}
    r = git(p, "rev-parse", "--show-toplevel")
    if r.returncode:
        return {"exists": True, "is_dir": True, "git": False, "path": str(p)}
    remote = git(p, "remote", "get-url", "origin").stdout.strip() or None
    branch = git(p, "branch", "--show-current").stdout.strip() or "(detached)"
    dirty = [l for l in git(p, "status", "--porcelain").stdout.splitlines() if l.strip()]
    return {"exists": True, "is_dir": True, "git": True, "path": str(p), "toplevel": r.stdout.strip(),
            "remote": remote, "branch": branch, "dirty": len(dirty)}


# ---------------------------------------------------------------- Google Drive
# Device flow only grants drive.file: Lineage sees files it created, so it can push outputs but
# cannot read an existing folder. Browser sign-in (loopback redirect) grants drive.readonly +
# drive.file and can read the folder. Both store the token in ~/.lineage/, never the project.
GOOGLE_DEVICE = {}
GOOGLE_PKCE = {}
DEVICE_SCOPES = "https://www.googleapis.com/auth/drive.file"
BROWSER_SCOPES = "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file"


def _post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"http {e.code}"}
    except Exception as e:
        return {"error": type(e).__name__}


def save_google_token(tok, scopes):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
    tok["scopes"] = scopes
    old = json.loads(GOOGLE_TOKEN_FILE.read_text()) if GOOGLE_TOKEN_FILE.exists() else {}
    if "refresh_token" not in tok and old.get("refresh_token"):
        tok["refresh_token"] = old["refresh_token"]
    GOOGLE_TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    os.chmod(GOOGLE_TOKEN_FILE, 0o600)


def google_access_token():
    if not GOOGLE_TOKEN_FILE.exists():
        return None
    tok = json.loads(GOOGLE_TOKEN_FILE.read_text())
    if tok.get("expires_at", 0) > time.time():
        return tok["access_token"]
    g = load_config()["google"]
    if not tok.get("refresh_token") or not g.get("client_id"):
        return None
    new = _post_form("https://oauth2.googleapis.com/token", {
        "client_id": g["client_id"], "client_secret": g.get("client_secret", ""),
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    if "access_token" not in new:
        return None
    save_google_token(new, tok.get("scopes", ""))
    return new["access_token"]


def drive_api(path, params=None, method="GET", data=None, headers=None, raw=False):
    at = google_access_token()
    if not at:
        raise RuntimeError("Google Drive is not connected")
    url = "https://www.googleapis.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {at}", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body if raw else json.loads(body.decode() or "{}")


def drive_folder_id(value):
    v = (value or "").strip()
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", v) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", v)
    if m:
        return m.group(1)
    return v if re.fullmatch(r"[A-Za-z0-9_-]{10,}", v) else None


def drive_status():
    g = load_config()["google"]
    tok = json.loads(GOOGLE_TOKEN_FILE.read_text()) if GOOGLE_TOKEN_FILE.exists() else {}
    return {"client_configured": bool(g.get("client_id")), "connected": bool(tok),
            "scopes": tok.get("scopes", ""), "can_read_folder": "drive.readonly" in tok.get("scopes", "")}


def drive_verify(folder):
    fid = drive_folder_id(folder)
    if not fid:
        return {"ok": False, "detail": "that doesn't look like a folder ID or folder URL"}
    if not google_access_token():
        return {"ok": None, "id": fid, "detail": "saved, unverified — connect Google Drive to check it"}
    try:
        meta = drive_api(f"/drive/v3/files/{fid}", {"fields": "id,name,mimeType", "supportsAllDrives": "true"})
        if meta.get("mimeType") != "application/vnd.google-apps.folder":
            return {"ok": False, "id": fid, "detail": f"{meta.get('name')} is not a folder"}
        return {"ok": True, "id": fid, "name": meta.get("name"), "detail": f"verified: {meta.get('name')}"}
    except urllib.error.HTTPError as e:
        hint = " (device-flow access only sees files Lineage created; use browser sign-in)" if e.code == 404 else ""
        return {"ok": False, "id": fid, "detail": f"Drive said {e.code}{hint}"}
    except Exception as e:
        return {"ok": None, "id": fid, "detail": f"could not reach Drive ({type(e).__name__})"}


def _drive_children(fid):
    q = f"'{fid}' in parents and trashed = false"
    res = drive_api("/drive/v3/files", {"q": q, "pageSize": 1000, "supportsAllDrives": "true",
                                       "includeItemsFromAllDrives": "true",
                                       "fields": "files(id,name,mimeType,size,modifiedTime)"})
    return res.get("files", [])


def _drive_subfolder(fid, name, create=False):
    for f in _drive_children(fid):
        if f["mimeType"] == "application/vnd.google-apps.folder" and f["name"].lower() == name.lower():
            return f["id"]
    if not create:
        return None
    meta = json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [fid]}).encode()
    return drive_api("/drive/v3/files", {"supportsAllDrives": "true", "fields": "id"}, "POST", meta,
                     {"Content-Type": "application/json"})["id"]


def drive_sync(project):
    """Sources: Drive → project (adds files that aren't here; never deletes or overwrites).
    Outputs: project → Drive (uploads output/ files missing from the Drive 'outputs' folder)."""
    s = project.read()["settings"]
    fid = drive_folder_id(s.get("drive_folder"))
    if not fid:
        raise RuntimeError("set a Drive folder in Settings first")
    if not (s.get("sync_sources") or s.get("sync_outputs")):
        raise RuntimeError("both sync directions are off — turn one on in Settings")
    report = {"downloaded": [], "uploaded": [], "skipped": []}
    dmap = drive_map(project)
    if s.get("sync_sources"):
        src_folder = _drive_subfolder(fid, "sources") or fid
        for f in _drive_children(src_folder):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                continue
            name = Path(f["name"]).name
            if f["mimeType"].startswith("application/vnd.google-apps."):
                name += ".txt"
            dest = project.root / "sources" / name
            if dest.exists():
                report["skipped"].append(name)
            else:
                if f["mimeType"].startswith("application/vnd.google-apps."):
                    data = drive_api(f"/drive/v3/files/{f['id']}/export", {"mimeType": "text/plain"}, raw=True)
                else:
                    data = drive_api(f"/drive/v3/files/{f['id']}", {"alt": "media", "supportsAllDrives": "true"}, raw=True)
                dest.write_bytes(data)
                report["downloaded"].append(name)
                intake_start(project, intake_adopt(project, dest.relative_to(project.root).as_posix())["id"])
            dmap[name] = f["id"]
    if s.get("sync_outputs"):
        out_folder = _drive_subfolder(fid, "outputs", create=True)
        existing = {f["name"]: f for f in _drive_children(out_folder)}
        for p in sorted((project.root / "output").glob("*")):
            if not p.is_file():
                continue
            if p.name in existing and int(existing[p.name].get("size", -1)) == p.stat().st_size:
                report["skipped"].append(p.name)
                continue
            boundary = "lineage" + secrets.token_hex(8)
            meta = json.dumps({"name": p.name, "parents": [out_folder]})
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                    f"--{boundary}\r\nContent-Type: {mimetypes.guess_type(p.name)[0] or 'application/octet-stream'}\r\n\r\n").encode() \
                + p.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            drive_api("/upload/drive/v3/files", {"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id"},
                      "POST", body, {"Content-Type": f"multipart/related; boundary={boundary}"})
            report["uploaded"].append(p.name)
    (project.root / ".lineage" / "drive_map.json").write_text(json.dumps(dmap, indent=1))
    return report


# ---------------------------------------------------------------- family (owner-only management)
# Members and invites live in <project>/.lineage/family.json. Until the project is hosted, an
# invite link only works on this machine; the server validates it, the UI says so.
FAMILY_ROLES = ("contributor", "reader", "editor")


def family_load(project):
    p = project.root / ".lineage" / "family.json"
    return json.loads(p.read_text()) if p.exists() else {"members": [], "invites": []}


def family_save(project, data):
    p = project.root / ".lineage" / "family.json"
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    os.chmod(p, 0o600)


def family_view(project):
    data = family_load(project)
    now = time.time()
    contributions = {}
    for row in engine_sources(project):
        by = (row.get("added_by") or "")
        if by:
            contributions[by] = contributions.get(by, 0) + 1
    for m in data["members"]:
        m["contributions"] = contributions.get(m["name"], 0)
        live = [i for i in data["invites"] if i["member"] == m["id"] and not i.get("revoked") and i["expires"] > now]
        m["invite"] = ({"url": f"http://127.0.0.1:{PORT}/join/{live[-1]['token']}",
                        "expires": datetime.fromtimestamp(live[-1]["expires"], timezone.utc).isoformat(timespec="minutes")}
                       if live else None)
    data["review_queue"] = []          # contributions from others land here first (none until hosted)
    data["roles"] = FAMILY_ROLES
    return data

# ---------------------------------------------------------------- terminal (a PTY per session)
class Terminal:
    """One shell-like session in a pseudo-terminal. This is a shell: localhost + token only."""
    MEM_CAP = 512 * 1024          # bytes of scrollback kept in memory
    LOG_CAP = 1024 * 1024         # bytes kept in <project>/.lineage/terminal.log

    def __init__(self):
        self.lock = threading.Lock()
        self.pid = self.fd = None
        self.status, self.detail, self.exit_code = "not started", "", None
        self.buf = bytearray()
        self.subs = []
        self.cols, self.rows = 100, 30
        self.log_path = None
        self.command = self.cwd = None

    # -- scrollback
    def attach(self, project_root):
        self.log_path = Path(project_root) / ".lineage" / "terminal.log"
        if self.pid is None:
            self.buf = bytearray(self.log_path.read_bytes()[-self.MEM_CAP:]) if self.log_path.exists() else bytearray()

    def scrollback(self):
        with self.lock:
            return bytes(self.buf)

    def _append(self, data):
        with self.lock:
            self.buf += data
            if len(self.buf) > self.MEM_CAP:
                del self.buf[: len(self.buf) - self.MEM_CAP]
            subs = list(self.subs)
        if self.log_path:
            try:
                with open(self.log_path, "ab") as fh:
                    fh.write(data)
                if self.log_path.stat().st_size > self.LOG_CAP:
                    self.log_path.write_bytes(self.log_path.read_bytes()[-self.LOG_CAP // 2:])
            except OSError:
                pass
        enc = base64.b64encode(data).decode()
        for q in subs:
            q.put(("data", enc))

    def _broadcast(self, kind, payload):
        with self.lock:
            subs = list(self.subs)
        for q in subs:
            q.put((kind, payload))

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.subs.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)

    def info(self):
        return {"status": self.status, "detail": self.detail, "exit_code": self.exit_code,
                "command": self.command, "cwd": self.cwd, "pid": self.pid}

    # -- lifecycle
    def start(self, command, cwd):
        self.stop_process()
        command = (command or "claude").strip()
        self.detail = ""
        try:
            argv = shlex.split(command)
        except ValueError as e:
            argv, self.detail = [], f"can't parse the command: {e}"
        self.command, self.cwd = command, str(cwd)
        if not argv or not shutil.which(argv[0]):
            self.status = "not configured"
            self.detail = self.detail or (f"`{argv[0] if argv else command}` is not on PATH — pick an agent CLI in "
                                          "Connectors or set the terminal command in Settings")
            self._broadcast("status", self.info())
            return False
        if not Path(cwd).is_dir():
            self.status, self.detail = "not configured", f"working folder {cwd} does not exist"
            self._broadcast("status", self.info())
            return False
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))
        env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", LINEAGE_PROJECT=str(cwd))
        pid = os.fork()
        if pid == 0:                                    # child: own session, the pty as its terminal
            try:
                # Signals ignored by this server (SIGINT when it was started in the background,
                # SIGPIPE which Python always ignores) would be inherited through exec, and then
                # Ctrl-C would do nothing in the terminal. Give the child the defaults.
                for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTSTP, signal.SIGTTIN, signal.SIGTTOU,
                            signal.SIGPIPE, signal.SIGHUP, signal.SIGTERM, signal.SIGCHLD, signal.SIGWINCH):
                    signal.signal(sig, signal.SIG_DFL)
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
                for fd in (0, 1, 2):
                    os.dup2(slave, fd)
                if slave > 2:
                    os.close(slave)
                os.close(master)
                os.chdir(cwd)
                os.execvpe(argv[0], argv, env)
            finally:
                os._exit(127)
        os.close(slave)
        self.pid, self.fd = pid, master
        self.status, self.exit_code = "running", None
        banner = f"\r\n\x1b[2m── {datetime.now().strftime('%Y-%m-%d %H:%M')} · {command} · {cwd} ──\x1b[0m\r\n"
        self._append(banner.encode())
        self._broadcast("status", self.info())
        threading.Thread(target=self._reader, args=(pid, master), daemon=True).start()
        return True

    def _reader(self, pid, fd):
        while True:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            self._append(data)
        try:
            _, st = os.waitpid(pid, 0)
            code = os.waitstatus_to_exitcode(st)
        except ChildProcessError:
            code = None
        try:
            os.close(fd)
        except OSError:
            pass
        if self.pid == pid:
            self.pid = self.fd = None
            self.status, self.exit_code = "exited", code
            self.detail = f"exited with code {code}" if code is not None else "exited"
            self._broadcast("status", self.info())

    def write(self, data: bytes):
        if self.fd is None:
            return False
        try:
            os.write(self.fd, data)
            return True
        except OSError:
            return False

    def resize(self, cols, rows):
        self.cols, self.rows = max(20, min(int(cols), 500)), max(5, min(int(rows), 200))
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))
            except OSError:
                pass

    def interrupt(self):
        """SIGINT to whatever is in the foreground, exactly like pressing Ctrl-C: the terminal's
        line discipline turns ^C into SIGINT for its foreground process group. (Don't ask the
        master side for that group: on macOS tcgetpgrp(master) returns 0, and killpg(0) would
        signal this server.)"""
        if self.fd is None:
            return False
        if self.write(b"\x03"):
            return True
        try:
            os.killpg(os.getpgid(self.pid), signal.SIGINT)   # the session leader's own group
        except OSError:
            return False
        return True

    def stop_process(self):
        pid = self.pid
        if pid is None:
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGHUP)
        except OSError:
            pass
        for _ in range(40):
            if self.pid != pid:
                return
            time.sleep(0.05)
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass

    def clear(self):
        with self.lock:
            self.buf = bytearray()
        if self.log_path and self.log_path.exists():
            self.log_path.write_bytes(b"")
        self._broadcast("clear", "")


TERMINAL = Terminal()

QUICK_PROMPTS = [
    {"label": "Who are the relatives in my sources?",
     "prompt": "Read every source in this project (transcripts in transcript/clean/ and anything in sources/). "
               "List every relative who is named or described: their name as said, how they relate to the "
               "subject, the timestamps where they come up, and whether each relationship is witnessed, told "
               "to the subject, or family lore. Flag spellings you are unsure of. Don't search the web yet."},
    {"label": "Search the public records for the oldest ancestor",
     "prompt": "Find the oldest ancestor named in the sources. Using the records-archives skill, search free "
               "public sources (census, military rosters, ship registers, newspapers, grave records, museum "
               "catalogues) for that person. For each hit give the record, where it lives, a link, and whether "
               "it corroborates or contradicts the family's version. Cache what you find under facts/records/. "
               "Never send my personal details to any site."},
    {"label": "Propose a chapter map",
     "prompt": "Using the chapter-index-builder skill, propose a chapter map for this book from the story "
               "units and the timeline: a family-history part and a life part, each chapter with title, years, "
               "the units it uses and a one-line summary. Write it to data/chapters.csv with status proposed and "
               "stop for my approval. Batch any questions."},
    {"label": "Draft a preview of chapter 1",
     "prompt": "Draft chapter 1 as a preview, following the memoir-style-guide skill exactly: third person, "
               "quotes exact from the transcript, every paragraph cited with // src:, anything you add as a "
               "#bridge. Build the draft PDF and tell me where it is and what you flagged for review."},
    {"label": "What's still unapproved?",
     "prompt": "List everything still waiting on me: unapproved bridges, // REVIEW: notes, open gates "
               "(speaker confirmation, chapter map, final sign-off) and the questions in facts/gaps.md. Group "
               "them by chapter and give file and line for each."},
]


# =========================================================================================
# HTTP
# =========================================================================================
class Handler(http.server.BaseHTTPRequestHandler):
    project: Project = None
    cli_command = None
    cli_cwd = None
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    # ---- guards: a localhost Host header (blocks DNS rebinding) and the session token
    def host_ok(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def token_ok(self, query):
        t = self.headers.get("X-Lineage-Token") or (query.get("token") or [""])[0]
        return bool(t) and secrets.compare_digest(t, TOKEN)

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def serve_bytes(self, data, ctype, extra=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, rel):
        f = (STATIC / rel).resolve()
        if STATIC.resolve() not in f.parents or not f.is_file():
            return self.send_error(404)
        data = f.read_bytes()
        if f.name == "index.html":
            data = data.replace(b"__LINEAGE_TOKEN__", TOKEN.encode())
            return self.serve_bytes(data, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        cache = "no-cache" if f.suffix in (".js", ".css") else "max-age=300"
        return self.serve_bytes(data, mimetypes.guess_type(f.name)[0] or "application/octet-stream", {"Cache-Control": cache})

    # ---- routing
    def route(self, method):
        if not self.host_ok():
            return self.send_error(403, "localhost only")
        u = urllib.parse.urlparse(self.path)
        path, query = u.path, urllib.parse.parse_qs(u.query)
        if method == "GET" and not path.startswith(("/api/", "/oauth/", "/join/")):
            return self.serve_static("index.html" if path == "/" else path.lstrip("/"))
        if path == "/oauth/google/callback":
            return self.google_callback(query)
        if method == "GET" and path.startswith("/join/"):
            return self.join(path.split("/join/", 1)[1])
        if not self.token_ok(query):
            return self.send_json({"error": "missing or wrong session token"}, 403)
        fn = ROUTES.get((method, path))
        if fn:
            return fn(self, query)
        if method == "GET" and path.startswith("/api/job/"):
            job = JOBS.get(path.rsplit("/", 1)[-1])
            return self.send_json(job or {"state": "unknown"}, 200 if job else 404)
        if method == "POST" and path.startswith("/api/run/"):
            return self.run_stage(path.rsplit("/", 1)[-1])
        return self.send_json({"error": "not found"}, 404)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    # ======================= ENGINE endpoints (neutral vocabulary) =======================
    def e_sources(self, q):
        return self.send_json({"sources": engine_sources(self.project)})

    def e_source(self, q):
        try:
            return self.send_json(engine_source_detail(self.project, (q.get("id") or [""])[0]))
        except (PermissionError, FileNotFoundError) as e:
            return self.send_json({"error": str(e)}, 400)

    def e_page(self, q):
        sid = self.read_json().get("source", "")
        try:
            if not self.project.inside(sid).is_file():
                return self.send_json({"error": "no such source"}, 404)
        except PermissionError as e:
            return self.send_json({"error": str(e)}, 400)
        jid = start_job([("Reading the source", 0.4), ("Collecting its exact words", 0.4)],
                        lambda: {"page": engine_make_page(self.project, sid)})
        return self.send_json({"job": jid})

    def e_approvals(self, q):
        return self.send_json({"items": engine_approvals(self.project)})

    def e_status(self, q):
        s = self.project.read()
        return self.send_json({"title": s.get("title"), "subject": s.get("subject"),
                               "stages": [{"id": k, "label": l, "status": s["stages"].get(k, "todo")} for k, l in STAGES]})

    def run_stage(self, stage):
        try:
            return self.send_json({"job": engine_run(self.project, stage)})
        except StageIsTerminalWork as w:
            return self.send_json({"terminal_prompt": w.prompt})
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def e_stories(self, q):
        return self.send_json({"stories": engine_stories(self.project), "states": STORY_STATES})

    def e_story_state(self, q):
        d = self.read_json()
        try:
            return self.send_json({"states": engine_set_story_state(self.project, d.get("id"), d.get("state"))})
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def e_story_render(self, q):
        sid = str(self.read_json().get("id", ""))
        jid = start_job([("Compiling the story with the book template", 0.1)],
                        lambda: engine_render_story(self.project, sid))
        return self.send_json({"job": jid})

    def e_story_script(self, q):
        try:
            st, text = story_script(self.project, (q.get("id") or [""])[0])
            return self.send_json({"id": st["id"], "text": text, "chars": len(text)})
        except PermissionError as e:
            return self.send_json({"blocked": str(e)})
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 400)

    def e_narrate(self, q):
        d = self.read_json()
        sid = str(d.get("id", ""))
        try:
            story_script(self.project, sid)
        except PermissionError as e:
            return self.send_json({"blocked": str(e)})
        except RuntimeError as e:
            return self.send_json({"error": str(e)}, 400)
        if not load_config()["keys"].get("elevenlabs"):
            return self.send_json({"error": "Add an ElevenLabs key in Connectors to narrate"}, 400)
        jid = start_job([("Writing the narration script", 0.1), ("Recording with ElevenLabs", 0.1)],
                        lambda: engine_narrate(self.project, sid, d.get("voice_id")))
        return self.send_json({"job": jid})

    def e_story_voice(self, q):
        d = self.read_json()
        v = story_voices(self.project)
        if d.get("voice_id"):
            v[str(d["id"])] = d["voice_id"]
        else:
            v.pop(str(d.get("id")), None)
        (self.project.root / "data" / "story_voices.json").write_text(json.dumps(v, indent=1))
        return self.send_json({"ok": True})

    def e_audio_zip(self, q):
        data = engine_audio_zip(self.project)
        title = re.sub(r"[^A-Za-z0-9]+", "-", self.project.read().get("title") or "lineage").strip("-")
        return self.serve_bytes(data, "application/zip", {"Content-Disposition": f'attachment; filename="{title}-audio.zip"'})

    def e_timeline(self, q):
        return self.send_json(engine_timeline(self.project))

    def e_timeline_svg(self, q):
        return self.serve_bytes(engine_timeline_svg(self.project), "image/svg+xml",
                                {"Content-Disposition": 'attachment; filename="timeline.svg"'})

    def e_timeline_star(self, q):
        d = self.read_json()
        p = self.project.root / "data" / "timeline_stars.json"
        stars = set(json.loads(p.read_text())) if p.exists() else set()
        (stars.add if d.get("star") else stars.discard)(d.get("id"))
        p.write_text(json.dumps(sorted(stars)))
        return self.send_json({"stars": sorted(stars)})

    def e_question(self, q):
        d = self.read_json()
        return self.send_json({"questions": add_question(self.project, d.get("text", ""), d.get("source", ""))})

    def h_home(self, q):
        return self.send_json(engine_home(self.project, int(q.get("story", ["0"])[0] or 0), int(q.get("relative", ["0"])[0] or 0)))

    def h_attention(self, q):
        return self.send_json(attention(self.project))

    def h_request_draft(self, q):
        d = self.read_json()
        try:
            return self.send_json(request_draft(self.project, d.get("kind"), d.get("about"), d.get("to")))
        except (KeyError, ValueError) as e:
            return self.send_json({"error": str(e)}, 400)

    def h_request_save(self, q):
        return self.send_json(request_save(self.project, self.read_json()))

    def h_request_mark(self, q):
        d = self.read_json()
        try:
            return self.send_json(request_mark(self.project, d.get("id"), d.get("status")))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def h_requests(self, q):
        return self.send_json(_requests(self.project))

    def g_graph(self, q):
        return self.send_json(genealogy_graph(self.project))

    def g_rebuild(self, q):
        jid = start_job([("Reading the sources for people and relationships", 0.1)], lambda: genealogy_rebuild(self.project))
        return self.send_json({"job": jid})

    def g_review(self, q):
        return self.send_json(genealogy_diff(self.project))

    def g_apply(self, q):
        try:
            return self.send_json(genealogy_apply(self.project, self.read_json().get("accept")))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def g_edit(self, q):
        d = self.read_json()
        try:
            return self.send_json(genealogy_edit(self.project, d.get("op"), d))
        except (ValueError, KeyError) as e:
            return self.send_json({"error": str(e)}, 400)

    def g_gedcom(self, q):
        return self.serve_bytes(genealogy_gedcom(self.project), "text/plain; charset=utf-8",
                                {"Content-Disposition": 'attachment; filename="lineage.ged"'})

    def g_import(self, q):
        d = self.read_json()
        return self.send_json(genealogy_import_gedcom(self.project, d.get("text", ""), d.get("filename", "import.ged")))

    def e_familypedia(self, q):
        return self.send_json({"articles": engine_familypedia(self.project)})

    def e_article(self, q):
        try:
            return self.send_json(engine_article(self.project, (q.get("slug") or [""])[0]))
        except KeyError as e:
            return self.send_json({"error": str(e)}, 404)

    def e_article_save(self, q):
        d = self.read_json()
        try:
            return self.send_json(engine_save_article(self.project, d.get("slug", ""), d))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def e_fp_meta(self, q):
        return self.send_json({"types": [{"type": t, "label": familypedia.TYPE_LABELS[t], "singular": familypedia.TYPE_SINGULAR[t],
                                          "infobox": familypedia.INFOBOX[t]} for t in familypedia.TYPES],
                               "links": familypedia.link_table(self.project)})

    def e_fp_search(self, q):
        types = [t for t in ((q.get("types") or [""])[0]).split(",") if t]
        return self.send_json({"hits": familypedia.search(self.project, (q.get("q") or [""])[0], types or None)})

    def e_fp_picker(self, q):
        return self.send_json({"groups": familypedia.picker(self.project, (q.get("q") or [""])[0])})

    def e_fp_subject(self, q):
        d = self.read_json()
        try:
            return self.send_json(familypedia.new_subject(self.project, d.get("title", ""), d.get("type", ""),
                                                          d.get("aliases") or [], d.get("kind", "")))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def e_tags(self, q):
        return self.send_json(familypedia.tags_for(self.project, (q.get("target") or [""])[0]))

    def e_tags_set(self, q):
        """Tag sources, records, photographs or timeline events to any article. Accepting a suggestion
        is the same call with state=accepted; nothing is tagged without my say."""
        d = self.read_json()
        targets = d.get("targets") or ([d["target"]] if d.get("target") else [])
        if not targets or not all(re.match(r"^(source|record|photo|event):.+", t) for t in targets):
            return self.send_json({"error": "targets must look like source:<id>, record:<id>, photo:<id> or event:<id>"}, 400)
        subject = d.get("subject")
        try:
            if not subject and d.get("new"):
                subject = familypedia.new_subject(self.project, d["new"].get("title", ""), d["new"].get("type", ""))["slug"]
            if not subject:
                return self.send_json({"error": "choose a subject"}, 400)
            r = familypedia.set_tags(self.project, targets, subject, d.get("state", "accepted"), d.get("evidence", ""))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        return self.send_json({**r, "subject": subject})

    def e_fp_catalogue(self, q):
        what = (q.get("what") or ["records"])[0]
        return self.send_json({"items": familypedia.catalogue(self.project, "photos" if what == "photos" else "records")})

    def e_fp_map(self, q):
        return self.send_json(familypedia.map_data(self.project, (q.get("focus") or [None])[0]))

    def e_story_apparatus(self, q):
        try:
            return self.send_json(story_apparatus(self.project, (q.get("id") or [""])[0]))
        except (KeyError, StopIteration) as e:
            return self.send_json({"error": str(e) or "no such story"}, 404)

    def e_fp_story(self, q):
        return self.send_json({"subjects": familypedia.story_subjects(self.project, (q.get("id") or [""])[0])})

    def e_episodes(self, q):
        out = self.project.root / "output"
        eps = []
        for f in sorted(out.glob("podcast-*.md")) + sorted((out / "audio").glob("*.mp3") if (out / "audio").exists() else []):
            eps.append({"id": f.relative_to(self.project.root).as_posix(), "name": f.stem,
                        "kind": "script" if f.suffix == ".md" else "audio", "bytes": f.stat().st_size,
                        "text": f.read_text(encoding="utf-8")[:20000] if f.suffix == ".md" else None})
        return self.send_json({"episodes": eps})

    # ======================= dashboard state (settings, uploads, files) =======================
    def upload(self, q):
        """Stage 1 of intake for each file, then the rest in the background. Duplicates aren't stored."""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(.+)$", ctype)
        if not m:
            return self.send_json({"error": "expected multipart"}, 400)
        boundary = m.group(1).strip('"').encode()
        body = self.rfile.read(int(self.headers["Content-Length"]))
        saved, duplicates = [], []
        for part in body.split(b"--" + boundary):
            if b"\r\n\r\n" not in part:
                continue
            head, data = part.split(b"\r\n\r\n", 1)
            fn = re.search(rb'filename="([^"]*)"', head)
            if not fn or not fn.group(1):
                continue
            if data.endswith(b"\r\n"):
                data = data[:-2]
            row, dup = intake_ingest(self.project, fn.group(1).decode(errors="replace"), data)
            if dup:
                duplicates.append({"name": Path(fn.group(1).decode(errors="replace")).name, "existing": dup["path"],
                                   "added": dup["date_added"], "rid": dup["id"]})
            else:
                saved.append({"name": Path(row["path"]).name, "size": row["bytes"], "rid": row["id"]})
                intake_start(self.project, row["id"])
        if saved:
            self.project.mark("sources", "done")
        return self.send_json({"saved": saved, "duplicates": duplicates})

    def e_scan(self, q):
        """Index a file that's in the project but not yet scanned, or re-scan one (keeps my edits)."""
        d = self.read_json()
        rid = d.get("rid")
        if not rid:
            try:
                self.project.inside(d.get("path", ""))
            except PermissionError as e:
                return self.send_json({"error": str(e)}, 400)
            rid = intake_adopt(self.project, d["path"])["id"]
        intake_start(self.project, rid)
        return self.send_json({"ok": True, "rid": rid})

    def e_scan_all(self, q):
        n = 0
        for row in engine_sources(self.project):
            if not row["rid"]:
                intake_start(self.project, intake_adopt(self.project, row["id"])["id"]); n += 1
        return self.send_json({"ok": True, "started": n})

    def e_source_meta(self, q):
        rid = (q.get("rid") or [""])[0]
        row = intake_load(self.project).get(rid)
        if not row:
            return self.send_json({"error": "not indexed yet"}, 404)
        ex = self.project.root / (row.get("extracted") or "")
        return self.send_json({**effective(row), "extracted_text": ex.read_text(encoding="utf-8")[:200000] if row.get("extracted") and ex.is_file() else "",
                               "drive_connected": drive_status()["connected"], "doc_kinds": DOC_KINDS})

    def e_source_edit(self, q):
        d = self.read_json()
        if d.get("rid") not in intake_load(self.project):
            return self.send_json({"error": "not indexed yet"}, 404)
        row = intake_edit(self.project, d["rid"], d)
        if d.get("rescan"):
            intake_start(self.project, d["rid"])
        return self.send_json(effective(row))

    def e_source_trash(self, q):
        d = self.read_json()
        if d.get("rid") not in intake_load(self.project):
            return self.send_json({"error": "not indexed"}, 404)
        return self.send_json(effective(intake_trash(self.project, d["rid"], restore=bool(d.get("restore")),
                                                     delete_drive=bool(d.get("delete_drive")))))

    def e_source_consequences(self, q):
        rows = intake_load(self.project)
        out = []
        for rid in (q.get("rid") or [""])[0].split(","):
            if rid in rows:
                c = source_citations(self.project, rows[rid])
                out.append({"rid": rid, "name": rows[rid].get("mine", {}).get("accepted_name") or rows[rid]["original_name"],
                            "in_drive": bool(rows[rid].get("drive_id")), **c})
        return self.send_json({"items": out})

    def e_source_purge(self, q):
        try:
            intake_purge(self.project, self.read_json().get("rid"))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        return self.send_json({"ok": True})

    def e_bulk(self, q):
        """One action on several sources: reingest, delete, or tag (people, places, date)."""
        d = self.read_json()
        rows = intake_load(self.project)
        rids = [r for r in d.get("rids", []) if r in rows]
        done = 0
        for rid in rids:
            if d.get("action") == "reingest":
                intake_start(self.project, rid)
            elif d.get("action") == "delete":
                intake_trash(self.project, rid, delete_drive=bool(d.get("delete_drive")))
            elif d.get("action") == "tag":
                eff = effective(rows[rid])
                patch = {}
                if d.get("person"):
                    patch["people"] = sorted(set(eff.get("people") or []) | {d["person"]})
                if d.get("place"):
                    patch["places"] = sorted(set(eff.get("places") or []) | {d["place"]})
                if d.get("date"):
                    patch["date_range"] = d["date"]
                intake_edit(self.project, rid, patch)
            done += 1
        return self.send_json({"ok": True, "done": done})

    def e_trash(self, q):
        return self.send_json({"trash": [effective(r) for r in intake_load(self.project).values() if r.get("trashed")]})

    def e_search(self, q):
        return self.send_json({"hits": engine_search(self.project, (q.get("q") or [""])[0])})

    def e_transcribe(self, q):
        """Queue a recording for transcription. Runs once per file, never twice."""
        rid = self.read_json().get("rid")
        rows = intake_load(self.project)
        row = rows.get(rid)
        if not row or row["kind"] not in ("audio", "video"):
            return self.send_json({"error": "only recordings can be transcribed"}, 400)
        if row.get("transcription") in ("done", "running"):
            return self.send_json({"error": f"already {row['transcription']} — transcription never runs twice on the same file"}, 409)
        home = lineage_home()
        script = home / "scripts" / "transcribe.sh" if home else None
        venv_wx = (home.parent.parent / ".venv" / "bin" / "whisperx") if home else None
        if not script or not script.exists() or not (shutil.which("whisperx") or (venv_wx and venv_wx.exists())):
            return self.send_json({"error": "transcription tools aren't installed here: run `make install-transcribe` in the Lineage repo"}, 400)
        row["transcription"] = "running"
        row["history"].append({"at": _now(), "by": "me", "event": "transcription started"})
        intake_save_row(self.project, row)
        proj = self.project

        def go():
            r = subprocess.run(["bash", str(script), "--project", str(proj.root), str(proj.root / row["path"])],
                               capture_output=True, text=True, cwd=str(proj.root))
            cur = intake_load(proj)[rid]
            cur["transcription"] = "done" if r.returncode == 0 else "failed"
            cur["history"].append({"at": _now(), "by": "system", "event": f"transcription {cur['transcription']}"})
            intake_save_row(proj, cur)
            if r.returncode == 0:
                intake_run(proj, rid)
        threading.Thread(target=go, daemon=True).start()
        return self.send_json({"ok": True})

    def file(self, q):
        """Serve a project file to the page (audio for the transcript drawer). Supports Range."""
        try:
            p = self.project.inside((q.get("path") or [""])[0])
        except PermissionError:
            return self.send_error(403)
        if not p.is_file():
            return self.send_error(404)
        size = p.stat().st_size
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if m:
            start = int(m.group(1) or 0)
            end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            with open(p, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        return self.serve_bytes(p.read_bytes(), ctype, {"Accept-Ranges": "bytes"})

    def reveal(self, q):
        """Open a project file with the system's default app."""
        try:
            p = self.project.inside(self.read_json().get("path", ""))
        except PermissionError as e:
            return self.send_json({"error": str(e)}, 400)
        opener = "open" if shutil.which("open") else "xdg-open" if shutil.which("xdg-open") else None
        if not opener:
            return self.send_json({"ok": False, "detail": "no 'open' or 'xdg-open' on this machine"})
        subprocess.Popen([opener, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.send_json({"ok": True})

    def bootstrap(self, q):
        cfg = load_config()
        state = self.project.read()
        pv = STATIC / "previews"
        return self.send_json({
            "project": str(self.project.root), "state": state, "stages": STAGES,
            "chapter_templates": CHAPTER_TEMPLATES, "narrative_styles": NARRATIVE_STYLES,
            "voice_samples": VOICE_SAMPLES, "photo_styles": PHOTO_STYLES, "writing_options": WRITING_OPTIONS,
            "trims": TRIMS, "printers": PRINTERS, "quick_prompts": QUICK_PROMPTS,
            "keys": {p: mask(cfg["keys"].get(p, "")) for p in PROVIDERS},
            "providers": {p: {"label": v["label"], "use": v["use"]} for p, v in PROVIDERS.items()},
            "paths": self.paths(), "terminal": TERMINAL.info(), "identity": engine_identity(self.project), "demo": DEMO,
            "previews": sorted(p.name for p in pv.glob("*.png")) if pv.exists() else [],
        })

    def paths(self):
        root = self.project.root
        return {"keys file": str(CONFIG_FILE), "Google token": str(GOOGLE_TOKEN_FILE),
                "project": str(root), "settings": str(root / "lineage.json"), "sources": str(root / "sources"),
                "transcripts": str(root / "transcript"), "output": str(root / "output"),
                "terminal log": str(root / ".lineage" / "terminal.log")}

    def get_settings(self, q):
        s = self.project.read()
        return self.send_json({"title": s.get("title", ""), "subject": s.get("subject", ""), "settings": s["settings"]})

    def post_settings(self, q):
        d = self.read_json()
        s = self.project.read()
        stale = set(s.get("stale", []))
        for k, deps in IDENTITY_DEPENDENTS.items():
            old = s.get(k) if k == "title" else s["settings"].get(k)
            if k in d and str(d[k]) != str(old or ""):
                stale.update(deps)
        s["stale"] = sorted(stale)
        for k in ("title", "subject"):
            if k in d:
                s[k] = str(d.pop(k))
        s["settings"].update(d)
        self.project.write(s)
        return self.send_json({"title": s["title"], "subject": s["subject"], "settings": s["settings"],
                               "identity": engine_identity(self.project)})

    def identity(self, q):
        return self.send_json(engine_identity(self.project))

    def identity_draft(self, q):
        return self.send_json({"summary": engine_draft_summary(self.project), "by": "derived"})

    def identity_fresh(self, q):
        """The author has looked at the stale pages; clear the marks."""
        s = self.project.read()
        drop = set(self.read_json().get("items") or s.get("stale", []))
        s["stale"] = [x for x in s.get("stale", []) if x not in drop]
        self.project.write(s)
        return self.send_json(engine_identity(self.project))

    def crest_get(self, q):
        return self.send_json(crest_state(self.project))

    def crest_fill(self, q):
        return self.send_json({"prompt": crest_prompt_fill(self.project)})

    def crest_gen(self, q):
        d = self.read_json()
        if not load_config()["keys"].get("openai"):
            return self.send_json({"error": "Add an OpenAI key in Connectors"}, 400)
        jid = start_job([("Drawing four candidates", 0.1)], lambda: crest_generate(self.project, d.get("prompt", ""), d.get("style", "engraved")))
        return self.send_json({"job": jid})

    def crest_pick(self, q):
        try:
            return self.send_json(crest_choose(self.project, self.read_json().get("name", "")))
        except FileNotFoundError as e:
            return self.send_json({"error": str(e)}, 404)

    def crest_variant_ep(self, q):
        try:
            return self.send_json(crest_variant(self.project, self.read_json().get("kind")))
        except (RuntimeError, KeyError) as e:
            return self.send_json({"error": str(e)}, 400)

    def crest_upload_ep(self, q):
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(.+)$", ctype)
        if not m:
            return self.send_json({"error": "expected multipart"}, 400)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        fields, file = {}, None
        for part in body.split(b"--" + m.group(1).strip('"').encode()):
            if b"\r\n\r\n" not in part:
                continue
            head, data = part.split(b"\r\n\r\n", 1)
            data = data[:-2] if data.endswith(b"\r\n") else data
            nm = re.search(rb'name="([^"]*)"', head)
            fn = re.search(rb'filename="([^"]*)"', head)
            if fn and fn.group(1):
                file = (fn.group(1).decode(errors="replace"), data)
            elif nm:
                fields[nm.group(1).decode()] = data.decode(errors="replace")
        if not file:
            return self.send_json({"error": "no file"}, 400)
        try:
            return self.send_json(crest_upload(self.project, file[0], file[1], fields.get("provenance", "design"), fields.get("note", "")))
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    def crest(self, q):
        """One image file: the family crest or cover, used on the header and title page."""
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(.+)$", ctype)
        if not m:
            return self.send_json({"error": "expected multipart"}, 400)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        for part in body.split(b"--" + m.group(1).strip('"').encode()):
            fn = re.search(rb'filename="([^"]*)"', part.split(b"\r\n\r\n", 1)[0])
            if fn and fn.group(1) and b"\r\n\r\n" in part:
                ext = Path(fn.group(1).decode(errors="replace")).suffix.lower()
                if ext not in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
                    return self.send_json({"error": "use a PNG, JPEG, SVG, WebP or GIF"}, 400)
                data = part.split(b"\r\n\r\n", 1)[1]
                data = data[:-2] if data.endswith(b"\r\n") else data
                for old in (self.project.root / ".lineage").glob("crest.*"):
                    old.unlink()
                (self.project.root / ".lineage" / f"crest{ext}").write_bytes(data)
                s = self.project.read()
                s["stale"] = sorted(set(s.get("stale", [])) | {"title page", "Familypedia front page"})
                self.project.write(s)
                return self.send_json(engine_identity(self.project))
        return self.send_json({"error": "no file"}, 400)

    def voices(self, q):
        v, live = list_voices(load_config()["keys"].get("elevenlabs", ""))
        return self.send_json({"voices": v, "live": live})

    # ======================= AUTHOR-ONLY endpoints =======================
    def post_key(self, q):
        d = self.read_json()
        provider, key = d.get("provider"), (d.get("key") or "").strip()
        if provider not in PROVIDERS:
            return self.send_json({"ok": False, "detail": "unknown provider"}, 400)
        cfg = load_config()
        if d.get("remove"):
            cfg["keys"].pop(provider, None)
            save_config(cfg)
            return self.send_json({"ok": False, "detail": "disconnected", "masked": ""})
        res = check_key(provider, key) if key else {"ok": False, "detail": "empty"}
        if key and res["ok"] is not False:
            cfg["keys"][provider] = key
            save_config(cfg)
        res.pop("body", None)
        return self.send_json({**res, "masked": mask(key) if res["ok"] is not False else ""})

    def recheck_key(self, q):
        provider = self.read_json().get("provider")
        key = load_config()["keys"].get(provider, "")
        if not key:
            return self.send_json({"ok": False, "detail": "not set"})
        res = check_key(provider, key)
        res.pop("body", None)
        return self.send_json(res)

    def connectors(self, q):
        cfg = load_config()
        return self.send_json({
            "keys": {p: mask(cfg["keys"].get(p, "")) for p in PROVIDERS},
            "drive": drive_status(), "gh": gh_status(), "clis": detect_clis(),
            "terminal_command": self.project.read()["settings"].get("terminal_command") or self.cli_command or "claude",
        })

    def repo_verify(self, q):
        return self.send_json(repo_status(self.read_json().get("path") or self.project.root))

    def repo_init(self, q):
        path = Path(self.read_json().get("path") or self.project.root).expanduser()
        if not path.is_dir():
            return self.send_json({"ok": False, "detail": "folder does not exist"})
        r = git(path, "init", "-q")
        return self.send_json({"ok": r.returncode == 0, **repo_status(path)})

    def repo_push(self, q):
        st = repo_status(self.project.root)
        if not st.get("git") or not st.get("remote"):
            return self.send_json({"ok": False, "detail": "the project is not a git repo with an 'origin' remote"})
        r = git(self.project.root, "push", "origin", "HEAD", timeout=120)
        return self.send_json({"ok": r.returncode == 0, "detail": (r.stderr or r.stdout).strip()[-600:] or "pushed"})

    def use_project(self, q):
        p = Path(self.read_json().get("path", "")).expanduser()
        if not p.is_dir():
            return self.send_json({"ok": False, "detail": "folder does not exist"})
        Handler.project = Project(p)
        TERMINAL.attach(Handler.project.root)
        return self.send_json({"ok": True, "project": str(Handler.project.root)})

    def drive_verify_ep(self, q):
        folder = self.read_json().get("folder", "")
        res = drive_verify(folder)
        s = self.project.read()
        s["settings"]["drive_folder"] = folder
        s["settings"]["drive_verified"] = res.get("ok")
        self.project.write(s)
        return self.send_json(res)

    def google_client(self, q):
        d = self.read_json()
        cfg = load_config()
        cfg["google"] = {"client_id": d.get("client_id", "").strip(), "client_secret": d.get("client_secret", "").strip()}
        save_config(cfg)
        return self.send_json({"ok": True, **drive_status()})

    def google_device_start(self, q):
        g = load_config()["google"]
        if not g.get("client_id"):
            return self.send_json({"ok": False, "detail": "add an OAuth client ID first"})
        res = _post_form("https://oauth2.googleapis.com/device/code", {"client_id": g["client_id"], "scope": DEVICE_SCOPES})
        if "device_code" not in res:
            return self.send_json({"ok": False, "detail": res.get("error_description") or res.get("error") or "Google refused"})
        GOOGLE_DEVICE.clear()
        GOOGLE_DEVICE.update(res)
        return self.send_json({"ok": True, "user_code": res["user_code"],
                               "verification_url": res.get("verification_url") or res.get("verification_uri"),
                               "interval": res.get("interval", 5)})

    def google_device_poll(self, q):
        g = load_config()["google"]
        if not GOOGLE_DEVICE.get("device_code"):
            return self.send_json({"state": "none"})
        res = _post_form("https://oauth2.googleapis.com/token", {
            "client_id": g["client_id"], "client_secret": g.get("client_secret", ""),
            "device_code": GOOGLE_DEVICE["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if "access_token" in res:
            save_google_token(res, DEVICE_SCOPES)
            GOOGLE_DEVICE.clear()
            return self.send_json({"state": "connected", **drive_status()})
        return self.send_json({"state": res.get("error", "pending")})

    def google_browser_url(self, q):
        g = load_config()["google"]
        if not g.get("client_id"):
            return self.send_json({"ok": False, "detail": "add an OAuth client ID first"})
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        state = secrets.token_urlsafe(16)
        GOOGLE_PKCE.clear()
        GOOGLE_PKCE.update(verifier=verifier, state=state)
        params = {"client_id": g["client_id"], "redirect_uri": f"http://127.0.0.1:{PORT}/oauth/google/callback",
                  "response_type": "code", "scope": BROWSER_SCOPES, "code_challenge": challenge,
                  "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent", "state": state}
        return self.send_json({"ok": True, "url": "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)})

    def google_callback(self, query):
        code, state = (query.get("code") or [""])[0], (query.get("state") or [""])[0]
        ok = False
        if code and state and GOOGLE_PKCE.get("state") and secrets.compare_digest(state, GOOGLE_PKCE["state"]):
            g = load_config()["google"]
            res = _post_form("https://oauth2.googleapis.com/token", {
                "client_id": g["client_id"], "client_secret": g.get("client_secret", ""), "code": code,
                "code_verifier": GOOGLE_PKCE["verifier"], "grant_type": "authorization_code",
                "redirect_uri": f"http://127.0.0.1:{PORT}/oauth/google/callback"})
            if "access_token" in res:
                save_google_token(res, BROWSER_SCOPES)
                ok = True
        GOOGLE_PKCE.clear()
        self.send_response(302)
        self.send_header("Location", "/#connectors" + ("" if ok else "-drive-failed"))
        self.end_headers()

    def google_disconnect(self, q):
        if GOOGLE_TOKEN_FILE.exists():
            GOOGLE_TOKEN_FILE.unlink()
        return self.send_json({"ok": True, **drive_status()})

    # ---- family (owner-only)
    def family_get(self, q):
        return self.send_json(family_view(self.project))

    def family_member(self, q):
        d = self.read_json()
        data = family_load(self.project)
        if d.get("role") and d["role"] not in FAMILY_ROLES:
            return self.send_json({"error": f"role must be one of {FAMILY_ROLES}"}, 400)
        if d.get("id"):
            m = next((m for m in data["members"] if m["id"] == d["id"]), None)
            if not m:
                return self.send_json({"error": "no such member"}, 404)
            for k in ("name", "relationship", "email", "role", "status"):
                if k in d:
                    m[k] = d[k]
        else:
            if not d.get("name"):
                return self.send_json({"error": "a name is needed"}, 400)
            data["members"].append({"id": uuid.uuid4().hex[:10], "name": d["name"], "relationship": d.get("relationship", ""),
                                    "email": d.get("email", ""), "role": d.get("role", "contributor"), "status": "invited",
                                    "added": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        family_save(self.project, data)
        return self.send_json(family_view(self.project))

    def family_invite(self, q):
        d = self.read_json()
        data = family_load(self.project)
        if not any(m["id"] == d.get("member") for m in data["members"]):
            return self.send_json({"error": "no such member"}, 404)
        for i in data["invites"]:
            if i["member"] == d["member"]:
                i["revoked"] = True
        data["invites"].append({"token": secrets.token_urlsafe(24), "member": d["member"],
                                "expires": time.time() + 86400 * int(d.get("days", 14)), "revoked": False})
        family_save(self.project, data)
        return self.send_json(family_view(self.project))

    def family_revoke(self, q):
        d = self.read_json()
        data = family_load(self.project)
        for i in data["invites"]:
            if i["member"] == d.get("member"):
                i["revoked"] = True
        family_save(self.project, data)
        return self.send_json(family_view(self.project))

    def join(self, token):
        """An invite link. Validated server-side; the contributor view arrives with hosting."""
        data = family_load(self.project)
        inv = next((i for i in data["invites"] if secrets.compare_digest(i["token"], token)), None)
        ok = inv and not inv.get("revoked") and inv["expires"] > time.time()
        m = next((m for m in data["members"] if inv and m["id"] == inv["member"]), None)
        msg = (f"This invitation for {m['name']} ({m['role']}) is valid. The page where relatives add "
               f"their material arrives when the project is hosted." if ok and m else
               "This invitation has expired or been revoked. Ask for a new link.")
        body = (f"<!doctype html><meta charset='utf-8'><title>Lineage</title><body style='font-family:system-ui;"
                f"background:#F7F3EC;color:#1C1A17;max-width:560px;margin:15vh auto;padding:0 20px'>"
                f"<h1 style='font-family:Georgia,serif'>Lineage</h1><p>{html_escape(msg)}</p></body>").encode()
        return self.serve_bytes(body, "text/html; charset=utf-8", {"Cache-Control": "no-store"})

    # ---- terminal
    def term_info(self, q):
        return self.send_json(TERMINAL.info())

    def term_start(self, q):
        s = self.project.read()["settings"]
        command = s.get("terminal_command") or self.cli_command or "claude"
        cwd = s.get("terminal_cwd") or self.cli_cwd or str(self.project.root)
        TERMINAL.attach(self.project.root)
        TERMINAL.start(command, Path(cwd).expanduser())
        return self.send_json(TERMINAL.info())

    def term_input(self, q):
        ok = TERMINAL.write(self.read_json().get("data", "").encode("utf-8"))
        return self.send_json({"ok": ok, **({} if ok else TERMINAL.info())})

    def term_resize(self, q):
        d = self.read_json()
        TERMINAL.resize(d.get("cols", 100), d.get("rows", 30))
        return self.send_json({"ok": True, "cols": TERMINAL.cols, "rows": TERMINAL.rows})

    def term_stop(self, q):
        return self.send_json({"ok": TERMINAL.interrupt(), **TERMINAL.info()})

    def term_clear(self, q):
        TERMINAL.clear()
        return self.send_json({"ok": True})

    def term_stream(self, q):
        """Server-Sent Events: the scrollback first, then live output and status changes."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        sub = TERMINAL.subscribe()

        def event(kind, payload):
            data = payload if isinstance(payload, str) else json.dumps(payload)
            self.wfile.write(f"event: {kind}\ndata: {data}\n\n".encode())
            self.wfile.flush()
        try:
            event("hello", {**TERMINAL.info(), "scrollback": base64.b64encode(TERMINAL.scrollback()).decode()})
            while True:
                try:
                    kind, payload = sub.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                event(kind, payload)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            TERMINAL.unsubscribe(sub)


ROUTES = {
    # engine (neutral; a second front end can use these)
    ("GET", "/api/engine/sources"): Handler.e_sources,
    ("GET", "/api/engine/source"): Handler.e_source,
    ("POST", "/api/engine/page"): Handler.e_page,
    ("GET", "/api/engine/approvals"): Handler.e_approvals,
    ("GET", "/api/engine/status"): Handler.e_status,
    ("GET", "/api/engine/stories"): Handler.e_stories,
    ("POST", "/api/engine/story/state"): Handler.e_story_state,
    ("POST", "/api/engine/story/render"): Handler.e_story_render,
    ("GET", "/api/engine/familypedia"): Handler.e_familypedia,
    ("GET", "/api/engine/familypedia/meta"): Handler.e_fp_meta,
    ("GET", "/api/engine/familypedia/search"): Handler.e_fp_search,
    ("GET", "/api/engine/familypedia/picker"): Handler.e_fp_picker,
    ("POST", "/api/engine/familypedia/subject"): Handler.e_fp_subject,
    ("GET", "/api/engine/familypedia/catalogue"): Handler.e_fp_catalogue,
    ("GET", "/api/engine/familypedia/map"): Handler.e_fp_map,
    ("GET", "/api/engine/familypedia/story"): Handler.e_fp_story,
    ("GET", "/api/engine/story/apparatus"): Handler.e_story_apparatus,
    ("GET", "/api/engine/tags"): Handler.e_tags,
    ("POST", "/api/engine/tags"): Handler.e_tags_set,
    ("GET", "/api/engine/home"): Handler.h_home,
    ("GET", "/api/engine/attention"): Handler.h_attention,
    ("GET", "/api/engine/requests"): Handler.h_requests,
    ("POST", "/api/engine/request/draft"): Handler.h_request_draft,
    ("POST", "/api/engine/request/save"): Handler.h_request_save,
    ("POST", "/api/engine/request/mark"): Handler.h_request_mark,
    ("GET", "/api/engine/genealogy"): Handler.g_graph,
    ("POST", "/api/engine/genealogy/rebuild"): Handler.g_rebuild,
    ("GET", "/api/engine/genealogy/review"): Handler.g_review,
    ("POST", "/api/engine/genealogy/apply"): Handler.g_apply,
    ("POST", "/api/engine/genealogy/edit"): Handler.g_edit,
    ("GET", "/api/engine/genealogy.ged"): Handler.g_gedcom,
    ("POST", "/api/engine/genealogy/import"): Handler.g_import,
    ("GET", "/api/engine/timeline"): Handler.e_timeline,
    ("GET", "/api/engine/timeline.svg"): Handler.e_timeline_svg,
    ("POST", "/api/engine/timeline/star"): Handler.e_timeline_star,
    ("POST", "/api/engine/question"): Handler.e_question,
    ("GET", "/api/engine/article"): Handler.e_article,
    ("POST", "/api/engine/article"): Handler.e_article_save,
    ("GET", "/api/engine/episodes"): Handler.e_episodes,
    ("GET", "/api/engine/story/script"): Handler.e_story_script,
    ("POST", "/api/engine/story/narrate"): Handler.e_narrate,
    ("POST", "/api/engine/story/voice"): Handler.e_story_voice,
    ("GET", "/api/engine/audio.zip"): Handler.e_audio_zip,
    # dashboard state
    ("GET", "/api/bootstrap"): Handler.bootstrap,
    ("GET", "/api/settings"): Handler.get_settings,
    ("POST", "/api/settings"): Handler.post_settings,
    ("GET", "/api/identity"): Handler.identity,
    ("POST", "/api/identity/draft-summary"): Handler.identity_draft,
    ("POST", "/api/identity/fresh"): Handler.identity_fresh,
    ("POST", "/api/identity/crest"): Handler.crest,
    ("GET", "/api/crest"): Handler.crest_get,
    ("POST", "/api/crest/fill"): Handler.crest_fill,
    ("POST", "/api/crest/generate"): Handler.crest_gen,
    ("POST", "/api/crest/choose"): Handler.crest_pick,
    ("POST", "/api/crest/variant"): Handler.crest_variant_ep,
    ("POST", "/api/crest/upload"): Handler.crest_upload_ep,
    ("POST", "/api/upload"): Handler.upload,
    ("POST", "/api/engine/source/scan"): Handler.e_scan,
    ("POST", "/api/engine/source/scan-all"): Handler.e_scan_all,
    ("GET", "/api/engine/source/meta"): Handler.e_source_meta,
    ("POST", "/api/engine/source/edit"): Handler.e_source_edit,
    ("POST", "/api/engine/source/trash"): Handler.e_source_trash,
    ("GET", "/api/engine/trash"): Handler.e_trash,
    ("GET", "/api/engine/source/consequences"): Handler.e_source_consequences,
    ("POST", "/api/engine/source/purge"): Handler.e_source_purge,
    ("POST", "/api/engine/source/bulk"): Handler.e_bulk,
    ("GET", "/api/engine/search"): Handler.e_search,
    ("POST", "/api/engine/source/transcribe"): Handler.e_transcribe,
    ("GET", "/api/file"): Handler.file,
    ("POST", "/api/reveal"): Handler.reveal,
    ("GET", "/api/voices"): Handler.voices,
    # author-only surface
    ("POST", "/api/key"): Handler.post_key,
    ("POST", "/api/key/recheck"): Handler.recheck_key,
    ("GET", "/api/connectors"): Handler.connectors,
    ("POST", "/api/repo/verify"): Handler.repo_verify,
    ("POST", "/api/repo/init"): Handler.repo_init,
    ("POST", "/api/repo/push"): Handler.repo_push,
    ("POST", "/api/project"): Handler.use_project,
    ("POST", "/api/drive/verify"): Handler.drive_verify_ep,
    ("POST", "/api/google/client"): Handler.google_client,
    ("POST", "/api/google/device/start"): Handler.google_device_start,
    ("POST", "/api/google/device/poll"): Handler.google_device_poll,
    ("GET", "/api/google/browser-url"): Handler.google_browser_url,
    ("POST", "/api/google/disconnect"): Handler.google_disconnect,
    ("GET", "/api/family"): Handler.family_get,
    ("POST", "/api/family/member"): Handler.family_member,
    ("POST", "/api/family/invite"): Handler.family_invite,
    ("POST", "/api/family/revoke"): Handler.family_revoke,
    ("GET", "/api/term"): Handler.term_info,
    ("POST", "/api/term/start"): Handler.term_start,
    ("POST", "/api/term/input"): Handler.term_input,
    ("POST", "/api/term/resize"): Handler.term_resize,
    ("POST", "/api/term/stop"): Handler.term_stop,
    ("POST", "/api/term/clear"): Handler.term_clear,
    ("GET", "/api/term/stream"): Handler.term_stream,
}


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    global PORT
    ap = argparse.ArgumentParser(description="Lineage dashboard (binds to 127.0.0.1 only)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("LINEAGE_PORT", 8777)))
    ap.add_argument("--project", default=str(Path.home() / "lineage-books" / "my-book"))
    ap.add_argument("--command", default=None, help="terminal command (default: claude, or the one picked in Connectors)")
    ap.add_argument("--cwd", default=None, help="terminal working folder (default: the project)")
    ap.add_argument("--demo", action="store_true", help="invented sample results for development (shown with a banner)")
    a = ap.parse_args()
    global DEMO
    DEMO = a.demo
    PORT = a.port
    Handler.project = Project(a.project)
    Handler.cli_command, Handler.cli_cwd = a.command, a.cwd
    TERMINAL.attach(Handler.project.root)
    with Server(("127.0.0.1", a.port), Handler) as httpd:
        print(f"\n  Lineage   →  http://127.0.0.1:{a.port}")
        print(f"  project   →  {Handler.project.root}")
        print(f"  keys      →  {CONFIG_FILE} (chmod 600, this machine only)")
        print("  terminal  →  localhost only, session token required\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            TERMINAL.stop_process()
            print("\n  stopped\n")


if __name__ == "__main__":
    main()
