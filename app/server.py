#!/usr/bin/env python3
"""Lineage — a local dashboard for turning recorded interviews into a family book.

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
import secrets, shlex, shutil, signal, socketserver, struct, subprocess, termios, threading, time
import urllib.error, urllib.parse, urllib.request, uuid, warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*fork.*")

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
CONFIG_DIR = Path.home() / ".lineage"
CONFIG_FILE = CONFIG_DIR / "config.json"
GOOGLE_TOKEN_FILE = CONFIG_DIR / "google_token.json"
TOKEN = secrets.token_urlsafe(32)          # minted at start, injected into index.html
PORT = 8777

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
}


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
            rows.append({
                "id": f.relative_to(project.root).as_posix(), "name": f.name, "kind": kind, "bytes": st.st_size,
                "added": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "duration": media_duration(f) if kind in ("audio", "video") else None,
                "session": sid, "transcribed": transcribed, "units": n_units, "cited_in": cited,
                "status": status, "file_url": f.as_uri(),
                "drive_url": f"https://drive.google.com/file/d/{drive[f.name]}/view" if f.name in drive else None,
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


def engine_run(project, stage):
    """Start a pipeline stage as a job. Returns a job id."""
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
    "github": {"label": "GitHub", "use": "Push the book repo", "prefix": "",
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
        return DEMO_VOICES, False
    res = check_key("elevenlabs", key)
    voices = (res.get("body") or {}).get("voices") if res.get("ok") else None
    if not voices:
        return DEMO_VOICES, False
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
        return self.serve_bytes(data, mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                                {"Cache-Control": "max-age=300"})

    # ---- routing
    def route(self, method):
        if not self.host_ok():
            return self.send_error(403, "localhost only")
        u = urllib.parse.urlparse(self.path)
        path, query = u.path, urllib.parse.parse_qs(u.query)
        if method == "GET" and not path.startswith("/api/") and not path.startswith("/oauth/"):
            return self.serve_static("index.html" if path == "/" else path.lstrip("/"))
        if path == "/oauth/google/callback":
            return self.google_callback(query)
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
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)

    # ======================= dashboard state (settings, uploads, files) =======================
    def upload(self, q):
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r"boundary=(.+)$", ctype)
        if not m:
            return self.send_json({"error": "expected multipart"}, 400)
        boundary = m.group(1).strip('"').encode()
        body = self.rfile.read(int(self.headers["Content-Length"]))
        saved = []
        for part in body.split(b"--" + boundary):
            if b"\r\n\r\n" not in part:
                continue
            head, data = part.split(b"\r\n\r\n", 1)
            fn = re.search(rb'filename="([^"]*)"', head)
            if not fn or not fn.group(1):
                continue
            name = Path(fn.group(1).decode(errors="replace")).name
            if data.endswith(b"\r\n"):
                data = data[:-2]
            out = self.project.root / "sources" / name
            if out.exists():                       # originals are never overwritten
                out = out.with_name(f"{out.stem} ({datetime.now().strftime('%Y%m%d-%H%M%S')}){out.suffix}")
            out.write_bytes(data)
            saved.append({"name": out.name, "size": out.stat().st_size})
        if saved:
            self.project.mark("sources", "done")
        return self.send_json({"saved": saved})

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
            "paths": self.paths(), "terminal": TERMINAL.info(),
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
        for k in ("title", "subject"):
            if k in d:
                s[k] = str(d.pop(k))
        s["settings"].update(d)
        self.project.write(s)
        return self.send_json({"title": s["title"], "subject": s["subject"], "settings": s["settings"]})

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
    # dashboard state
    ("GET", "/api/bootstrap"): Handler.bootstrap,
    ("GET", "/api/settings"): Handler.get_settings,
    ("POST", "/api/settings"): Handler.post_settings,
    ("POST", "/api/upload"): Handler.upload,
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
    a = ap.parse_args()
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
